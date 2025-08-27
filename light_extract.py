import re, io, os, json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlsplit, urlunsplit
from pdfminer.high_level import extract_text as pdf_extract_text
from matcha_finder.domain_filters import BLOCK_DOMAINS

HDRS = {"User-Agent": "Mozilla/5.0 (compatible; MatchaFinder/1.0)"}
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10"))


MATCHA_WORDS = re.compile(r'(matcha|抹茶|green\s*tea\s*latte|ceremonial\s*matcha|iced\s*matcha|dirty\s*matcha)', re.I)
CAFE_HINTS   = re.compile(r'\b(cafe|coffee|tea|teahouse|bakery|boba|bubble\s*tea)\b', re.I)
ZIP_RE       = re.compile(r'\b\d{5}(?:-\d{4})?\b')
PHONE_RE     = re.compile(r'(?:\+1[\s\-.]?)?(?:\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4})\b')

def canon_root(u: str) -> str:
    try:
        s = urlsplit(u)
        scheme = "https"
        host = (s.netloc or "").lower()
        if host.startswith("www."): host = host[4:]
        return urlunsplit((scheme, host, "/", "", ""))
    except Exception:
        return u

def canon_url(u: str) -> str:
    if not u: return ""
    try:
        s = urlsplit(u)
        scheme = "https" if s.scheme in ("http","https","") else s.scheme
        host = (s.netloc or "").lower()
        if host.startswith("www."): host = host[4:]
        path = s.path or "/"
        if not path.endswith("/"): path += "/"
        return urlunsplit((scheme, host, path, "", ""))
    except Exception:
        return u

def is_blocked(u: str) -> bool:
    try:
        host = urlsplit(u).netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        return any(host==d or host.endswith("."+d) for d in BLOCK_DOMAINS)
    except Exception:
        return True

def is_media_or_platform(u: str, html: str=None) -> bool:
    # 互換: pipeline は (url, html) で呼ぶ。判定は URL 基準で十分
    try:
        return is_blocked(u)
    except Exception:
        return True

def normalize_candidate_url(u: str) -> str:
    if not u: return ""
    try:
        if u.startswith("mailto:"): return ""
        if is_blocked(u): return ""
        s = urlsplit(u)
        if s.scheme not in ("http","https"): return ""
        host = (s.netloc or "").lower()
        if host.startswith("www."): host = host[4:]
        labels = host.split(".")
        if len(labels)>=3 and labels[0] in ("order","orders","store","shop","locations","menu"):
            host = ".".join(labels[1:])
        return urlunsplit(("https", host, "/", "", ""))
    except Exception:
        return ""

def http_get(u: str, timeout=TIMEOUT):
    try:
        r = requests.get(u, headers=HDRS, timeout=timeout, allow_redirects=True)
        if r.status_code >= 400: return None
        return r
    except requests.RequestException:
        return None

def html_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script","style","noscript"]): t.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())

def find_menu_links(html: str, base: str, limit=4):
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]; text = (a.get_text() or "")
        if ("menu" in href.lower()) or re.search(r"menu|drink|beverage|tea|抹茶|メニュー|ドリンク", text, re.I):
            links.append(urljoin(base, href))
    for p in ["/menu","/menus","/our-menu","/drinks","/beverage","/tea","/drink-menu"]:
        links.append(urljoin(base, p))
    out, seen = [], set()
    for u in links:
        if u not in seen: seen.add(u); out.append(u)
    return out[:limit]

def one_pdf_text_from(html: str, base: str):
    soup = BeautifulSoup(html, "lxml")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            pdf_url = urljoin(base, href)
            r = http_get(pdf_url)
            if r and r.content:
                try: return pdf_extract_text(io.BytesIO(r.content))[:50000]
                except Exception: return ""
    return ""

# ---- email deobfuscation helpers ----
def _decode_cfemail(enc: str) -> str:
    try:
        r = bytes.fromhex(enc)
        key = r[0]
        dec = bytes([b ^ key for b in r[1:]]).decode("utf-8", "ignore")
        return dec
    except Exception:
        return ""

