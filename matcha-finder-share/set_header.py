import os, gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
load_dotenv()
scopes=["https://www.googleapis.com/auth/spreadsheets"]
creds=Credentials.from_service_account_file("service_account.json", scopes=scopes)
gc=gspread.authorize(creds)
ws=gc.open_by_key(os.environ["SHEET_ID"]).worksheet("リスト")
ws.update("A1:F1", [["店名","国","公式サイトURL","Instagramリンク","問い合わせアドレス","問い合わせフォームURL"]])
print("ヘッダーを更新しました")
