import os, re, html, json
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import requests

# ------- チューニング可能なパラメータ（環境変数で上書き可） -------
REQ_TIMEOUT = float(os.getenv("REQUESTS_TIMEOUT", "12"))  # 1リクエストの上限秒
MAX_BYTES   = int(os.getenv("EMAIL_MAX_BYTES", "300000")) # 読み込む最大バイト（重いページ防止）
CAND_CAP    = int(os.getenv("EMAIL_CONTACT_CAP", "3"))    # 追う連絡先ページの最大件数
UA = {"User-Agent": "Mozilla/5.0 (contact-email-finder/1.0)"}

# 除外（明確に問い合わせ用途でない）
EXCLUDE_RE = re.compile(r"(no-?reply|career|jobs|recruit|press|media|reservation|booking|order|orders|privacy|policy|terms)", re.I)

# 優先ワード（ユーザー部分やページ文脈に現れると加点）
P1_RE = re.compile(r"(owner|founder|ceo|gm|manager|mgr|buyer)", re.I)
P2_RE = re.compile(r"(info|hello|contact|support|enquiries|inquiries|sales)", re.I)

COMPOUND_TLDS = ('co.jp','com.au','co.uk','com.sg','com.hk','com.tw','com.br','com.mx')

CONTACT_HINTS = [
    "contact","contact-us","contacts","kontakt","contacto","お問い合わせ","お問合せ","問合せ","連絡",
    "connect","support","help","get in touch","アクセス","店舗情報","会社概要"
]

EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)

def _registrable(host: str) -> str:
    host = host.lower()
    host = re.sub(r"^www\d?\.", "", host)
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in COMPOUND_TLDS:
        base = ".".join(parts[-3:])
    elif len(parts) >= 2:
        base = ".".join(parts[-2:])
    else:
        base = host
    return base

def _get(url: str) -> str:
    r = requests.get(url, timeout=REQ_TIMEOUT, headers=UA, allow_redirects=True, stream=True)
    r.raise_for_status()
    data = bytearray()
    for chunk in r.iter_content(16384):
        if not chunk: break
        data.extend(chunk)
        if len(data) >= MAX_BYTES: break
    enc = r.encoding or "utf-8"
    return data.decode(enc, errors="ignore")

def _canonical_home(url: str, html_text: str|None) -> str:
    try:
        if html_text:
            soup = BeautifulSoup(html_text, "lxml")
            can = soup.find("link", rel=lambda x: x and "canonical" in x)
            if can and can.get("href") and can["href"].startswith("http"):
                return can["href"]
        u = urlparse(url)
        return f"{u.scheme}://{u.netloc}/"
    except Exception:
        return url

def _deobfuscate_text(text: str) -> str:
    t = html.unescape(text)
    # よくある表記揺れを @ / . に戻す
    t = re.sub(r"\s*\[\s*at\s*\]|\s*\(\s*at\s*\)\s*|＠|\sat\s", "@", t, flags=re.I)
    t = re.sub(r"\s*\[\s*dot\s*\]|\s*\(\s*dot\s*\)\s*|\sdot\s", ".", t, flags=re.I)
    t = t.replace("（at）","@").replace("（dot）",".").replace("★","@").replace("☆",".")
    return t

def _cf_decode_attr(soup: BeautifulSoup) -> list[str]:
    # Cloudflare data-cfemail デコード
    res = []
    for el in soup.select("[data-cfemail]"):
        try:
            hexd = el.get("data-cfemail")
            data = bytes.fromhex(hexd)
            key = data[0]
            email = "".join(chr(b ^ key) for b in data[1:])
            if EMAIL_RE.fullmatch(email): res.append(email)
        except Exception:
            pass
    return res

def _extract_emails_from_html(html_text: str) -> list[str]:
    out = set()
    t = _deobfuscate_text(html_text)
    # mailto:
    for m in re.findall(r"mailto:([^\"'>\s]+)", t, flags=re.I):
        m = html.unescape(m.split("?")[0])
        if EMAIL_RE.fullmatch(m): out.add(m)
    # プレーンテキスト
    for m in EMAIL_RE.findall(t):
        out.add(m)
    # data-cfemail
    try:
        soup = BeautifulSoup(html_text, "lxml")
        out.update(_cf_decode_attr(soup))
    except Exception:
        pass
    return list(out)

