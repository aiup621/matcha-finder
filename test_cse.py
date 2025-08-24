from dotenv import load_dotenv
load_dotenv()

import os
import requests
import pytest

key = os.getenv("GOOGLE_API_KEY")
cx = os.getenv("GOOGLE_CX")

if not key or not cx:
    pytest.skip("Google CSE の環境変数が設定されていないため、このテストをスキップします。", allow_module_level=True)


def test_cse_quick_query():
    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": key, "cx": cx, "q": "matcha cafe CA", "num": 1},
            timeout=15,
        )
    except Exception as e:
        pytest.skip(f"ネットワークに接続できないためスキップ: {e}")
        return
    assert r.status_code == 200
    assert "searchInformation" in r.json()

