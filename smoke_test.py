import os, sys, types

# ---- 依存スタブ（インストール不要） ----
# gspread スタブ
if 'gspread' not in sys.modules:
    gspread = types.ModuleType('gspread')
    def service_account(filename=None):
        return types.SimpleNamespace(open_by_key=lambda key: types.SimpleNamespace(
            worksheet=lambda name: None, add_worksheet=lambda **k: None))
    gspread.service_account = service_account
    excmod = types.ModuleType('gspread.exceptions')
    class WorksheetNotFound(Exception): pass
    excmod.WorksheetNotFound = WorksheetNotFound
    gspread.exceptions = excmod
    sys.modules['gspread'] = gspread
    sys.modules['gspread.exceptions'] = excmod

# requests スタブ
if 'requests' not in sys.modules:
    requests = types.ModuleType('requests')
    class _Resp:
        def __init__(self, text='', content=b''):
            self.status_code=200; self.text=text; self.content=content
    def get(*a, **k): return _Resp()
    requests.get = get
    requests.RequestException = Exception
    sys.modules['requests'] = requests

# bs4 スタブ（今回は使わない想定）
if 'bs4' not in sys.modules:
    bs4 = types.ModuleType('bs4')
    class _Soup:
        def __init__(self, *a, **k): pass
        def get_text(self, *a, **k): return ""
        def find_all(self, *a, **k): return []
        def select(self, *a, **k): return []
        def __call__(self,*a,**k): return []
        def decompose(self): pass
    def BeautifulSoup(html, parser=None): return _Soup()
    bs4.BeautifulSoup = BeautifulSoup
    sys.modules['bs4'] = bs4

# pdfminer スタブ
if 'pdfminer' not in sys.modules:
    pdfminer = types.ModuleType('pdfminer')
    hl = types.ModuleType('pdfminer.high_level')
    def extract_text(fp): return ""
    hl.extract_text = extract_text
    pdfminer.high_level = hl
    sys.modules['pdfminer'] = pdfminer
    sys.modules['pdfminer.high_level'] = hl

# ---- 本体読み込み ----
import pipeline_smart as ps

# .envの空値を無視して強制セット
os.environ['GOOGLE_API_KEY'] = 'dummy'
os.environ['GOOGLE_CX'] = 'dummy'
os.environ['SHEET_ID'] = 'dummy'
os.environ['TARGET_NEW'] = '1'   # 1件だけ追加したら終了

# ダミー検索
class FakeCSE:
    def __init__(self, *a, **k): pass
    def search(self, q, start=1, num=10, safe='off'):
        return {'items':[{'link':'https://matcha.test/','title':'Test Matcha Cafe'}]}

# HTTPは固定HTMLを返す
def fake_http_get(url, timeout=10, allow_redirects=True):
    html = '<html><body>matcha latte <a href="mailto:hello@matcha.test">mail</a>' \
           '<a href="https://instagram.com/matcha_cafe/"></a><form></form></body></html>'
    return types.SimpleNamespace(status_code=200, text=html, content=b'')

# === ここがポイント ===
# テスト時は「抹茶含むHTMLならTrue」を直接判定（パーサ依存を外す）
ps.has_matcha_text = lambda html: ('matcha' in (html or '').lower()) or ('抹茶' in (html or ''))

# 差し替え
ps.CSEClient = FakeCSE
ps.http_get = fake_http_get
ps.is_chain_like = lambda home, html: False
ps.append_row_in_order = lambda sheet, ws, row: print('[WRITE]', row)
ps.load_existing_keys = lambda sheet, ws: {'homes': set(), 'instas': set()}

# 実行
ps.main()
print('SMOKE TEST OK')
