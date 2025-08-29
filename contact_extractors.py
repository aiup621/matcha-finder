"""Utilities for extracting contact endpoints from HTML content.

The functions here focus on English text only and aim to locate
contact forms, pages, e-mail addresses and phone numbers.  The
implementation is intentionally lightweight and avoids making any
network requests; it merely parses the supplied HTML document.
"""
from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# English anchor keywords that may indicate contact links
_ANCHOR_KEYWORDS = {
    "contact",
    "contact us",
    "get in touch",
    "connect",
    "support",
    "feedback",
    "booking",
    "reserve",
    "book now",
}

# Known third party form providers we want to recognise
_FORM_PROVIDERS = {
    "typeform": "typeform.com",
    "jotform": "jotform.com",
    "googleforms": "docs.google.com/forms",
    "wufoo": "wufoo.com",
    "formspree": "formspree.io",
    "hubspot": "hubspotforms.com",
    "netlify": "netlify.app",
    "squarespace": "squarespace.com",
    "wix": "wix.com",
    "tally": "tally.so",
    "paperform": "paperform.co",
    "cognito": "cognitoforms.com",
    "zoho": "zoho.com",
}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def extract_contact_endpoints(html: str, base_url: str) -> Dict[str, object]:
    """Extract contact related endpoints from ``html``.

    Parameters
    ----------
    html:
        Raw HTML text.
    base_url:
        The URL of the page where ``html`` was retrieved from.  Used to
        resolve relative links.
    """

    soup = BeautifulSoup(html, "html.parser")

    form_urls: List[str] = []
    form_providers: List[Dict[str, str]] = []
    contact_pages: List[str] = []
    emails: List[str] = []
    phones: List[str] = []

    # ---- anchors ----
    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ", strip=True) or "").lower()
        aria = (a.get("aria-label") or "").lower()
        href = a["href"]
        low_href = href.lower()
        if low_href.startswith("mailto:"):
            emails.append(low_href.split(":", 1)[1])
        if low_href.startswith("tel:"):
            phones.append(low_href.split(":", 1)[1])
        anchor_txt = f"{text} {aria}".strip()
        if any(k in anchor_txt for k in _ANCHOR_KEYWORDS):
            contact_pages.append(urljoin(base_url, href))

    # ---- forms ----
    for frm in soup.find_all("form"):
        action = frm.get("action") or ""
        if action:
            url = urljoin(base_url, action)
        else:
            # client side handled forms are considered to submit to the
            # current page
            url = base_url
            action = "client-side"
        form_urls.append(url)
        low = url.lower()
        for provider, domain in _FORM_PROVIDERS.items():
            if domain in low:
                form_providers.append({"provider": provider, "url": url})
                break

    # recognise embedded third party forms via iframe/src
    for tag in soup.find_all(["iframe", "embed"], src=True):
        src = urljoin(base_url, tag["src"])
        low = src.lower()
        for provider, domain in _FORM_PROVIDERS.items():
            if domain in low:
                form_urls.append(src)
                form_providers.append({"provider": provider, "url": src})
                break

    # ---- text based extraction ----
    body_text = soup.get_text(" ")
    emails.extend(_EMAIL_RE.findall(body_text))
    phones.extend(_PHONE_RE.findall(body_text))

    return {
        "form_urls": _dedupe([urljoin(base_url, u) for u in form_urls]),
        "form_providers": form_providers,
        "contact_pages": _dedupe([urljoin(base_url, u) for u in contact_pages]),
        "emails": _dedupe(emails),
        "phones": _dedupe(phones),
    }


__all__ = ["extract_contact_endpoints"]
