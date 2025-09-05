import os
import gspread
from google.oauth2.service_account import Credentials
from light_extract import http_get, extract_contacts

def open_ws():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    ws = sh.worksheet(os.environ.get("GOOGLE_WORKSHEET_NAME", "抹茶営業リスト（カフェ）"))
    return ws

def update_contacts(start_row: int = 2):
    ws = open_ws()
    values = ws.get_all_values()
    if start_row < 2:
        start_row = 2
    for idx in range(start_row-1, len(values)):
        row_num = idx + 1
        row = values[idx]
        home = row[2].strip() if len(row) > 2 else ""
        if not home:
            continue
        resp = http_get(home)
        if not resp or not resp.text:
            continue
        ig, emails, form = extract_contacts(home, resp.text)
        email = emails[0] if emails else ""
        updates = [{"range": f"D{row_num}:F{row_num}", "values": [[ig, email, form]]}]
        note = "なし" if not ig and not email and not form else ""
        updates.append({"range": f"G{row_num}", "values": [[note]]})
        ws.batch_update(updates, value_input_option="RAW")

def main():
    start = int(os.getenv("ACTION_ROW", "2"))
    update_contacts(start)

if __name__ == "__main__":
    main()
