from __future__ import annotations
import re, json, html, urllib.parse
from typing import Iterable, List, Set, Tuple
from bs4 import BeautifulSoup

MAILTO_RE = re.compile(r'mailto:([^"?\s>#]+)', re.I)
PLAIN_RE = re.compile(r'\b[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{1,253}\.[A-Za-z]{2,63}\b')

LABEL = r'[A-Za-z0-9\-]{1,63}'
DOT_PAT = r'(?:\s*(?:\.|\(?.?dot\.?\)?|\[?dot\]?|\s+dot\s+)\s*)'
AT_PAT  = r'(?:\s*(?:@|\(?.?at\.?\)?|\[?at\]?|\s+at\s+)\s*)'
OBF_RE = re.compile(
    rf'([A-Za-z0-9._%+\-]{{1,64}}){AT_PAT}({LABEL}(?:{DOT_PAT}{LABEL})+)',
    re.I
)

EXTRA_CONTACT_PATHS = [
    'contact', 'contact-us', 'about', 'about-us', 'connect', 'visit',
    'info', 'booking', 'reservations', 'wholesale', 'order', 'orders', 'purchase', 'purchasing'
]

def decode_cfemail(hexstr: str) -> str:
    try:
        key = int(hexstr[:2], 16)
        chars = [chr(int(hexstr[i:i+2], 16) ^ key) for i in range(2, len(hexstr), 2)]
        return ''.join(chars)
    except Exception:
        return ''

def _add(emails: Set[str], candidate: str):
    try:
        c = candidate.strip().strip('.,;:()[]{}<>').replace('\u200b', '')
        c = html.unescape(c)
        if c and '@' in c and len(c) <= 320:
            emails.add(c)
    except Exception:
        pass

def extract_emails_from_html(base_url: str, html_text: str) -> Set[str]:
    emails: Set[str] = set()
    soup = BeautifulSoup(html_text, 'html.parser')

    for a in soup.find_all('a', href=True):
        m = MAILTO_RE.search(a['href'])
        if m:
            _add(emails, urllib.parse.unquote(m.group(1)))

    for node in soup.select('span.__cf_email__'):
        h = node.get('data-cfemail')
        if h:
            addr = decode_cfemail(h)
            if addr:
                _add(emails, addr)

    for tag in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        try:
            data = json.loads(tag.string or 'null')
            objs = data if isinstance(data, list) else [data]
            for o in objs:
                if isinstance(o, dict) and 'email' in o:
                    e = o['email']
                    if isinstance(e, str):
                        _add(emails, e)
        except Exception:
            pass

    for el in soup.find_all(attrs={'itemprop': 'email'}):
        _add(emails, el.get_text(' ', strip=True))

    for m in PLAIN_RE.finditer(html_text):
        _add(emails, m.group(0))

    for m in OBF_RE.finditer(html_text.replace('[at]', ' at ').replace('[dot]', ' dot ')):
        local = m.group(1)
        domain_obf = m.group(2)
        domain = re.sub(DOT_PAT, '.', domain_obf, flags=re.I)
        _add(emails, f'{local}@{domain}')

    return emails

def crawl_candidate_paths(base_url: str, fetch_html, max_pages: int = 5) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    seen = set()
    for p in EXTRA_CONTACT_PATHS:
        if len(out) >= max_pages:
            break
        u = urllib.parse.urljoin(base_url, '/' + p.strip('/') + '/')
        if u in seen:
            continue
        seen.add(u)
        try:
            html_text = fetch_html(u)
            if html_text:
                out.append((u, html_text))
        except Exception:
            continue
    return out

def score_email(addr: str) -> int:
    a = addr.lower()
    score = 0
    if any(k in a for k in ['wholesale','order','orders','purchas','retail','sales','buy']):
        score += 5
    if any(k in a for k in ['info','contact','hello','team','office']):
        score += 2
    if any(k in a for k in ['careers','job','press','media','support','help','privacy','admin','noreply','no-reply','donotreply']):
        score -= 2
    return score

def pick_best(emails: Iterable[str]) -> str | None:
    ranked = sorted(set(emails), key=lambda e: (score_email(e), -len(e)), reverse=True)
    return ranked[0] if ranked else None

