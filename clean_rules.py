import re, html, urllib.parse

MULTI_TLDS = {"co.uk","com.au","co.jp","com.sg","com.mx","com.br","co.nz","com.tr","com.ar"}

def _host(url:str)->str:
    try:
        h = urllib.parse.urlparse(url).netloc.lower()
        if ":" in h: h = h.split(":")[0]
        return h.lstrip("www.")
    except:
        return ""

def normalize_domain(url:str)->str:
    h = _host(url)
    if not h: return ""
    parts = h.split(".")
    if len(parts)>=3 and (".".join(parts[-2:]) in MULTI_TLDS or (parts[-2] in {"co","com","org","gov","edu","net"} and len(parts[-1])==2)):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts)>=2 else h

def country_from_domain(url:str, default:str="USA")->str:
    h = _host(url)
    if   h.endswith(".ca"): return "Canada"
    elif h.endswith(".uk"): return "UK"
    elif h.endswith(".au"): return "Australia"
    elif h.endswith(".jp"): return "Japan"
    return default or "USA"

_SEP_TAIL = re.compile(r"\s*(?:\|\s*[^|]{2,}|[–—-]\s+[^–—-]{2,}|[:：]\s+[^:：]{2,})\s*$", re.U)
def _strip_seo_tail(s:str)->str:
    # 末尾の「|…」「 – …」「 : …」を段階的に削る（店名が短くなり過ぎない範囲）
    prev = None
    while s and s!=prev:
        prev = s
        s = _SEP_TAIL.sub("", s).strip()
    return s

def normalize_name(name:str)->str:
    s = html.unescape((name or "").strip())
    s = s.replace("\\'", "'").replace("&#39;", "'")
    s = _strip_seo_tail(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def instagram_profile_only(url:str)->str:
    if not url: return ""
    u = url.split("?")[0]
    if re.match(r"^https?://(?:www\.)?instagram\.com/[^/?#]+/?$", u, re.I):
        return u
    return ""  # 投稿やリールは捨てる

_PLACEHOLDER_DOMAINS = {"example.com","yourdomain.com","website.com","email.com"}
def is_valid_email(em:str)->str:
    if not em: return ""
    s = em.strip().lower()
    if "@2x" in s or "@3x" in s: return ""                # 画像の命名に混入
    if re.search(r"\.(png|jpe?g|svg|webp)(?:\?|$)", s):   # 画像拡張子
        return ""
    if s in {"email@website.com","info@example.com","test@test.com"}:
        return ""
    # プレースホルダーTLD/ドメイン
    if any(s.endswith("@"+d) for d in _PLACEHOLDER_DOMAINS):
        return ""
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", s, re.I):
        return ""
    return s

def dedup_rows(rows:list)->list:
    seen = set()
    out = []
    for r in rows:
        try:
            home = (r[2] or "").strip()
        except Exception:
            out.append(r); continue
        key = normalize_domain(home) or home
        if key in seen: 
            continue
        seen.add(key)
        out.append(r)
    return out

def fix_row(name, country, home, insta, email, form_url):
    name = normalize_name(name)
    insta = instagram_profile_only(insta)
    email = is_valid_email(email)
    country = country_from_domain(home, country or "USA")
    return [name, country, home, insta, email, form_url]