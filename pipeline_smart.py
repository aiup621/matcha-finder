import os, json, traceback
import re
import requests
import argparse
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from cse_client import CSEClient, DailyQuotaExceeded
from sheet_io_v2 import append_row_in_order, load_existing_keys
from light_extract import (
    canon_url, http_get, html_text, is_media_or_platform,
    normalize_candidate_url, find_menu_links,
    extract_contacts, is_us_cafe_site, guess_brand, MATCHA_WORDS
)
from contact_extractors import extract_contact_endpoints
from verify_matcha import verify_matcha
from blocklist import load_domain_blocklist, is_blocked_domain
from crawler_cache import load_cache, save_cache, has_seen, mark_seen, is_blocked_host
from config_loader import load_settings
from crawler.query_builder import QueryBuilder, BASE_NEG
from crawler.control import RunState, format_stop
from crawler.snippet_gate import accepts as snippet_accepts
from persistent_cache import PersistentCache
from cache_utils import Cache, EnvConfig
from runtime_blocklist import RuntimeBlockList, requires_js

"""Smart pipeline with bridge-domain hopping and dynamic negatives.

Env additions:
  - BRIDGE_DOMAINS / HARD_BLOCKLIST for special domain handling
  - PHASE_MAX controls query phase escalation
  - SKIP_ROTATE_THRESHOLD / MAX_ROTATIONS_PER_RUN tuning
  - ENGLISH_ONLY / REGION_HINT / SMALL_CHAIN_MAX_LOCATIONS
  - CONTACT_FORM_ALLOW_THIRDPARTY to allow third-party form discovery
"""

load_dotenv()

SEEN_PATH = ".seen_roots.json"


def apex(host_or_url: str) -> str:
    netloc = urlparse(host_or_url).netloc or host_or_url
    netloc = netloc.split(":")[0]
    parts = netloc.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc


BRIDGE_DOMAINS = {d.strip() for d in os.getenv("BRIDGE_DOMAINS", "").split(",") if d.strip()}
HARD_BLOCKLIST = {d.strip() for d in os.getenv("HARD_BLOCKLIST", "").split(",") if d.strip()}


def is_bridge(url: str) -> bool:
    return apex(url) in BRIDGE_DOMAINS


def is_hard_blocked(url: str) -> bool:
    return apex(url) in HARD_BLOCKLIST


ANCHOR_KEYS = [
    "website",
    "visit website",
    "official site",
    "order online",
    "order direct",
    "menu",
    "reservations",
]


def extract_official_site_from_bridge(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    cands: list[str] = []
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True).lower()
        if any(k in txt for k in ANCHOR_KEYS):
            cands.append(urljoin(base_url, a["href"]))
    for tag in soup.find_all("meta", property="og:url"):
        url = tag.get("content")
        if url:
            cands.append(url)
    for tag in soup.find_all("link", rel=lambda x: x and "canonical" in x.lower()):
        href = tag.get("href")
        if href:
            cands.append(urljoin(base_url, href))
    if apex(base_url) == "instagram.com":
        m = re.search(r'"external_url"\s*:\s*"(https?://[^"]+)"', html)
        if m:
            cands.append(m.group(1))
    return cands


def rank_and_pick(candidates: list[str], seen_roots: set[str], blocklist: list[str]) -> str | None:
    best = None
    best_score = -999
    for u in candidates:
        d = apex(u)
        if d in BRIDGE_DOMAINS or d in HARD_BLOCKLIST:
            continue
        if is_blocked_domain(u, blocklist):
            continue
        score = 0
        if re.search(r"\.(com|net|org)(/|$)", u):
            score += 2
        if d not in seen_roots:
            score += 1
        if score > best_score:
            best_score = score
            best = u
    return best


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def check_cse_quota(api_key: str, cx: str):
    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cx, "q": "quota check", "num": 1},
            timeout=10,
        )
    except requests.RequestException:
        return
    if resp.status_code in (429, 403):
        print("クォータ不足")
        raise SystemExit(1)


def _is_html(url: str) -> tuple[bool, int]:
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        status = r.status_code
        if status in (401, 403, 429):
            return False, status
        if status >= 400:
            return False, status
        ct = r.headers.get("content-type", "").lower()
        return ct.startswith("text/html"), status
    except requests.RequestException:
        return False, 0


