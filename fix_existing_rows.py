import os, gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from rules import homepage_of, extract_brand_name
from crawl_site import fetch_site

load_dotenv()

def open_ws():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_file("service_account.json", scopes=scopes)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.environ["SHEET_ID"])
    return sh.worksheet("リスト")

ws = open_ws()
values = ws.get_all_values()
header = values[0]
i_name = header.index("店名"); i_country = header.index("国"); i_url = header.index("公式サイトURL")
updates = []
for r, row in enumerate(values[1:], start=2):
    url = row[i_url].strip()
    if not url:
        continue
    home = homepage_of(url)
    if home != url or "menu" in url.lower():
        site = fetch_site(home)
        name = extract_brand_name(site["html"], home)
        updates.append({"range": f"A{r}:C{r}", "values": [[name, row[i_country] or "USA", home]]})

if updates:
    ws.batch_update(updates, value_input_option="RAW")
    print(f"updated {len(updates)} rows")
else:
    print("no rows to update")
