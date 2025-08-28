import os, json, traceback, re, logging
import requests
from dotenv import load_dotenv
from cse_client import CSEClient, DailyQuotaExceeded
from sheet_io_v2 import append_row_in_order, load_existing_keys
from light_extract import (
    canon_url, http_get, html_text, is_media_or_platform,
    normalize_candidate_url, find_menu_links,
    extract_contacts, is_us_cafe_site, guess_brand, MATCHA_WORDS
)
from verify_matcha import verify_matcha
from blocklist import load_domain_blocklist, is_blocked_domain
from crawler_cache import load_cache, save_cache, has_seen, mark_seen, is_blocked_host
from config_loader import load_settings
from smart_search import QueryBuilder
from persistent_cache import PersistentCache

load_dotenv()

SEEN_PATH = ".seen_roots.json"  # 既に検証したルートを保存（同じ結果の再検証を避ける）

NEG_SITE_QUERY = ""

# スニペット判定用（ベーカリー単独は除外）
SNIPPET_CAFE_HINTS = re.compile(
    r"\b(cafe|coffee|tea|teahouse|boba|bubble\s*tea)\b|カフェ|コーヒー|珈琲|喫茶",
    re.I,
)

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path,"r",encoding="utf-8") as f: return json.load(f)
        except Exception: return default
    return default

def save_json(path, obj):
    try:
        with open(path,"w",encoding="utf-8") as f: json.dump(obj,f,ensure_ascii=False,indent=2)
    except Exception: pass

def check_cse_quota(api_key: str, cx: str):
    """Google CSE にテストクエリを送り、クォータを事前確認する"""
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

def snippet_ok(item, home: str) -> bool:
    # スニペットに matcha / 抹茶 があり、かつカフェ系ワードを含む場合のみ採用
    title = (item.get("title") or "") + " " + (item.get("snippet") or "")
    if is_media_or_platform(home):
        return False
    return bool(MATCHA_WORDS.search(title) and SNIPPET_CAFE_HINTS.search(title))

def mini_site_matcha(cse: CSEClient, home: str) -> bool:
    # サイト内簡易検索（site:host matcha）で補強。予算が少ないので最大1クエリのみ。
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
    """CSE 検索結果をページ送りで反復取得し、item を返す"""
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

def default_queries(qb: QueryBuilder):
    """Return a list with the current query from QueryBuilder."""
    return [qb.build()]

