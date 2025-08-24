import os
import time
import pytest
from dotenv import load_dotenv
import gspread

# 環境変数やサービスアカウント設定を読み込む
load_dotenv()
sheet_id = os.environ.get("SHEET_ID")
ws_name = os.environ.get("GOOGLE_WORKSHEET_NAME", "raw")
sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")

print(f"[check] SHEET_ID={sheet_id}")
print(f"[check] WORKSHEET={ws_name}")
print(f"[check] SA_JSON={sa_json}")

# service_account.json がなければテストをスキップ
if not os.path.exists(sa_json):
    pytest.skip("service_account.json が存在しないため、このテストをスキップします。", allow_module_level=True)


def test_append_healthcheck_row():
    """Google スプレッドシートへヘルスチェック行を追加できるかを確認する"""
    try:
        gc = gspread.service_account(filename=sa_json)
        sh = gc.open_by_key(sheet_id)
        ws = sh.worksheet(ws_name)
        row = ["_healthcheck_", time.strftime("%Y-%m-%d %H:%M:%S")]
        ws.append_row(row)
        print("[OK] appended one _healthcheck_ row.")
    except gspread.exceptions.WorksheetNotFound:
        pytest.fail(f"ワークシート '{ws_name}' が見つかりません。タブ名を合わせてください。")
    except gspread.exceptions.SpreadsheetNotFound:
        pytest.fail("シートIDが不正、またはシェア権限がありません（サービスアカウントに編集者権限を付与してください）。")
    except Exception as e:
        pytest.fail(f"予期せぬエラー: {repr(e)}")

