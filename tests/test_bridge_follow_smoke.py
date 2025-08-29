import os, sys, subprocess
from pathlib import Path


def test_bridge_follow_smoke(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    (tmp_path / "pipeline_smart.py").write_text(
        (repo_root / "pipeline_smart.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    sheet_stub = """\
def load_existing_keys(*a, **k):
    return {"homes": set(), "instas": set()}

def append_row_in_order(*a, **k):
    pass
"""
    (tmp_path / "sheet_io_v2.py").write_text(sheet_stub, encoding="utf-8")
    light_stub = """\
import re
MATCHA_WORDS = re.compile('matcha', re.I)

def canon_url(u):
    return u

def http_get(url):
    class R:
        def __init__(self, txt):
            self.text = txt
    if 'yelp' in url:
        return R('<a href=\"https://official.com\">Website</a>')
    return R('<html>Our Matcha Latte</html>')

def html_text(x):
    return x

def is_media_or_platform(u):
    return False

def normalize_candidate_url(u):
    return u

def find_menu_links(html, home, limit=3):
    return []

def extract_contacts(home, html):
    return ('http://instagram.com/foo', ['a@example.com'], None)

def is_us_cafe_site(home, html):
    return True

def guess_brand(home, html, title):
    return 'Foo Cafe'
"""
    (tmp_path / "light_extract.py").write_text(light_stub, encoding="utf-8")
    cse_stub = """\
class DailyQuotaExceeded(Exception):
    pass

class CSEClient:
    def __init__(self, *a, **k):
        pass

    def search(self, *a, **k):
        return {"items": [{"link": "https://www.yelp.com/biz/foo"}]}
"""
    (tmp_path / "cse_client.py").write_text(cse_stub, encoding="utf-8")
    (tmp_path / "dotenv.py").write_text("def load_dotenv():\n    pass\n", encoding="utf-8")
    requests_stub = """\
class RequestException(Exception):
    pass

def get(*a, **k):
    class R:
        status_code = 200
        headers = {'content-type':'text/html'}
        def json(self):
            return {}
    return R()

def head(*a, **k):
    class R:
        status_code = 200
        headers = {'content-type':'text/html'}
    return R()
"""
    (tmp_path / "requests.py").write_text(requests_stub, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "GOOGLE_API_KEY": "dummy",
            "GOOGLE_CX": "dummy",
            "SHEET_ID": "dummy",
            "TARGET_NEW": "1",
            "MAX_QUERIES_PER_RUN": "1",
            "BRIDGE_DOMAINS": "yelp.com",
            "PYTHONPATH": str(repo_root),
        }
    )
    result = subprocess.run(
        [sys.executable, "-u", "pipeline_smart.py"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert "bridge-followed[yelp.com]" in result.stdout
    assert result.returncode == 0
