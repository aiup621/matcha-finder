import os, time, sys
from dotenv import load_dotenv
import gspread

load_dotenv()  # .env を読む
sheet_id  = os.environ.get("SHEET_ID")
ws_name   = os.environ.get("GOOGLE_WORKSHEET_NAME", "raw")
sa_json   = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")

print(f"[check] SHEET_ID={sheet_id}")
print(f"[check] WORKSHEET={ws_name}")
print(f"[check] SA_JSON={sa_json}")

try:
    gc = gspread.service_account(filename=sa_json)
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet(ws_name)
    row = ["_healthcheck_", time.strftime("%Y-%m-%d %H:%M:%S")]
    ws.append_row(row)
    print("[OK] appended one _healthcheck_ row.")
except gspread.exceptions.WorksheetNotFound:
    print(f"[NG] ワークシート '{ws_name}' が見つかりません。タブ名を合わせてください。")
    sys.exit(2)
except gspread.exceptions.SpreadsheetNotFound:
    print("[NG] シートIDが不正、またはシェア権限がありません（サービスアカウントに編集者権限を付与してください）。")
    sys.exit(3)
except Exception as e:
    print("[NG] 予期せぬエラー:", repr(e))
    sys.exit(1)