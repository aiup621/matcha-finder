# rules.py
import re
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup

def normalize_url(u: str) -> str:
    if not u: return ""
    u = u.strip()
    try:
        p = urlparse(u if "://" in u else f"https://{u}")
        scheme = "https" if p.scheme in ("http","https") else (p.scheme or "https")
        netloc = (p.netloc or "").lower()
        if netloc.startswith("www."): netloc = netloc[4:]
        path = (p.path or "/").rstrip("/") or "/"
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return u.strip()

def is_independent(html):
    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text(" ", strip=True)
    hits = re.findall(r"\b[A-Z][a-z]+,\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|DC)\b", text)
    return len(set(hits)) <= 5# ==== appended helpers ====
from urllib.parse import urlparse, urlunparse
import re as _re

def homepage_of(u: str) -> str:
    try:
        p = urlparse(u if "://" in u else f"https://{u}")
        scheme = p.scheme if p.scheme in ("http","https") else "https"
        netloc = (p.netloc or "").lower()
        if netloc.startswith("www."): netloc = netloc[4:]
        return urlunparse((scheme, netloc, "/", "", "", ""))
    except Exception:
        return u

def extract_brand_name(html: str, url: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    og = soup.select_one("meta[property='og:site_name'][content]")
    if og and og.get("content","").strip():
        name = og["content"].strip()
    else:
        title = (soup.title.string or "").strip() if soup.title else ""
        for sep in ["|","-","—","·","•"]:
            if sep in title:
                title = title.split(sep)[0].strip()
                break
        name = title
    noise = ["Menu","MENU","Menus","Locations","Location","Stores","Store","Cafe Menu","Café Menu"]
    for w in noise:
        name = name.replace(w, "").strip()
    name = _re.sub(r"\s{2,}", " ", name)
    if not name or len(name) < 2:
        dom = urlparse(url).netloc
        if dom.startswith("www."): dom = dom[4:]
        name = dom.split(".")[0].replace("-", " ").title()
    return name
# ==== end helpers ====
# ==== accuracy & quality helpers (appended) ====
from urllib.parse import urlparse, urlunparse
from bs4 import BeautifulSoup
import re

DELIVERY_BLACKLIST = {
  "doordash.com","ubereats.com","grubhub.com","postmates.com","toasttab.com",
  "square.site","order.online","opentable.com","resy.com","yelp.com","tripadvisor.com",
  "zomato.com","seamless.com","clover.com","foodbooking.com","ezcater.com"
}

def domain(host: str)->str:
    h = (host or "").lower()
    return h[4:] if h.startswith("www.") else h

def is_delivery_or_portal(u: str)->bool:
    try:
        d = domain(urlparse(u).netloc)
        return any(d.endswith(b) for b in DELIVERY_BLACKLIST)
    except: return False

def canonical_url(html: str, fallback: str)->str:
    try:
        s = BeautifulSoup(html or "", "lxml")
        link = s.select_one("link[rel='canonical'][href]")
        if not link: return fallback
        href = link["href"].strip()
        p = urlparse(href if "://" in href else f"https://{href}")
        host = domain(p.netloc)
        if not host: return fallback
        if is_delivery_or_portal(href): return fallback
        return urlunparse((p.scheme if p.scheme in ("http","https") else "https", host, p.path or "/", "", "", ""))
    except: return fallback

def instagram_handle(u: str)->str:
    try:
        p = urlparse(u); h = domain(p.netloc)
        if "instagram.com" not in h: return ""
        seg = (p.path or "").strip("/").split("/")
        if not seg or seg[0] in ("p","reel","reels","explore","stories","s"): return ""
        return seg[0].lower()
    except: return ""

def is_independent_strict(html: str)->bool:
    """Locations/Store一覧の痕跡から5店舗以下と推定（チェーンはFalse）"""
    try:
        s = BeautifulSoup(html or "", "lxml")
        # locations系リンクの近傍にある店舗カード/リストを概算カウント
        text = s.get_text(" ", strip=True)
        # 明示的除外ワード
        if re.search(r"\bfranchise\b|\bfind a store\b", text, re.I):
            return False
        # カード的な要素を概算
        cards = s.select("a[href*='location'], a[href*='locations'], a[href*='stores'], .location, .store")
        if len(cards) > 10:  # 露骨に多い
            return False
        # 文章内ヒント "Locations (n)"
        m = re.search(r"Locations?\s*\(?\s*(\d{1,3})\s*\)?", text, re.I)
        if m and int(m.group(1)) >= 6:
            return False
        return True
    except:
        return True
# ==== end append ====
# ==== freshness helpers (appended) ====
import os, re, io, json, requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

def _to_utc(dt):
    try:
        return dt.astimezone(timezone.utc)
    except:
        return dt.replace(tzinfo=timezone.utc)

def _parse_date_str(s: str):
    s = (s or "").strip()
    if not s: return None
    # ISO 8601 / RFC 3339 っぽいもの
    for pat in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(s, pat)
            return _to_utc(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
        except:
            pass
    # "Mon DD, YYYY" 形式などは簡易対応
    try:
        dt = datetime.strptime(s, "%b %d, %Y")
        return _to_utc(dt.replace(tzinfo=timezone.utc))
    except:
        return None

def _dates_from_meta(html: str):
    s = BeautifulSoup(html or "", "lxml")
    candidates = []
    # よくあるメタ
    keys = [
        ("meta", {"property":"article:modified_time"}),
        ("meta", {"property":"og:updated_time"}),
        ("meta", {"name":"last-modified"}),
        ("meta", {"itemprop":"dateModified"}),
        ("meta", {"name":"modified"}),
        ("meta", {"name":"updated"}),
    ]
    for tag, attrs in keys:
        el = s.select_one(f"{tag}[{','.join(f'{k}={json.dumps(v)}' for k,v in attrs.items())}]")
        if el and el.get("content"):
            dt = _parse_date_str(el["content"])
            if dt: candidates.append(dt)
    # JSON-LD の dateModified / datePublished
    for sc in s.select("script[type='application/ld+json']"):
        try:
            data = json.loads(sc.string or "{}")
            if isinstance(data, dict):
                for k in ("dateModified","datePublished"):
                    dt = _parse_date_str(str(data.get(k) or ""))
                    if dt: candidates.append(dt)
            elif isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict): continue
                    for k in ("dateModified","datePublished"):
                        dt = _parse_date_str(str(item.get(k) or ""))
                        if dt: candidates.append(dt)
        except:
            pass
    return candidates

def _last_modified_http(url: str):
    try:
        r = requests.head(url, timeout=15, allow_redirects=True,
                          headers={"User-Agent":"Mozilla/5.0"})
        lm = r.headers.get("Last-Modified")
        if lm:
            dt = parsedate_to_datetime(lm)
            return _to_utc(dt)
        # HEADで出ない場合はGET
        r = requests.get(url, timeout=20, allow_redirects=True,
                         headers={"User-Agent":"Mozilla/5.0"}, stream=True)
        lm = r.headers.get("Last-Modified")
        if lm:
            dt = parsedate_to_datetime(lm)
            return _to_utc(dt)
    except:
        return None
    return None

def _dates_from_instagram_html(html: str):
    # <time datetime="2025-06-01T...Z"> や "taken_at":"2025-06-01T..." を拾う
    out = []
    try:
        for m in re.finditer(r'datetime="([^"]+)"', html or "", re.I):
            dt = _parse_date_str(m.group(1))
            if dt: out.append(dt)
        for m in re.finditer(r'"taken_at"[:\s]*"([^"]+)"', html or "", re.I):
            dt = _parse_date_str(m.group(1))
            if dt: out.append(dt)
        # UNIX秒（"taken_at": 1717228800）の簡易対応
        for m in re.finditer(r'"taken_at"[:\s]*(\d{10})', html or "", re.I):
            try:
                dt = datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc)
                out.append(dt)
            except:
                pass
    except:
        pass
    return out