def _deobf_text_emails(txt: str):
    # name [at] example [dot] com / name(at)example(dot)com 等
    t = re.sub(r'\s*\[\s*at\s*\]\s*|\s*\(\s*at\s*\)\s*|\s+at\s+', '@', txt, flags=re.I)
    t = re.sub(r'\s*\[\s*dot\s*\]\s*|\s*\(\s*dot\s*\)\s*|\s+dot\s+', '.', t, flags=re.I)
    return re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", t, re.I)

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

def find_contact_form_urls(base: str, html: str, limit=5):
    soup = BeautifulSoup(html, "lxml")
    cand = set()
    # 明示フォーム
    if soup.find("form"): cand.add(base)
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(k in href for k in ("/contact","/contact-us","/contactus","/connect","/get-in-touch","/inquiry")):
            cand.add(urljoin(base, a["href"]))
        txt = (a.get_text() or "").lower()
        if any(k in txt for k in ("contact","inquiry","お問い合わせ","問合せ")):
            cand.add(urljoin(base, a["href"]))
    # お決まりの直接パスも加える
    for p in ("/contact","/contact-us","/contactus","/connect","/get-in-touch","/support","/about"):
        cand.add(urljoin(base, p))
    out = []
    seen = set()
    for u in cand:
        if u not in seen: seen.add(u); out.append(u)
        if len(out)>=limit: break
    return out

def extract_contacts(base: str, html: str):
    """Instagram / emails / contact form URL をできるだけ拾う"""
    ig = ""
    emails = set()
    form = ""

    soup = BeautifulSoup(html, "lxml")

    # 1) anchors
    for a in soup.find_all("a", href=True):
        href = a["href"]
        low = href.lower()
        if "instagram.com" in low and not ig:
            ig = canon_url(urljoin(base, href))
        if low.startswith("mailto:"):
            emails.add(low.replace("mailto:", "").strip())
    # 2) cfemail (Cloudflare)
    for el in soup.select("a.__cf_email__"):
        enc = el.get("data-cfemail")
        if enc:
            dec = _decode_cfemail(enc)
            if dec: emails.add(dec)
    # 3) JSON-LD sameAs / contactPoint
    for tag in soup.find_all("script", type=lambda x: x and "ld+json" in x):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        def walk(obj):
            if isinstance(obj, dict):
                same = obj.get("sameAs")
                if isinstance(same, (list, tuple)):
                    for u in same:
                        if isinstance(u, str) and "instagram.com" in u and not ig:
                            ig = canon_url(u)
                cp = obj.get("contactPoint") or obj.get("ContactPoint")
                if isinstance(cp, (list, tuple)):
                    for c in cp:
                        if isinstance(c, dict) and "email" in c and c["email"]:
                            emails.add(c["email"])
                if "email" in obj and isinstance(obj["email"], str):
                    emails.add(obj["email"])
                for v in obj.values(): walk(v)
            elif isinstance(obj, (list, tuple)):
                for v in obj: walk(v)
        try:
            walk(data)
        except Exception:
            pass

    # 4) 追加ページ探索 (必要ならば)
    if ig or emails:
        return (ig, sorted(emails), form)

    tried = set()

    def scan_more(limit: int = 2):
        nonlocal ig, form
        urls = find_contact_form_urls(base, html, limit=limit)
        new_urls = [u for u in urls if u not in tried]
        for url in new_urls[:2]:
            tried.add(url)
            r = http_get(url)
            if not r or not r.text:
                continue
            if "<form" in r.text.lower() and not form:
                form = url
            for e in EMAIL_RE.findall(r.text):
                emails.add(e)
            for e in _deobf_text_emails(r.text):
                emails.add(e)
            s2 = BeautifulSoup(r.text, "lxml")
            for el in s2.select("a.__cf_email__"):
                enc = el.get("data-cfemail")
                if enc:
                    dec = _decode_cfemail(enc)
                    if dec:
                        emails.add(dec)
            if not ig:
                for a in s2.find_all("a", href=True):
                    href = a["href"]
                    if "instagram.com" in href.lower():
                        ig = canon_url(urljoin(url, href))
                        break
            if ig or emails:
                return
        if not ig and not emails and len(urls) > len(tried):
            scan_more(limit + 2)

    scan_more(2)
    return (ig, sorted(emails), form)