def main():
    api_key = os.getenv("GOOGLE_API_KEY")
    cx      = os.getenv("GOOGLE_CX")
    sheet_id= os.getenv("SHEET_ID")
    ws_name = os.getenv("GOOGLE_WORKSHEET_NAME","抹茶営業リスト（カフェ）")
    target  = int(os.getenv("TARGET_NEW","100"))
    debug   = bool(int(os.getenv("DEBUG","0")))
    require_contact_on_snippet = bool(int(os.getenv("REQUIRE_CONTACT_ON_SNIPPET","1")))
    if not (api_key and cx and sheet_id):
        raise SystemExit("GOOGLE_API_KEY / GOOGLE_CX / SHEET_ID を .env に設定してください。")

    check_cse_quota(api_key, cx)

    existing = load_existing_keys(sheet_id, ws_name)
    seen_homes = set(existing["homes"])
    seen_instas = set(existing["instas"])

    seen = load_json(SEEN_PATH, {"roots": []})
    seen_roots = set(seen.get("roots", []))

    # configuration and caches
    settings = load_settings()
    blocklist_path = os.getenv("BLOCKLIST_FILE", "config/domain_blocklist.txt")
    domain_blocklist = load_domain_blocklist(blocklist_path)
    extra = [d.strip() for d in os.getenv("EXCLUDE_DOMAINS", "").split(",") if d.strip()]
    domain_blocklist = sorted(set(domain_blocklist + extra))
    cache = load_cache()
    qb = QueryBuilder()
    pc = PersistentCache()
    skip_breaker = qb.rotate_threshold
    skip_streak = 0
    added = 0
    skip_reasons = {}
    cse = CSEClient(api_key, cx, max_daily=int(os.getenv("MAX_DAILY_CSE_QUERIES", "100")))
    # Limit how many CSE queries are issued per run. Can be overridden via the
    # MAX_QUERIES_PER_RUN environment variable.
    max_queries = int(os.getenv("MAX_QUERIES_PER_RUN", "120"))

    def on_skip(url: str, reason: str):
        nonlocal skip_streak
        qb.record_skip()
        pc.record(url, "skip", reason)
        skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
        skip_streak += 1
        if skip_streak >= skip_breaker:
            print(f"[ROTATE] consecutive_skips={skip_breaker}")
            skip_streak = 0
        return False

    def on_add(url: str, name: str):
        nonlocal skip_streak
        skip_streak = 0
        qb.record_hit()
        pc.record(url, "add")
        pc.record_add(url, name)

    # まず広域クエリをページ巡回しながら収集
    # base query covering nationwide search
    wide_q = os.getenv("WIDE_QUERY", qb.build())
    try:
        for it in iter_cse_items(cse, wide_q, num=10, start=1, max_pages=3):
            raw = (it.get("link") or "").strip()
            home = normalize_candidate_url(raw)
            if not home:
                if debug: print(f"skip[{raw}]: blocked or empty")
                if on_skip(raw, "blocked or empty"):
                    return
                continue
            host = canon_url(home).split("//")[-1].split("/")[0]
            if is_blocked_domain(home, domain_blocklist) or is_blocked_host(cache, host):
                if debug: print(f"skip[{home}]: blocked-domain")
                mark_seen(cache, home)
                if on_skip(home, "blocked-domain"):
                    save_cache(cache)
                    return
                continue
            if has_seen(cache, home) or pc.seen(home):
                if debug: print(f"skip[{home}]: cache-hit")
                if on_skip(home, "cache-hit"):
                    return
                continue
            mark_seen(cache, home)
            if home in seen_roots:
                if debug: print(f"skip[{home}]: already-seen root")
                if on_skip(home, "already-seen root"):
                    return
                continue
            if home in seen_homes:
                if debug: print(f"skip[{home}]: already-in-sheet")
                if on_skip(home, "already-in-sheet"):
                    return
                continue
            if not snippet_ok(it, home):
                if debug: print(f"skip[{home}]: snippet not matcha or platform")
                seen_roots.add(home)
                if on_skip(home, "snippet not matcha or platform"):
                    return
                continue

            # ランディング取得
            r = http_get(home)
            html = r.text if (r and r.text) else ""
            if not html:
                if debug: print(f"skip[{home}]: no html")
                seen_roots.add(home)
                if on_skip(home, "no html"):
                    return
                continue

            ig, emails, form = extract_contacts(home, html)
            menus = list(find_menu_links(html, home, limit=3))
            how, evidence = verify_matcha(menus, ig, html_text(html))
            ok = bool(how)
            if not ok:
                ok = mini_site_matcha(cse, home)

            if not ok:
                if debug: print(f"skip[{home}]: no matcha evidence")
                seen_roots.add(home)
                if on_skip(home, "no matcha evidence"):
                    return
                continue

            if not is_us_cafe_site(home, html):
                if debug: print(f"skip[{home}]: not US independent cafe")
                seen_roots.add(home)
                if on_skip(home, "not US independent cafe"):
                    return
                continue

            if require_contact_on_snippet and not (ig or emails or form):
                if debug: print(f"skip[{home}]: no contacts found")
                seen_roots.add(home)
                if on_skip(home, "no contacts found"):
                    return
                continue

            ig_key = canon_url(ig) if ig else ""
            if ig_key and ig_key in seen_instas:
                if debug: print(f"skip[{home}]: dup insta")
                seen_roots.add(home)
                if on_skip(home, "dup insta"):
                    return
                continue

            brand = guess_brand(home, html, it.get("title") or "")
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
                added += 1
                on_add(home, brand)
                seen_homes.add(home)
                if ig_key:
                    seen_instas.add(ig_key)
                seen_roots.add(home)
                print(
                    f"[ADD] {brand} -> {home} contacts: ig={ig or '-'} email={(emails[0] if emails else '-')} form={form or '-'} （累計 {added}）"
                )
                if added >= target:
                    save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
                    print("[DONE] 目標件数に到達。終了します。")
                    return
            except Exception as e:
                print(f"[WARN] スプシ書き込み失敗: {home} -> {e}")
                traceback.print_exc()
                seen_roots.add(home)
                if on_skip(home, "sheet write failure"):
                    return
    except Exception as e:
        if debug:
            print(f"search_iter error: {e}")


    save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
    save_cache(cache)
    print(f"[END] 追加 {added} 件で終了")
    if skip_reasons:
        print("[SUMMARY] skip reasons:")
        for k, v in sorted(skip_reasons.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Crawl Summary\n")
            f.write(f"- Added: {added}\n")
            total = sum(skip_reasons.values())
            f.write(f"- Total Skips: {total}\n")
            for k, v in sorted(skip_reasons.items(), key=lambda x: -x[1])[:10]:
                f.write(f"- {k}: {v}\n")


if __name__ == "__main__":
    main()