def _find_contact_links(home_url: str, html_text: str) -> list[str]:
    soup = BeautifulSoup(html_text, "lxml")
    cands = []
    # aタグのテキストに contact 系ワード
    for a in soup.find_all("a", href=True):
        label = " ".join((a.get_text(" ") or "").strip().split())
        href = a["href"]
        if any(w.lower() in label.lower() for w in CONTACT_HINTS):
            try:
                u = urljoin(home_url, href)
                cands.append(u)
            except Exception:
                pass
    # 既知の定番パスも試す
    base = _canonical_home(home_url, html_text)
    for p in ("/contact", "/contact-us", "/contacts", "/support", "/help", "/about", "/company", "/お問い合わせ", "/contacto", "/kontakt"):
        try:
            cands.append(urljoin(base, p))
        except Exception:
            pass
    # ユニークにして先頭だけ
    uniq = []
    seen = set()
    for u in cands:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
        if len(uniq) >= CAND_CAP:
            break
    return uniq

def _score_email(email: str, site_host: str, ctx: dict) -> int:
    score = 0
    if EXCLUDE_RE.search(email): score -= 40
    # ドメイン一致を加点
    try:
        if _registrable(email.split("@",1)[1]) == _registrable(site_host):
            score += 30
    except Exception:
        pass
    # ローカルパート
    local = email.split("@",1)[0]
    if P1_RE.search(local): score += 18
    if P2_RE.search(local): score += 10
    # フリーメールは軽めに減点（小規模店が使う可能性はある）
    if re.search(r"@(gmail|yahoo|outlook|hotmail|icloud)\.", email, re.I): score -= 4
    # 取得元が contact ページ等なら加点
    if ctx.get("is_contact"): score += 6
    return score

def find_best_contact_email(home_url: str) -> tuple[str|None, str|None, list[str]]:
    """
    戻り値: (best_email or None, form_url or None, all_emails_found list)
    """
    form_url = None
    all_emails = []
    best = None
    best_score = -10**9

    # 1) ホーム取得
    try:
        html_text = _get(home_url)
    except Exception:
        html_text = ""

    # canonical でホームへ寄せて再取得（必要なら）
    home2 = _canonical_home(home_url, html_text)
    if home2 != home_url:
        try:
            html_text = _get(home2)
            home_url = home2
        except Exception:
            pass

    host = urlparse(home_url).netloc

    # 2) まずホームで抽出
    emails_home = _extract_emails_from_html(html_text)
    all_emails.extend(emails_home)

    # 3) contact系リンクを少数だけ追って抽出
    contact_links = _find_contact_links(home_url, html_text)
    for link in contact_links:
        ctx = {"is_contact": True}
        try:
            h = _get(link)
        except Exception:
            continue
        # フォームURL（action付きのform）があれば拾う
        try:
            soup = BeautifulSoup(h, "lxml")
            for f in soup.find_all("form"):
                if f.get("action"):
                    fu = urljoin(link, f["action"])
                    # メール/メッセージ/名前フィールドを含んでいそうなら優先
                    body = f.get_text(" ").lower()
                    if any(k in body for k in ("mail","email","message","お問い合わせ","問合せ","名前","name")):
                        form_url = form_url or fu
                        break
        except Exception:
            pass
        ems = _extract_emails_from_html(h)
        all_emails.extend(ems)
        for e in ems:
            sc = _score_email(e, host, ctx)
            if sc > best_score:
                best, best_score = e, sc

    # 4) ホームで見つかったメールも評価
    for e in emails_home:
        sc = _score_email(e, host, {"is_contact": False})
        if sc > best_score:
            best, best_score = e, sc

    # 5) 返却
    # 同一ドメインのメールが一つも無い＆フリメだけ、なら最良のものをそのまま返す（小規模店想定）
    uniq_all = sorted(set(all_emails))
    return best, form_url, uniq_all