def is_recent_enough(home_url: str, homepage_html: str,
                     insta_html: str = "", menu_urls=None,
                     days: int = None) -> bool:
    """直近 days 日以内に“更新/投稿”の痕跡があれば True"""
    horizon = int(os.getenv("FRESH_WITHIN_DAYS", "730")) if days is None else int(days)
    now = datetime.now(timezone.utc)
    # 1) HTTPヘッダ
    dt = _last_modified_http(home_url)
    if dt and (now - dt) <= timedelta(days=horizon):
        return True
    # 2) HTMLメタ/JSON-LD
    for d in _dates_from_meta(homepage_html or ""):
        if (now - d) <= timedelta(days=horizon):
            return True
    # 3) メニューURL群の Last-Modified も見てみる
    for mu in (menu_urls or []):
        dtm = _last_modified_http(mu)
        if dtm and (now - dtm) <= timedelta(days=horizon):
            return True
    # 4) Instagram（ページHTMLが渡されていれば）
    for d in _dates_from_instagram_html(insta_html or ""):
        if (now - d) <= timedelta(days=horizon):
            return True
    return False
# ==== end freshness helpers ====
# === brand name extractor v2 ===
import re as _re
from urllib.parse import urlparse as _urlparse

_GENERIC_TOKENS = {"home","menu","welcome","locations","location","store","stores","shop","contact","about","cafe menu","café menu","coffee menu"}

def _brand_from_domain(u):
    d = _urlparse(u).netloc.lower()
    if d.startswith("www."): d = d[4:]
    tok = d.split(".")[0].replace("-", " ")
    return tok.title()

