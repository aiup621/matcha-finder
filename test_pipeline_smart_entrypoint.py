import os
import subprocess
import sys
from pathlib import Path


SHEET_IO_V2_STUB = """\
def load_existing_keys(*args, **kwargs):
    return {"homes": set(), "instas": set()}


def append_row_in_order(*args, **kwargs):
    pass
"""


LIGHT_EXTRACT_STUB = """\
import re

MATCHA_WORDS = re.compile(r"matcha", re.I)


def canon_root(u):
    return u


def canon_url(u):
    return u


def http_get(url):
    return None


def html_text(x):
    return ""


def is_media_or_platform(u):
    return False


def is_blocked(u):
    return False


def normalize_candidate_url(u):
    return ""


def find_menu_links(html, home, limit=3):
    return []


def one_pdf_text_from(html, home):
    return ""


def extract_contacts(home, html):
    return None, [], None


def is_us_cafe_site(home, html):
    return True


def guess_brand(home, html, title):
    return "Dummy"
"""


REQUESTS_STUB = """\
class RequestException(Exception):
    pass


def get(*args, **kwargs):
    class _Resp:
        status_code = 200
        ok = True

        def json(self):
            return {}

        text = ""

    return _Resp()
"""


DOTENV_STUB = """\
def load_dotenv():
    pass
"""


def test_pipeline_smart_entrypoint(tmp_path):
    repo_root = Path(__file__).resolve().parent

    (tmp_path / "pipeline_smart.py").write_text(
        (repo_root / "pipeline_smart.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "sheet_io_v2.py").write_text(SHEET_IO_V2_STUB, encoding="utf-8")
    (tmp_path / "light_extract.py").write_text(LIGHT_EXTRACT_STUB, encoding="utf-8")
    (tmp_path / "requests.py").write_text(REQUESTS_STUB, encoding="utf-8")
    (tmp_path / "dotenv.py").write_text(DOTENV_STUB, encoding="utf-8")

    env = os.environ.copy()
    env.update(
        {
            "GOOGLE_API_KEY": "dummy",
            "GOOGLE_CX": "dummy",
            "SHEET_ID": "dummy",
            "MAX_QUERIES_PER_RUN": "1",  # quick exit
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

    assert "[STOP]" in result.stdout
    assert result.returncode == 0
