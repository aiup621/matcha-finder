# contact_csv.py（任意）
import sys, csv, re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
EXCLUDE_PATTERNS = r"(no-?reply|career|jobs|recruit|press|media|reservation|booking|order|orders)"
PRIO1 = r"(owner|founder|ceo|gm|manager|mgr|buyer)"
PRIO2 = r"(info|hello|contact)"
PRIO3 = r"(catering|events)"
def pick_best_email(emails):
    cand = [e.lower() for e in emails if not re.search(EXCLUDE_PATTERNS, e.lower())]
    for p in (PRIO1, PRIO2, PRIO3):
        for e in cand:
            if re.search(p, e): return e
    return cand[0] if cand else ""
def crawl_once(url):
    with sync_playwright() as p:
        b = p.chromium.launch(); page = b.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        soup = BeautifulSoup(page.content(), "lxml")
        emails, forms, found_on = set(), [], ""
        for a in soup.select("a[href]"):
            href = a["href"]; low = href.lower()
            if low.startswith("mailto:"):
                emails.add(low.replace("mailto:", "").strip())
                if not found_on: found_on = urlparse(page.url).path or "/"
            if "contact" in low or "inquiry" in low or "support" in low:
                forms.append(href if href.startswith("http") else urljoin(page.url, href))
        for f in forms[:3]:
            try:
                page.goto(f, wait_until="domcontentloaded", timeout=30000)
                s = BeautifulSoup(page.content(), "lxml")
                for a in s.select("a[href^='mailto:']"):
                    mail = a["href"].replace("mailto:", "").strip().lower()
                    emails.add(mail)
                    if not found_on: found_on = urlparse(page.url).path or "/"
            except Exception: pass
        b.close()
    best = pick_best_email(list(emails))
    status = "found" if best else "none"
    form_flag = "フォーム有り" if forms else ""
    form_url = forms[0] if forms else ""
    return best or "無し", status, form_flag, form_url, found_on or ""
if __name__ == "__main__":
    urls = [l.strip() for l in sys.stdin if l.strip()]
    w = csv.writer(sys.stdout)
    w.writerow(["index","url","email","status","form","form_url","found_on"])
    for i, u in enumerate(urls, 1):
        email, status, form_flag, form_url, found_on = crawl_once(u)
        w.writerow([i, u, email, status, form_flag, form_url, found_on])
