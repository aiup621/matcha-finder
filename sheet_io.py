# sheet_io.py
import os, time
import gspread
from google.oauth2.service_account import Credentials
from rules import normalize_url

HEADERS = ["店名","国","公式サイトURL","問い合わせアドレス","問い合わせフォームURL","Instagramリンク"]

def open_sheet():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file('service_account.json', scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    ws = sh.worksheet(os.environ.get("GOOGLE_WORKSHEET_NAME", "抹茶営業リスト（カフェ）"))
    if not ws.get_all_values():
        ws.append_row(HEADERS, value_input_option='RAW')
    return ws

def append_rows_batched(ws, rows, batch=50):
    for i in range(0, len(rows), batch):
        ws.append_rows(rows[i:i+batch], value_input_option='RAW'); time.sleep(1)

def get_existing_official_urls(ws) -> set[str]:
    values = ws.get_all_values()
    if not values: return set()
    header = values[0]
    try:
        col_idx = header.index("公式サイトURL")
    except ValueError:
        return set()
    urls=set()
    for row in values[1:]:
        if len(row) > col_idx:
            u = (row[col_idx] or "").strip()
            if u: urls.add(normalize_url(u))
    return urls
