import io, re, requests
from bs4 import BeautifulSoup
try:
    from PIL import Image
except ImportError:  # Pillow が無い環境でも他の判定は継続できるようにする
    Image = None
from PyPDF2 import PdfReader
import pytesseract

# 語彙（過検知を避けるフィルタつき）
KW_POSITIVE = [r"\bmatcha\b", r"\bmatcha\s+latte\b", r"抹茶"]
KW_SECONDARY = [r"\bgreen\s+tea\b", r"\bceremonial\b", r"\buji\b"]
KW_NEGATIVE = [r"houjicha", r"genmaicha", r"sencha", r"jasmine"]

def _has_matcha_text(text: str)->bool:
    t = text or ""
    if any(re.search(p, t, re.I) for p in KW_POSITIVE):
        return True
    if any(re.search(n, t, re.I) for n in KW_NEGATIVE):
        # ネガが強く出るなら様子見
        pass
    # セカンダリ語彙は“matcha”不在時のみ弱判定
    if any(re.search(p, t, re.I) for p in KW_SECONDARY) and "matcha" not in t.lower():
        return True
    return False

def _get_html(url: str)->str:
    try:
        r = requests.get(url, timeout=12, headers={"User-Agent":"Mozilla/5.0"})
        if r.status_code >= 400: return ""
        return r.text
    except: return ""

def _pdf_text(url: str)->str:
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        with io.BytesIO(r.content) as f:
            reader = PdfReader(f)
            out = []
            for page in reader.pages:
                out.append(page.extract_text() or "")
            return "\n".join(out)
    except: return ""

def _ocr_image_from_url(url: str) -> str:
    if Image is None:
        return ""
    try:
        r = requests.get(url, timeout=15, stream=True)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        # 文字が小さい想定で拡大→OCR
        w, h = img.size
        if min(w, h) < 1200:
            img = img.resize((w * 2, h * 2))
        return pytesseract.image_to_string(img, lang="eng")
    except:
        return ""

def verify_matcha(menu_urls, insta_url, homepage_html):
    """
    返り値:
      how: どこで確認できたか 'menu_html' | 'menu_pdf' | 'menu_ocr' | 'homepage' | 'instagram' | ''
      evidence: 証跡URL or ヒット語
    """
    # 1) ホームのテキスト
    if _has_matcha_text(homepage_html or ""):
        return ("homepage", "home_html_match")

    # 2) メニューURLでチェック
    for mu in (menu_urls or []):
        mu_l = (mu or "").lower()
        if mu_l.endswith(".pdf"):
            txt = _pdf_text(mu)
            if _has_matcha_text(txt):
                return ("menu_pdf", mu)
        else:
            html = _get_html(mu)
            if _has_matcha_text(html):
                return ("menu_html", mu)
            # メニュー画像のOCR（menu/drinkを含むimg優先）
            try:
                s = BeautifulSoup(html or "", "lxml")
                imgs = [im.get("src") for im in s.select("img[src]")]
                imgs = [im for im in imgs if im and any(k in im.lower() for k in ["menu","drink","beverage"])]
                for src in imgs[:3]:
                    # 絶対URL化（簡易）
                    if src.startswith("//"): src = "https:" + src
                    if src.startswith("/"):
                        from urllib.parse import urljoin
                        src = urljoin(mu, src)
                    text = _ocr_image_from_url(src)
                    if _has_matcha_text(text):
                        return ("menu_ocr", src)
            except:
                pass

    # 3) 最後の手段：Instagram（投稿本文の解析はログイン壁があるため、証跡URLとして返す）
    if insta_url:
        return ("instagram", insta_url)

    return ("", "")

