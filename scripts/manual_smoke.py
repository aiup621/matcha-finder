import os, types

import sys

# Minimal stubs for optional dependencies
if "gspread" not in sys.modules:
    gspread = types.ModuleType("gspread")
    def service_account(filename=None):
        return types.SimpleNamespace(open_by_key=lambda key: types.SimpleNamespace(worksheet=lambda name: None, add_worksheet=lambda **k: None))
    gspread.service_account = service_account
    excmod = types.ModuleType("gspread.exceptions")
    class WorksheetNotFound(Exception):
        pass
    excmod.WorksheetNotFound = WorksheetNotFound
    gspread.exceptions = excmod
    sys.modules["gspread"] = gspread
    sys.modules["gspread.exceptions"] = excmod

if "requests" not in sys.modules:
    requests = types.ModuleType("requests")
    class _Resp:
        def __init__(self, text="", content=b""):
            self.status_code = 200
            self.text = text
            self.content = content
    def get(*a, **k):
        return _Resp()
    requests.get = get
    requests.RequestException = Exception
    sys.modules["requests"] = requests

if "bs4" not in sys.modules:
    bs4 = types.ModuleType("bs4")
    class _Soup:
        def __init__(self, *a, **k):
            pass
        def find_all(self, *a, **k):
            return []
        def get_text(self, *a, **k):
            return ""
    def BeautifulSoup(html, parser=None):
        return _Soup()
    bs4.BeautifulSoup = BeautifulSoup
    sys.modules["bs4"] = bs4

if "pdfminer" not in sys.modules:
    pdfminer = types.ModuleType("pdfminer")
    hl = types.ModuleType("pdfminer.high_level")
    def extract_text(fp):
        return ""
    hl.extract_text = extract_text
    pdfminer.high_level = hl
sys.modules["pdfminer"] = pdfminer
sys.modules["pdfminer.high_level"] = hl

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pipeline_smart as ps
from finder.bridge import extract_official
from finder.querygen import _sanitize_query
from finder import bridge as bridge_mod


def _bs_stub(html, parser=None):
    class _A:
        def __init__(self):
            self.href = "https://www.yelp.com/biz_redir?url=http://official.example.com"

        def get(self, key, default=None):
            return getattr(self, key, default)

        def get_text(self, *a, **k):
            return "Website"

        def __getitem__(self, k):
            return getattr(self, k)

    class _Soup:
        def find_all(self, *a, **k):
            return [_A()]

    return _Soup()


bridge_mod.BeautifulSoup = _bs_stub

# Environment setup
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("GOOGLE_CX", "dummy")
os.environ.setdefault("SHEET_ID", "dummy")
os.environ.setdefault("TARGET_NEW", "1")
os.environ.setdefault("CITY_SEEDS", "Seattle, WA,Denver, CO,Boston, MA")
os.environ.setdefault("MAX_QUERIES_PER_RUN", "3")
os.environ.setdefault("MAX_ROTATIONS_PER_RUN", "1")

# Fake CSE client ensuring queries are sanitized
class FakeCSE:
    def __init__(self, *a, **k):
        pass

    def search(self, q, start=1, num=10, safe="off", lr="lang_en", cr="countryUS", gl="us"):
        assert "site:.com" not in q
        return {"items": [{"link": "https://www.yelp.com/biz/test-cafe", "title": "Yelp"}]}

# Fake HTTP fetcher for Yelp and official site
def fake_http_get(url, timeout=10, allow_redirects=True):
    if "yelp.com" in url:
        html = (
            '<a href="https://www.yelp.com/biz_redir?url=http://official.example.com">Website</a>'
        )
    else:
        html = "<html>matcha</html>"
    return types.SimpleNamespace(status_code=200, text=html, content=b"")

# Stubs for extraction functions
ps.CSEClient = FakeCSE
ps.http_get = fake_http_get
ps.extract_contacts = lambda home, html: (None, [], None)
ps.extract_contact_endpoints = lambda html, home: {}
ps.find_menu_links = lambda html, home, limit=3: []
ps.html_text = lambda html: html
ps.page_has_matcha = lambda text: "matcha" in text.lower()
ps.verify_matcha = lambda menus, ig, text: (True, "mock")
ps.is_us_cafe_site = lambda home, html: True
ps.guess_brand = lambda home, html, title: "Test Cafe"
ps.append_row_in_order = lambda sheet, ws, row: None
ps.load_existing_keys = lambda sheet, ws: {"homes": set(), "instas": set()}
ps.normalize_candidate_url = lambda u: u

# Sanitize check example
test_q = _sanitize_query("matcha seattle site:.com cafe")
assert "site:.com" not in test_q

# Bridge extraction unit test
yelp_html = '<a href="https://www.yelp.com/biz_redir?url=http://official.example.com">Website</a>'
assert extract_official("https://www.yelp.com/biz/foo", yelp_html) == "http://official.example.com"

ps.main([])

print("クラッシュ無し")
print(f"橋渡し試行回数={ps.BRIDGE_TRIED} 公式URL件数={ps.BRIDGE_SUCCESS}")
