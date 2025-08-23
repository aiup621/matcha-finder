import os, gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from rules import homepage_of, extract_brand_name_v2 as extract_brand_name
from crawl_site import fetch_site_safe as fetch_site

load_dotenv()
scopes=["https://www.googleapis.com/auth/spreadsheets"]
creds=Credentials.from_service_account_file("service_account.json", scopes=scopes)
gc=gspread.authorize(creds)
ws=gc.open_by_key(os.environ["SHEET_ID"]).worksheet("リスト")

values = ws.get_all_values()
header = values[0]
i_name = header.index("店名") if "店名" in header else 0
i_url  = header.index("公式サイトURL")

updates = []
for r,row in enumerate(values[1:], start=2):
    name = (row[i_name] or "").strip()
    if name.lower() == "home":
        url = (row[i_url] or "").strip()
        if not url: continue
        home = homepage_of(url)
        site = fetch_site(home, screenshot_path=None)
        new  = extract_brand_name(site.get("html",""), home)
        if new and new.lower() != "home":
            updates.append({"range": f"A{r}", "values": [[new]]})

if updates:
    ws.batch_update(updates, value_input_option="RAW")
    print(f"fixed {len(updates)} rows")
else:
    print("no rows to fix")