def mini_site_matcha(cse: CSEClient, home: str) -> bool:
    host = canon_url(home).split("//")[-1].split("/")[0]
    q = f'site:{host} (matcha OR 抹茶)'
    try:
        data = cse.search(q, start=1, num=10, safe="off", lr="lang_en", cr="countryUS", gl="us")
        items = data.get("items") or []
        for it in items:
            link = it.get("link") or ""
            if link and host in link and not is_media_or_platform(link):
                return True
    except DailyQuotaExceeded:
        pass
    except Exception:
        pass
    return False


def iter_cse_items(cse: CSEClient, query: str, num=10, start=1, max_pages=1):
    s = start
    for _ in range(max_pages):
        try:
            data = cse.search(
                query,
                start=s,
                num=num,
                safe="off",
                lr="lang_en",
                cr="countryUS",
                gl="us",
            )
        except DailyQuotaExceeded:
            break
        except Exception:
            break
        items = data.get("items") or []
        if not items:
            break
        for it in items:
            yield it
        s += num


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-bust", action="store_true")
    args = parser.parse_args(argv)
    env = EnvConfig()
    api_key = os.getenv("GOOGLE_API_KEY")
    cx = os.getenv("GOOGLE_CX")
    sheet_id = os.getenv("SHEET_ID")
    ws_name = os.getenv("GOOGLE_WORKSHEET_NAME", "抹茶営業リスト（カフェ）")
    target = int(os.getenv("TARGET_NEW", "100"))
    debug = bool(int(os.getenv("DEBUG", "0")))
    require_contact_on_snippet = bool(int(os.getenv("REQUIRE_CONTACT_ON_SNIPPET", "1")))
    if not (api_key and cx and sheet_id):
        raise SystemExit("GOOGLE_API_KEY / GOOGLE_CX / SHEET_ID を .env に設定してください。")

    check_cse_quota(api_key, cx)

    existing = load_existing_keys(sheet_id, ws_name)
    seen_homes = set(existing["homes"])
    seen_instas = set(existing["instas"])

    seen = load_json(SEEN_PATH, {"roots": []})
    seen_roots = set(seen.get("roots", []))

    settings = load_settings()
    blocklist_path = os.getenv("BLOCKLIST_FILE", "config/domain_blocklist.txt")
    domain_blocklist = load_domain_blocklist(blocklist_path)
    extra_env = os.getenv("EXCLUDE_DOMAINS", "")
    extra_env2 = os.getenv("EXCLUDE_DOMAINS_EXTRA", "")
    extra = [d.strip() for d in f"{extra_env},{extra_env2}".split(",") if d.strip()]
    domain_blocklist = sorted(set(domain_blocklist + extra))
    cache = load_cache()
    qb = QueryBuilder(blocklist=domain_blocklist)
    qb.set_phase(1)
    pc = PersistentCache()
    cache_wrap = Cache(env, phase=1, cache_bust=args.cache_bust)
    rt_block = RuntimeBlockList()
    hits = 0
    skip_reasons: dict[str, int] = {}
    blocked_domains: dict[str, int] = {}
    max_queries = int(os.getenv("MAX_QUERIES_PER_RUN", "120"))
    search_radius = float(os.getenv("SEARCH_RADIUS_KM", "25"))

    dynamic_negative_sites: set[str] = set()

    def add_negative_site(url: str):
        d = apex(url)
        if d and d not in BRIDGE_DOMAINS and d not in HARD_BLOCKLIST:
            dynamic_negative_sites.add(d)

    def wrap_query(q: str) -> str:
        parts = list(dynamic_negative_sites)[:8]
        if parts:
            return f"{q} " + " ".join(f"-site:{p}" for p in parts)
        return q

    state = RunState(
        target=target,
        max_queries=max_queries,
        max_rotations=int(os.getenv("MAX_ROTATIONS_PER_RUN", "8")),
        skip_rotate_threshold=env.SKIP_ROTATE_THRESHOLD,
        cache_burst_threshold=float(os.getenv("CACHE_BURST_THRESHOLD", "0.5")),
        phase_max=int(os.getenv("PHASE_MAX", "8")),
    )
    cse = CSEClient(api_key, cx, max_daily=int(os.getenv("MAX_DAILY_CSE_QUERIES", "100")))
    queries = qb.build_queries()
    qi = 0

    def on_skip(url: str, reason: str):
        nonlocal queries, qi, cache_wrap
        print(f"skip[{url}]: {reason}")
        state.record_skip(reason)
        rotated = qb.record_skip()
        if state.should_rotate():
            rotated = True
        pc.record(url, "skip", reason)
        rt_block.record(url, reason)
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        if reason == "blocked_domain":
            host = canon_url(url).split("//")[-1].split("/")
            host = host[0]
            blocked_domains[host] = blocked_domains.get(host, 0) + 1
        if reason in {"cache-hit", "already-in-sheet", "already-seen root", "dup insta", "blocked_domain", "not US independent cafe"}:
            add_negative_site(url)
        if rotated:
            phase = state.escalate_phase()
            qb.set_phase(phase)
            cache_wrap = Cache(env, phase=phase, cache_bust=args.cache_bust)
            print(f"[ROTATE] consecutive_skips={state.skip_rotate_threshold} phase={phase}")
            queries = qb.build_queries()
            qi = 0
        return False

    def on_add(url: str, name: str):
        state.record_add()
        qb.record_hit()
        pc.record(url, "add")
        pc.record_add(url, name)

    stop = False
    reason = ""
    try:
        while state.queries < max_queries and not stop:
            if qi >= len(queries):
                phase = state.escalate_phase()
                qb.set_phase(phase)
                cache_wrap = Cache(env, phase=phase, cache_bust=args.cache_bust)
                queries = qb.build_queries()
                qi = 0
                if not queries:
                    stop, reason = state.should_stop(no_candidates=True)
                    break
            q = queries[qi]
            q = f"{q} {BASE_NEG}".strip()
            q = wrap_query(q)
            print(f'query(wrapped): "{q}"')
            state.queries += 1
            for it in iter_cse_items(cse, q, num=10, start=1, max_pages=3):
                raw = (it.get("link") or "").strip()
                home = normalize_candidate_url(raw)
                if not home:
                    if on_skip(raw, "blocked or empty"):
                        return
                    continue
                if is_hard_blocked(home):
                    if on_skip(home, "hard-blocked"):
                        return
                    continue
                snippet = it.get("snippet") or ""
                title = it.get("title") or ""
                if is_bridge(home):
                    bridge_html = http_get(home)
                    bridge_txt = bridge_html.text if (bridge_html and bridge_html.text) else ""
                    if not bridge_txt:
                        if on_skip(home, "no_html"):
                            return
                        continue
                    cands = extract_official_site_from_bridge(bridge_txt, home)
                    official = rank_and_pick(cands, seen_roots, domain_blocklist)
                    if not official:
                        if on_skip(home, "no official site"):
                            return
                        continue
                    print(f"bridge-followed[{apex(home)}]: {home} -> {official}")
                    home = normalize_candidate_url(official)
                    if not home:
                        if on_skip(official, "blocked or empty"):
                            return
                        continue
                    if is_hard_blocked(home):
                        if on_skip(home, "hard-blocked"):
                            return
                        continue
                    snippet = ""
                    title = ""
                host = canon_url(home).split("//")[-1].split("/")[0]
                if rt_block.is_blocked(home):
                    if on_skip(home, "runtime_block"):
                        return
                    continue
                if is_blocked_domain(home, domain_blocklist) or is_blocked_host(cache, host):
                    mark_seen(cache, home)
                    if on_skip(home, "blocked_domain"):
                        save_cache(cache)
                        return
                    continue
                if cache_wrap.seen(home) or has_seen(cache, home) or pc.seen(home):
                    if on_skip(home, "cache-hit"):
                        return
                    continue
                mark_seen(cache, home)
                if home in seen_roots:
                    if on_skip(home, "already-seen root"):
                        return
                    continue
                if home in seen_homes:
                    if on_skip(home, "already-in-sheet"):
                        return
                    continue
                if snippet and not snippet_accepts(home, snippet):
                    seen_roots.add(home)
                    if on_skip(home, "snippet_not_matcha_context"):
                        return
                    continue
                hits += 1
                ok_html, status_code = _is_html(home)
                if not ok_html:
                    reason = "no_html"
                    if status_code == 401:
                        reason = "status_401"
                    elif status_code == 403:
                        reason = "status_403"
                    seen_roots.add(home)
                    if on_skip(home, reason):
                        return
                    continue
                r = http_get(home)
                html = r.text if (r and r.text) else ""
                if not html:
                    seen_roots.add(home)
                    if on_skip(home, "no_html"):
                        return
                    continue
                if requires_js(html):
                    seen_roots.add(home)
                    if on_skip(home, "js_required"):
                        return
                    continue
                ig, emails, form = extract_contacts(home, html)
                extra_contacts = extract_contact_endpoints(html, home)
                if not form and extra_contacts.get("form_urls"):
                    form = extra_contacts["form_urls"][0]
                if not emails and extra_contacts.get("emails"):
                    emails = extra_contacts["emails"]
                menus = list(find_menu_links(html, home, limit=3))
                how, evidence = verify_matcha(menus, ig, html_text(html))
                ok = bool(how)
                if not ok:
                    ok = mini_site_matcha(cse, home)
                if not ok:
                    seen_roots.add(home)
                    if on_skip(home, "no matcha evidence"):
                        return
                    continue
                if not is_us_cafe_site(home, html):
                    seen_roots.add(home)
                    if on_skip(home, "not US independent cafe"):
                        return
                    continue
                if require_contact_on_snippet and not (ig or emails or form):
                    seen_roots.add(home)
                    if on_skip(home, "no contacts found"):
                        return
                    continue
                ig_key = canon_url(ig) if ig else ""
                if ig_key and ig_key in seen_instas:
                    seen_roots.add(home)
                    if on_skip(home, "dup insta"):
                        return
                    continue
                brand = guess_brand(home, html, title)
                row = {
                    "店名": brand,
                    "国": "US",
                    "公式サイトURL": home,
                    "Instagramリンク": ig,
                    "問い合わせアドレス": (emails[0] if emails else ""),
                    "問い合わせフォームURL": form,
                }
                try:
                    append_row_in_order(sheet_id, ws_name, row)
                    on_add(home, brand)
                    seen_homes.add(home)
                    if ig_key:
                        seen_instas.add(ig_key)
                    seen_roots.add(home)
                    print(f"[ADD] {brand} -> {home} contacts: ig={ig or '-'} email={(emails[0] if emails else '-')} form={form or '-'} (累計 added={state.added})")
                    stop, reason = state.should_stop()
                    if stop:
                        save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
                        save_cache(cache)
                        print(format_stop(reason, state))
                        return
                except Exception as e:
                    print(f"[WARN] スプシ書き込み失敗: {home} -> {e}")
                    traceback.print_exc()
                    seen_roots.add(home)
                    if on_skip(home, "sheet write failure"):
                        return
            qi += 1
            stop, reason = state.should_stop()
            if stop:
                break
    except Exception as e:
        if debug:
            print(f"search_iter error: {e}")

    save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
    save_cache(cache)
    if not reason:
        stop, reason = state.should_stop()
    print(format_stop(reason, state))
    if skip_reasons:
        print("[SUMMARY] skip reasons:")
        for k, v in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")
    if blocked_domains:
        print("[SUMMARY] blocked domains:")
        for k, v in sorted(blocked_domains.items(), key=lambda x: -x[1])[:10]:
            print(f"  {k}: {v}")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Crawl Summary\n")
            f.write(f"- Added: {state.added}\n")
            f.write(f"- Hits: {hits}\n")
            f.write(f"- Queries: {state.queries}\n")
            total = sum(skip_reasons.values())
            f.write(f"- Total Skips: {total}\n")
            for k, v in sorted(skip_reasons.items(), key=lambda x: -x[1])[:10]:
                f.write(f"- {k}: {v}\n")
            if blocked_domains:
                f.write("### Blocked domains\n")
                for k, v in sorted(blocked_domains.items(), key=lambda x: -x[1])[:10]:
                    f.write(f"- {k}: {v}\n")
            if qb.rotation_summary():
                f.write("### Rotations\n")
                for act, frm, to in qb.rotation_summary():
                    f.write(f"- {act}: {frm} -> {to}\n")


if __name__ == "__main__":
    main()
