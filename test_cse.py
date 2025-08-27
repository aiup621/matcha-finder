import os

import pytest
import requests
from dotenv import load_dotenv


load_dotenv()


def test_google_cse():
    """Simple query against the Google Custom Search API.

    The test is skipped when the required API credentials are not
    supplied via environment variables.
    """

    key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CSE_ID")
    if not key or not cx:
        pytest.skip("Google CSE credentials not configured")

    resp = requests.get(
        "https://www.googleapis.com/customsearch/v1",
        params={"key": key, "cx": cx, "q": "matcha cafe CA", "num": 1},
        timeout=15,
    )

    assert resp.status_code == 200
    assert "searchInformation" in resp.json()

