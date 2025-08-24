import os, gspread
from gspread.exceptions import WorksheetNotFound
from urllib.parse import urlsplit, urlunsplit

ORDER = ["店名","国","公式サイトURL","Instagramリンク","問い合わせアドレス","問い合わせフォームURL"]

# ヘッダーには一切触れない。存在しなければワークシートを作るだけ。
def _open_ws(sheet_id, worksheet_name):
    cred_path = os.getenv("SERVICE_ACCOUNT_JSON", "service_account.json")
    gc = gspread.service_account(filename=cred_path)
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(worksheet_name)
    except WorksheetNotFound:
        ws = sh.add_worksheet(title=worksheet_name, rows=2000, cols=max(6, len(ORDER)))
    return ws

def _canon_root(u: str) -> str:
    if not u: return ""
    try:
        s = urlsplit(u.strip())
        scheme = "https"
        netloc = (s.netloc or "").lower()
        if netloc.startswith("www."): netloc = netloc[4:]
        return urlunsplit((scheme, netloc, "/", "", ""))
    except Exception:
        return u.strip()

def _canon_url(u: str) -> str:
    if not u: return ""
    try:
        s = urlsplit(u.strip())
        scheme = "https" if s.scheme in ("http","https","") else s.scheme
        netloc = (s.netloc or "").lower()
        if netloc.startswith("www."): netloc = netloc[4:]
        path = s.path or "/"
        if not path.endswith("/"): path += "/"
        return urlunsplit((scheme, netloc, path, "", ""))
    except Exception:
        return u.strip()

def _norm(x: str) -> str:
    return (x or "").strip().lower()

def _find_col(header, candidates):
    idx = { _norm(v): i+1 for i, v in enumerate(header) if v }
    for name in candidates:
        c = idx.get(_norm(name))
        if c: return c
    return None

# 既存の重複判定キーを読み取る（見つからなければ可能な範囲で空集合）
def load_existing_keys(sheet_id, worksheet_name):
    ws = _open_ws(sheet_id, worksheet_name)
    header = ws.row_values(1)
    # よくある表記ゆれを許容
    home_col = _find_col(header, ["公式サイトURL","公式URL","Web","Website","サイト","URL","ホームページ"])
    insta_col = _find_col(header, ["Instagramリンク","Instagram","IG","インスタグラム"])

    homes, instas = set(), set()
    if home_col:
        for v in ws.col_values(home_col)[1:]:
            if v: homes.add(_canon_root(v))
    if insta_col:
        for v in ws.col_values(insta_col)[1:]:
            if v: instas.add(_canon_url(v))
    return {"homes": homes, "instas": instas}

# 常に最終行の次へ追記（ヘッダーは変更しない）
def append_row_in_order(sheet_id, worksheet_name, rowdict):
    skip_env = os.getenv("SKIP_SHEETS", "").lower()
    if skip_env in ("1", "true", "yes", "on"):
        print(f"[WARN] SKIP_SHEETS={skip_env} -> Sheets append skipped")
        return
    ws = _open_ws(sheet_id, worksheet_name)
    row = [rowdict.get(k, "") for k in ORDER]
    ws.append_row(row, value_input_option="RAW")
