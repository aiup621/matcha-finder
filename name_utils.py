import re, json, os
from urllib.parse import urlparse, urljoin
from functools import lru_cache
from bs4 import BeautifulSoup
import requests

REQ_TIMEOUT = float(os.getenv("REQUESTS_TIMEOUT", "15"))

# スローガン/汎用語を多言語で（必要なら .env の NAME_BAD_WORDS で追記可能）
BAD_WORDS = tuple((os.getenv("NAME_BAD_WORDS","privacy,policy,terms,menu,home,shop,store,locations,location,login,signup,about,news,blog,faq,contact,access,online shop,official,公式,オフィシャル,店舗情報,メニュー,プライバシー,利用規約,会社概要")).split(','))
SEP = r'\s*(?:\||—|–|-|•|·|»|«|:|｜|：)\s*'
GENERIC_PAGES = ('/privacy', '/policy', '/terms', '/login', '/signin', '/account')

COMPOUND_TLDS = ('co.jp','com.au','co.uk','com.sg','com.hk','com.tw','com.br','com.mx')

UA = {"User-Agent": "Mozilla/5.0 (name-extractor)"}  # 素朴なUA

def _norm(s): return re.sub(r'\s+', ' ', s or '').strip()

def _too_generic(s):
    t = (s or '').lower().strip()
    if not t: return True
    if any(w.strip() and w.strip() in t for w in BAD_WORDS): return True
    if t.count(',') >= 2: return True
    if len(t) > 70: return True
    return False

def _strip_tagline(s):
    s = _norm(s)
    # 「Brand | Official Site」などの仕切りで手前の“らしい方”を取る
    parts = re.split(SEP, s)
    best = None
    for p in parts:
        p = p.strip()
        if not p: continue
        # 「Brand 公式サイト」「Coffee Roasters」など末尾の凡用語を削る
        p = re.sub(r'\b(official site|official|online store|coffee roasters?|roasters?|cafe|coffee|tea|store|shop|inc\.?|ltd\.?|llc)\b\.?$', '', p, flags=re.I).strip()
        p = re.sub(r'(公式サイト|オフィシャルサイト)$', '', p).strip()
        if not _too_generic(p):
            best = p
            break
    if best: return best
    return parts[0].strip() if parts else s

def _smart_title(s):
    s = _norm(s)
    # Title Case しつつ 2〜4文字の完全大文字(例: NYC, USA)は維持
    out = []
    for w in re.split(r'[\s\-_/\.]+', s):
        if 2 <= len(w) <= 4 and w.isupper():
            out.append(w)
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return ' '.join(out).strip()

def _domain_core(host):
    host = host.lower()
    host = re.sub(r'^www\d?\.', '', host)
    labels = host.split('.')
    if len(labels) >= 3 and '.'.join(labels[-2:]) in COMPOUND_TLDS:
        core = labels[-3]
    else:
        core = labels[-2] if len(labels) >= 2 else labels[0]
    core = re.sub(r'[^a-z0-9\-]+', '', core)
    core = re.sub(r'-(?=[a-z0-9])', ' ', core)
    # 「matcha」「cafe」等が末尾にくっついてたら間にスペース
    core = re.sub(r'([a-z])(?=(cafe|coffee|coffeebar|matcha|tea|roasters?|roastery|bakery|house|lab|labs|studio|store|shop|farms?)\b)', r'\1 ', core)
    return _smart_title(core)

def _looks_brandlike(s):
    t = _norm(s)
    if not t or _too_generic(t): return False
    if sum(ch.isalpha() for ch in t) < 3: return False
    if len(t.split()) > 6: return False
    return True

def _from_jsonld(html):
    out = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for s in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                data = json.loads(s.string or "")
            except Exception:
                continue
            def collect(obj):
                if isinstance(obj, dict):
                    n = obj.get("name") or obj.get("alternateName") \
                        or (obj.get("brand") or {}).get("name")
                    if n: out.append(_norm(n))
                    for k in ("@graph","itemListElement","mainEntityOfPage","author","publisher","creator"):
                        if k in obj: collect(obj[k])
                elif isinstance(obj, list):
                    for x in obj: collect(x)
            collect(data)
    except Exception:
        pass
    return out

def _from_meta(html):
    soup = BeautifulSoup(html, "lxml")
    cand = []
    for prop in ("og:site_name","og:title","twitter:title"):
        m = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
        if m and m.get("content"): cand.append(_norm(m["content"]))
    if soup.title and soup.title.string:
        cand.append(_norm(soup.title.string))
    # headerロゴの alt/aria-label も拾う
    for sel in ('header img[alt]', 'img[alt*=logo i]', 'a[aria-label]', 'a[class*=logo i]'):
        el = soup.select_one(sel)
        if el:
            val = el.get("alt") or el.get("aria-label")
            if val: cand.append(_norm(val))
    return cand

def _to_home(url, html=None):
    """/menu 等を受け取ってもホームへ寄せる（canonical 優先）"""
    try:
        u = urlparse(url)
        if html:
            soup = BeautifulSoup(html, "lxml")
            can = soup.find("link", rel=lambda x: x and "canonical" in x)
            if can and can.get("href"):
                c = can["href"].strip()
                if c.startswith("http"): return c
        return f"{u.scheme}://{u.netloc}/"
    except Exception:
        return url

def _instagram_like(url):
    try:
        u = urlparse(url)
        if u.netloc.endswith("instagram.com") and u.path.strip("/"):
            h = u.path.strip("/").split("/")[0]
            h = re.sub(r'[_\.\-]+', ' ', h)
            return _smart_title(h)
        if u.netloc in ("linktr.ee", "lit.link") and u.path.strip("/"):
            h = u.path.strip("/").split("/")[0]
            h = re.sub(r'[_\.\-]+', ' ', h)
            return _smart_title(h)
    except Exception:
        pass
    return None

@lru_cache(maxsize=512)
def _fetch(url):
    r = requests.get(url, timeout=REQ_TIMEOUT, headers=UA, allow_redirects=True)
    r.raise_for_status()
    return r.text

def fetch_brand_from_home(home):
    inst = _instagram_like(home)
    if inst: return inst
    try:
        html = _fetch(home)
    except Exception:
        # ルートじゃなければルートを試す
        try:
            html = _fetch(_to_home(home))
        except Exception:
            return None
    # canonical でさらに寄せる
    home2 = _to_home(home, html)
    if home2 != home:
        try:
            html = _fetch(home2)
        except Exception:
            pass

    for raw in (_from_jsonld(html) + _from_meta(html)):
        x = _strip_tagline(raw)
        if _looks_brandlike(x):
            return _smart_title(x)
    return None

def fix_brand_name(name, home):
    # 1) 既存名を掃除
    name = _strip_tagline(name or "")
    if _looks_brandlike(name):
        return _smart_title(name)

    # 2) ホームから推定
    brand = None
    if home:
        try:
            brand = fetch_brand_from_home(home)
        except Exception:
            brand = None
    if brand and _looks_brandlike(brand):
        return _smart_title(brand)

    # 3) ドメインから安全フォールバック
    netloc = ""
    try: netloc = urlparse(home).netloc
    except Exception: pass
    if netloc:
        return _domain_core(netloc)

    return (name or "").strip()