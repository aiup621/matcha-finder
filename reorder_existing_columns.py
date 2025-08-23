import os, gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
load_dotenv()
gc = gspread.authorize(Credentials.from_service_account_file("service_account.json",
    scopes=["https://www.googleapis.com/auth/spreadsheets"]))
ws = gc.open_by_key(os.environ["SHEET_ID"]).worksheet("リスト")

values = ws.get_all_values()
if not values: raise SystemExit("empty sheet")

# 2行目以降を D,E,F の新並びに更新
updates = []
for r, row in enumerate(values[1:], start=2):
    # 安全に長さチェック
    old = row + [""] * (6 - len(row))
    newD = old[5]  # Instagram → D
    newE = old[3]  # 問い合わせアドレス → E
    newF = old[4]  # フォームURL → F
    updates.append({"range": f"D{r}:F{r}", "values": [[newD, newE, newF]]})

if updates:
    ws.batch_update(updates, value_input_option="RAW")
    print(f"reordered {len(updates)} rows")
else:
    print("no rows to reorder")
