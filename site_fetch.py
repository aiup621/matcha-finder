import os, re, time, html, urllib.parse
import requests

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None  # 無くても最低限動く

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

def _timeout():
    try:
        return float(os.getenv("REQUESTS_TIMEOUT", "15"))
    except Exception:
        return 15.0

class Site:
    """属性でも dict 風でもアクセスできる薄いラッパー"""
    __slots__ = ("url","status","html","text","headers","title","metas","links","soup")
    def __init__(self, **kw):
        for k,v in kw.items():
            setattr(self, k, v)
    def __getitem__(self, k):
        return getattr(self, k)
    def get(self, k, default=None):
        try:
            return getattr(self, k)
        except AttributeError:
            return default

def _absolutize(base, href):
    if not href: return ""
    href = href.strip()
    if href.startswith("mailto:") or href.startswith("tel:"):
        return href
    try:
        return urllib.parse.urljoin(base, href)
    except Exception:
        return href

def fetch_site(url: str, screenshot_path=None):
    """URL を取得して title/meta/リンクの簡易情報を返す"""
    if not url:
        return Site(url="", status=0, html="", text="", headers={}, title="", metas={}, links=[], soup=None)

    # scheme 無しでも https:// 付与
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", url):
        url = "https://" + url

    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers, timeout=_timeout(), allow_redirects=True)
    except Exception:
        # 失敗時は空サイトを返して上位に任せる
        return Site(url=url, status=0, html="", text="", headers={}, title="", metas={}, links=[], soup=None)

    text = r.text or ""
    html_text = text
    title = ""
    metas = {}
    links = []
    soup = None

    if BeautifulSoup is not None and (r.headers.get("content-type","").lower().startswith("text/html") or "<html" in text.lower()):
        try:
            soup = BeautifulSoup(text, "html.parser")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            # <meta name / property> をざっくり収集
            for m in soup.find_all("meta"):
                k = m.get("name") or m.get("property")
                v = m.get("content")
                if k and v:
                    metas.setdefault(k.strip().lower(), v.strip())
            # aリンク収集（最大200件）
            for a in soup.find_all("a", href=True)[:200]:
                href = _absolutize(r.url, a.get("href"))
                text = a.get_text(" ", strip=True) or ""
                links.append((href, text))
        except Exception:
            pass
    else:
        # HTML でない場合は title などは空のまま
        pass

    return Site(
        url=r.url, status=getattr(r, "status_code", 0), html=html_text, text=html_text,
        headers=dict(r.headers), title=title, metas=metas, links=links, soup=soup
    )