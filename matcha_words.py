import re

KW_POSITIVE = [
    r"\bmatcha\b",
    r"\bmacha\b",
    r"\bmatcha\s+latte\b",
    r"抹茶",
]
KW_SECONDARY = [
    r"\bgreen\s*tea\b",
    r"\bceremonial\b",
    r"\buji\b",
]
KW_NEGATIVE = [
    r"houjicha",
    r"genmaicha",
    r"sencha",
    r"jasmine",
]

def has_matcha_text(text: str) -> bool:
    t = text or ""
    if any(re.search(p, t, re.I) for p in KW_POSITIVE):
        return True
    if any(re.search(n, t, re.I) for n in KW_NEGATIVE):
        return False
    if any(re.search(p, t, re.I) for p in KW_SECONDARY) and "matcha" not in t.lower():
        return True
    return False
