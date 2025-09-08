import html
import json
import re
from typing import List, Dict
from bs4 import BeautifulSoup

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAILTO_RE = re.compile(
    r"mailto:([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
    re.I,
)
OBFUSCATED_RE = re.compile(
    r"([A-Za-z0-9._%+-]+)[\s\[\]()\u2022\u00b7-]*@[\s\[\]()\u2022\u00b7-]*([A-Za-z0-9.-]+)[\s\[\]()\u2022\u00b7-]*\.[\s\[\]()\u2022\u00b7-]*([A-Za-z]{2,})"
)


FREEMAILS = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "aol.com",
    "icloud.com",
    "protonmail.com",
}


def decode_cfemail(code: str) -> str:
    r = int(code[:2], 16)
    return "".join(chr(int(code[i : i + 2], 16) ^ r) for i in range(2, len(code), 2))


def _yield_json_emails(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() == "email" and isinstance(v, str):
                if EMAIL_RE.search(v):
                    yield v
            elif isinstance(v, (dict, list)):
                yield from _yield_json_emails(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _yield_json_emails(item)


def extract_emails(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Return a list of {"email", "surface"} found in ``soup``."""

    results: List[Dict[str, str]] = []
    seen = set()

    # mailto links and Cloudflare protected
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().startswith("mailto:"):
            email = href.split(":", 1)[1].split("?")[0]
            if email not in seen:
                results.append({"email": email, "surface": "a"})
                seen.add(email)
        cf = a.get("data-cfemail")
        if cf:
            email = decode_cfemail(cf)
            if email not in seen:
                results.append({"email": email, "surface": "a"})
                seen.add(email)

    # inline script content
    for tag in soup.find_all("script"):
        if tag.string:
            for match in MAILTO_RE.finditer(tag.string):
                email = match.group(1)
                if email not in seen:
                    results.append({"email": email, "surface": "script"})
                    seen.add(email)

    # on* handlers
    for tag in soup.find_all(True):
        for attr, value in tag.attrs.items():
            if attr.startswith("on") and isinstance(value, str):
                for match in MAILTO_RE.finditer(value):
                    email = match.group(1)
                    if email not in seen:
                        results.append({"email": email, "surface": "script"})
                        seen.add(email)

    # data-attribute assembly
    for tag in soup.find_all(attrs={"data-domain": True}):
        user = tag.get("data-user") or tag.get("data-name")
        domain = tag.get("data-domain")
        if user and domain:
            email = f"{user}@{domain}"
            if email not in seen:
                results.append({"email": email, "surface": "data-attr"})
                seen.add(email)

    # json-ld
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except json.JSONDecodeError:
            continue
        for email in _yield_json_emails(data):
            if email not in seen:
                results.append({"email": email, "surface": "jsonld"})
                seen.add(email)

    # text with obfuscation
    raw_text = soup.get_text(" ")
    text = html.unescape(raw_text)
    replaced = False
    if re.search(r"\[at\]|\(at\)|&#64;", text, flags=re.I):
        replaced = True
    text = re.sub(r"\[at\]|\(at\)|&#64;", "@", text, flags=re.I)
    if re.search(r"\[dot\]|\(dot\)|&#46;", text, flags=re.I):
        replaced = True
    text = re.sub(r"\[dot\]|\(dot\)|&#46;", ".", text, flags=re.I)
    text = re.sub(r"\s*@\s*", "@", text)
    text = re.sub(r"\s*\.\s*", ".", text)
    for match in EMAIL_RE.finditer(text):
        email = match.group(0)
        surface = "obfuscated" if replaced else "text"
        if email not in seen:
            results.append({"email": email, "surface": surface})
            seen.add(email)
    for match in OBFUSCATED_RE.finditer(text):
        email = f"{match.group(1)}@{match.group(2)}.{match.group(3)}"
        if email not in seen:
            results.append({"email": email, "surface": "obfuscated"})
            seen.add(email)

    return results