def is_chain_like(base: str, html: str) -> bool:
    loc = urljoin(base, "/locations")
    rr = http_get(loc)
    if rr and rr.text:
        soup = BeautifulSoup(rr.text, "lxml")
        cards = soup.select('[class*="location"], [class*="store"], .card, li')
        if len(cards) >= 6:
            return True
    addr_hits = len(re.findall(r"\d{1,5}\s+\w+\s+\w+|[A-Za-z]+,\s*[A-Z]{2}\s*\d{5}", html))
    return addr_hits >= 8

def is_us_cafe_site(base: str, html: str) -> bool:
    txt = html_text(html)
    if not CAFE_HINTS.search(txt): return False
    if re.search(r"\b(cart|checkout|collections?/|product(s)?/|woocommerce|shopify)\b", txt, re.I):
        if not (ZIP_RE.search(txt) or PHONE_RE.search(txt)):
            return False
    if not (ZIP_RE.search(txt) or PHONE_RE.search(txt)): return False
    if is_chain_like(base, html): return False
    if is_media_or_platform(base): return False
    return True

def _domain_to_name(base: str) -> str:
    try:
        host = urlsplit(base).netloc.lower()
        if host.startswith("www."): host = host[4:]
        parts = host.split(".")
        core = parts[-2] if len(parts)>=2 else parts[0]
        core = core.replace("-", " ").replace("_", " ").strip()
        core = re.sub(r"\s+", " ", core)
        return core.title()
    except Exception:
        return base

def _clean_brand_text(t: str) -> str:
    if not t: return ""
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s*[-–—|:·•]\s*(menu|order|online|home|locations?|shop|store|official\s*site|site)\b.*$", "", t, flags=re.I)
    t = re.sub(r"^(welcome\s+to\s+|official\s+site\s*:\s*)", "", t, flags=re.I)
    return t.strip()

def guess_brand(base: str, html: str, snippet_title: str="") -> str:
    cands = []
    if snippet_title: cands.append(_clean_brand_text(snippet_title))
    try:
        soup = BeautifulSoup(html, "lxml")
        if soup.title and soup.title.string: cands.append(_clean_brand_text(soup.title.string))
        for sel in [('meta',{'property':'og:site_name'}),('meta',{'property':'og:title'}),('meta',{'name':'twitter:title'})]:
            m = soup.find(*sel)
            if m and (m.get('content') or m.get('value')):
                cands.append(_clean_brand_text(m.get('content') or m.get('value')))
        for tag in soup.find_all(['h1','h2']):
            txt = _clean_brand_text(tag.get_text(" ", strip=True))
            if txt: cands.append(txt)
    except Exception:
        pass
    cands.append(_domain_to_name(base))
    def score(t: str) -> int:
        if not t: return -999
        sc=0
        if re.search(r"\b(cafe|coffee|tea|teahouse|bakery|boba)\b", t, re.I): sc+=3
        if re.search(r"matcha|抹茶", t, re.I): sc+=2
        if len(t)<=2 or len(t)>60: sc-=5
        if re.search(r"\b(menu|order|online|locations?)\b", t, re.I): sc-=3
        return sc
    uniq=[]; seen=set()
    for x in cands:
        x=_clean_brand_text(x)
        if not x: continue
        k=x.lower()
        if k in seen: continue
        seen.add(k); uniq.append(x)
    if not uniq: return _domain_to_name(base)
    return max(uniq, key=score)
