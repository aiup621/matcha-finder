from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

def _dedupe(seq):
    seen = set(); out = []
    for x in seq or []:
        if not x: continue
        if x in seen: continue
        seen.add(x); out.append(x)
    return out

def fetch_site(url, screenshot_path=None, timeout_ms=45000):
    """指定URLを開いて、基本要素を抽出して返す。
    戻り値: {"status","html","instagram","menus","emails","forms"}
    """
    result = {"status": None, "html": "", "instagram": "", "menus": [], "emails": [], "forms": []}
    with sync_playwright() as p:
        # 証明書エラーを無視、かつ Chromium にもフラグを渡す
        browser = p.chromium.launch(headless=True, args=["--ignore-certificate-errors"])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        resp = None
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception:
            # httpsで失敗なら http で再試行
            if url.startswith("https://"):
                try:
                    resp = page.goto("http://" + url[len("https://"):], wait_until="domcontentloaded", timeout=timeout_ms)
                except Exception:
                    resp = None

        if resp:
            try:
                result["status"] = resp.status
            except Exception:
                result["status"] = None

        # スクショは任意
        if screenshot_path:
            try:
                page.screenshot(path=screenshot_path, full_page=True)
            except Exception:
                pass

        html = ""
        try:
            html = page.content()
        except Exception:
            html = ""
        result["html"] = html or ""
        soup = BeautifulSoup(html or "", "lxml")

        # すべてのリンクを絶対URL化
        links = []
        for a in soup.find_all("a", href=True):
            try:
                links.append(urljoin(page.url, a["href"]))
            except Exception:
                pass

        # Instagram
        result["instagram"] = next((l for l in links if "instagram.com" in l), "")

        # メニュー候補
        menu_keys = ("menu", "/menu", "menus", "our-menu", "food-menu", "drink-menu", "cafe-menu", "beverage")
        result["menus"] = _dedupe([l for l in links if any(k in l.lower() for k in menu_keys)])[:10]

        # 問い合わせフォーム候補
        form_keys = ("contact", "contact-us", "/contact", "contactus")
        result["forms"] = _dedupe([l for l in links if any(k in l.lower() for k in form_keys)])[:5]

        # メール抽出（mailto と テキストから）
        emails = []
        emails += [re.sub(r"^mailto:", "", l) for l in links if l.lower().startswith("mailto:")]
        raw = soup.get_text(" ", strip=True)
        raw = raw.replace("[at]", "@").replace("(at)", "@").replace(" at ", "@").replace("＠", "@")
        raw = raw.replace("[dot]", ".").replace("(dot)", ".").replace(" dot ", ".")
        emails += re.findall(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", raw)
        result["emails"] = _dedupe([e.lower() for e in emails])[:10]

        context.close(); browser.close()
    return result
# ==== safe fetch wrapper (appended) ====
from urllib.parse import urlparse, urlunparse
def _to_http(u: str)->str:
    try:
        p = urlparse(u); 
        if (p.scheme or "").lower() != "https": return u
        return urlunparse(("http", p.netloc, p.path or "/", p.params, p.query, p.fragment))
    except: return u

def fetch_site_safe(url: str, screenshot_path=None):
    try:
        r = fetch_site(url, screenshot_path=screenshot_path)
        ok = str(r.get("status") or "") == "200"
        if ok: return r
    except Exception as e:
        err = str(e)
        if "ERR_CERT" not in err and "SSL" not in err:
            raise
        # SSL由来の失敗 → httpに落として再試行
    # ここに来たら http フォールバック
    try:
        url_http = _to_http(url)
        r2 = fetch_site(url_http, screenshot_path=screenshot_path)
        if str(r2.get("status") or "") == "200":
            # 元URLも知りたい場合はメモ
            r2["redirected_from_https"] = True
            return r2
        return r2
    except:
        # それでもダメならそのままraiseして上位で除外
        raise
# ==== end append ====
