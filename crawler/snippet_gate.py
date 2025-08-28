from __future__ import annotations
import re
from urllib.parse import urlparse

# regex: matcha within ±50 chars of latte/menu/drink/ceremonial
NEAR_REGEX = re.compile(
    r"(?is)matcha.{0,50}(latte|menu|drink|ceremonial)|(latte|menu|drink|ceremonial).{0,50}matcha"
)


def accepts(url: str, snippet: str) -> bool:
    snippet = (snippet or "").casefold()
    path = urlparse(url).path.lower()
    if NEAR_REGEX.search(snippet):
        return True
    if "menu" in path and "matcha" in snippet:
        return True
    return False

__all__ = ["accepts"]