def extract_brand_name_v2(html: str, url: str) -> str:
    import logging
    from bs4 import BeautifulSoup
    log = logging.getLogger("pipeline")
    soup = BeautifulSoup(html or "", "lxml")

    # 1) 強いシグナル（site_name等）
    for sel in ["meta[property='og:site_name'][content]",
                "meta[name='application-name'][content]",
                "meta[property='og:title'][content]",
                "meta[name='apple-mobile-web-app-title'][content]"]:
        tag = soup.select_one(sel)
        if tag and tag.get("content","").strip():
            cand = tag["content"].strip()
            if cand and cand.lower() not in _GENERIC_TOKENS:
                name = _re.sub(r"\s{2,}", " ", cand).strip()
                try: log.info("brand_v2 strong meta | url=%s | chosen=%s", url, name)
                except: pass
                return name

    # 2) <title> を分解し、汎用語を除外 → ドメインに近い／長い方を採用
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    title = _re.sub(r"\s+", " ", title)
    parts = [p.strip() for p in _re.split(r"\s*[|\-—·•:–]\s*", title) if p.strip()]
    parts = [p for p in parts if p.lower() not in _GENERIC_TOKENS]

    dom_hint = _brand_from_domain(url).lower()
    def _score(s: str):
        a = set(_re.findall(r"[a-z]+", s.lower()))
        b = set(_re.findall(r"[a-z]+", dom_hint))
        overlap = len(a & b)
        return (overlap, len(s))  # ドメイン一致度→長さ

    if parts:
        best = max(parts, key=_score)
        name = _re.sub(r"\s{2,}", " ", best).strip()
        try: log.info("brand_v2 title parts | url=%s | parts=%s | chosen=%s", url, parts, name)
        except: pass
        return name

    # 3) 最後の手段：ドメインから生成
    name = _brand_from_domain(url)
    try: log.info("brand_v2 fallback domain | url=%s | chosen=%s", url, name)
    except: pass
    return name
# === end brand name extractor v2 ===
# === brand name extractor v2 ===
import re as _re
from urllib.parse import urlparse as _urlparse

_GENERIC_TOKENS = {"home","menu","welcome","locations","location","store","stores","shop","contact","about","cafe menu","café menu","coffee menu","news"}
# 日本語の汎用語も除外対象に
_GENERIC_TOKENS.update({"ホーム","メニュー","トップ","店舗","お問い合わせ","問合せ","アクセス","ニュース"})

def _brand_from_domain(u):
    d = _urlparse(u).netloc.lower()
    if d.startswith("www."): d = d[4:]
    tok = d.split(".")[0].replace("-", " ")
    return tok.title()

def extract_brand_name_v2(html: str, url: str) -> str:
    import logging
    from bs4 import BeautifulSoup
    log = logging.getLogger("pipeline")
    soup = BeautifulSoup(html or "", "lxml")

    # 1) 強いシグナル（site_name 等）
    for sel in [
        "meta[property='og:site_name'][content]",
        "meta[name='application-name'][content]",
        "meta[property='og:title'][content]",
        "meta[name='apple-mobile-web-app-title'][content]",
    ]:
        tag = soup.select_one(sel)
        if tag and tag.get("content","").strip():
            cand = tag["content"].strip()
            if cand and cand.lower() not in _GENERIC_TOKENS and cand not in _GENERIC_TOKENS:
                name = _re.sub(r"\s{2,}", " ", cand).strip()
                try: log.info("brand_v2 strong meta | url=%s | chosen=%s", url, name)
                except: pass
                return name

    # 2) <title> を分解し汎用語を除外 → ドメイン類似度→長さの順で採用
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    title = _re.sub(r"\s+", " ", title)
    parts = [p.strip() for p in _re.split(r"\s*[|\-—·•:–]\s*", title) if p.strip()]
    parts = [p for p in parts if p.lower() not in _GENERIC_TOKENS and p not in _GENERIC_TOKENS]

    dom_hint = _brand_from_domain(url).lower()
    def _score(s: str):
        a = set(_re.findall(r"[a-z]+", s.lower()))
        b = set(_re.findall(r"[a-z]+", dom_hint))
        overlap = len(a & b)
        return (overlap, len(s))  # ドメイン一致度→長さ

    if parts:
        best = max(parts, key=_score)
        name = _re.sub(r"\s{2,}", " ", best).strip()
        try: log.info("brand_v2 title parts | url=%s | parts=%s | chosen=%s", url, parts, name)
        except: pass
        return name

    # 3) 最後の手段：ドメインから生成
    name = _brand_from_domain(url)
    try: log.info("brand_v2 fallback domain | url=%s | chosen=%s", url, name)
    except: pass
    return name
# === end brand name extractor v2 ===
