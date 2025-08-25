import os, requests

API = "https://www.googleapis.com/customsearch/v1"

def _base_params(query, num=10):
    return {
        "key": os.environ["GOOGLE_API_KEY"],
        "cx": os.environ["GOOGLE_CX"],
        "q": query,
        "num": num,
        "lr": "lang_en",
        "cr": "countryUS",
        "gl": "us",
    }

def search_candidates(query, num=10):
    """後方互換の単発検索（従来関数）"""
    p = _base_params(query, num=num)
    r = requests.get(API, params=p, timeout=15)
    r.raise_for_status()
    data = r.json()
    for it in data.get("items", []) or []:
        link = it.get("link")
        if link:
            yield link

def search_candidates_iter(query, num=10, start=1, max_pages=1):
    """
    ページ送りで複数ページを巡回:
      start: 1,11,21...（CSEの開始位置）
      max_pages: 取るページ数
    """
    s = start
    for _ in range(max_pages):
        p = _base_params(query, num=num)
        p["start"] = s
        try:
            r = requests.get(API, params=p, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception:
            break
        items = data.get("items", []) or []
        if not items:
            break
        for it in items:
            link = it.get("link")
            if link:
                yield link
        # 次のページへ
        s += num
