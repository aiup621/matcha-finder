import os, json, traceback, re, random
import requests
from pathlib import Path
from dotenv import load_dotenv
from cse_client import CSEClient, DailyQuotaExceeded
from sheet_io_v2 import append_row_in_order, load_existing_keys
from light_extract import (
    canon_url, http_get, html_text, is_media_or_platform,
    normalize_candidate_url, find_menu_links,
    extract_contacts, is_us_cafe_site, guess_brand, MATCHA_WORDS
)
from verify_matcha import verify_matcha

load_dotenv()

SEEN_PATH = ".seen_roots.json"  # 既に検証したルートを保存（同じ結果の再検証を避ける）

# Google CSE で除外したいノイズドメイン
# Google CSE で除外したいノイズドメイン
EXCLUDE_SITES = [
    # SNS / UGC / メディア
    "instagram.com", "tiktok.com", "reddit.com", "pinterest.com",
    "linkedin.com", "x.com", "quora.com", "flickr.com", "goodreads.com",
    "timeout.com", "eater.com", "theinfatuation.com", "sfchronicle.com",
    "sacbee.com", "king5.com", "thenewstribune.com", "wanderlog.com",
    "trip.com",
    # デリバリー / モール / 求人 / 注文ホスティング等
    "yelp.com", "ubereats.com", "doordash.com", "postmates.com",
    "seamless.com", "grubhub.com", "mercato.com", "order.online",
    "toasttab.com", "toast.site", "orderexperience.net", "appfront.app",
    "res-menu.com", "craverapp.com", "square.site", "mapquest.com",
    "indeed.com", "glassdoor.com",
    # 量販 / EC / ティーブランド等
    "amazon.com", "walmart.com", "samsclub.com", "sayweee.com",
    "centralmarket.com", "uwajimaya.com", "jadeleafmatcha.com",
    "isshikimatcha.com", "cuzenmatcha.com", "senbirdtea.com",
    # チェーン店
    "starbucks.com", "starbucksreserve.com", "bluebottlecoffee.com",
    "peets.com", "dutchbros.com", "arabicacoffeeus.com",
    "85cbakerycafe.com", "parisbaguette.com", "lalalandkindcafe.com",
    "nanasgreentea.com", "nanasgreenteaus.com", "chachamatcha.com",
    "kettl.co", "matchaful.com",
]
NEG_SITE_QUERY = " " + " ".join(f"-site:{d}" for d in EXCLUDE_SITES)

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

def _region_queries(base_queries):
    cfg_path = Path(__file__).resolve().parent / "config" / "regions.json"
    try:
        with open(cfg_path, encoding="utf-8") as f:
            regions = json.load(f)
    except Exception:
        regions = {}

    states_env = [s.strip() for s in os.getenv("STATES", "").split(",") if s.strip()]
    states = states_env or list(regions.keys())
    random.shuffle(states)
    state_sample = int(os.getenv("STATE_SAMPLE", "5"))
    states = states[:state_sample]
    city_sample = int(os.getenv("CITY_SAMPLE", "5"))

    out = []
    for st in states:
        out += [tmpl.format(kw=st) for tmpl in base_queries]
        cities = regions.get(st, [])
        random.shuffle(cities)
        for city in cities[:city_sample]:
            out += [tmpl.format(kw=f"{city} {st}") for tmpl in base_queries]
    random.shuffle(out)
    return out

def default_queries():
    base = [
        f"(\"matcha latte\" OR \"matcha menu\" OR \"抹茶 ラテ\" OR \"抹茶 メニュー\") (cafe OR \"coffee house\" OR \"tea house\" OR bakery) {{kw}}{NEG_SITE_QUERY}"
    ]
    return _region_queries(base)

def fallback_queries():
    base = [
        f"(matcha OR 抹茶) (dessert cafe OR bubble tea shop) {{kw}}{NEG_SITE_QUERY}"
    ]
    return _region_queries(base)

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
    seen_homes  = set(existing["homes"])
    seen_instas = set(existing["instas"])

    seen = load_json(SEEN_PATH, {"roots": []})
    seen_roots = set(seen.get("roots", []))

    added = 0
    cse = CSEClient(api_key, cx, max_daily=int(os.getenv("MAX_DAILY_CSE_QUERIES","100")))
    # Limit how many CSE queries are issued per run. Can be overridden via
    # the MAX_QUERIES_PER_RUN environment variable.
    max_queries = int(os.getenv("MAX_QUERIES_PER_RUN", "120"))
    skip_breaker = int(os.getenv("SKIP_BREAKER", "60"))
    skip_streak = 0
    fallback_mode = False
    queries_run = 0

    def on_skip():
        nonlocal skip_streak, fallback_mode
        skip_streak += 1
        if skip_streak >= skip_breaker:
            if not fallback_mode:
                fallback_mode = True
                skip_streak = 0
                print("[INFO] switching to fallback queries")
            else:
                save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
                print("[STOP] too many consecutive skips")
                return True
        return False

    def on_add():
        nonlocal skip_streak
        skip_streak = 0

    def run_query_batch(q_list):
        nonlocal added, fallback_mode, queries_run
        for q in q_list:
            if queries_run >= max_queries:
                if debug:
                    print("[STOP] per-run query cap reached")
                return True
            queries_run += 1
            try:
                data = cse.search(q, start=1, num=10, safe="off", lr="lang_en", cr="countryUS", gl="us")
            except DailyQuotaExceeded:
                print("[STOP] Google CSE 日次上限/レート制限に到達。")
                return True
            except Exception as e:
                if debug: print(f"search error: {e}")
                continue

            for it in (data.get("items") or []):
                raw = (it.get("link") or "").strip()
                home = normalize_candidate_url(raw)
                if not home:
                    if debug: print(f"skip[{raw}]: blocked or empty")
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue
                if home in seen_roots:
                    if debug: print(f"skip[{home}]: already-seen root")
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue
                if home in seen_homes:
                    if debug: print(f"skip[{home}]: already-in-sheet")
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue

                if not snippet_ok(it, home):
                    if debug: print(f"skip[{home}]: snippet not matcha or platform")
                    seen_roots.add(home)
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue

                r = http_get(home)
                html = r.text if (r and r.text) else ""
                if not html:
                    if debug: print(f"skip[{home}]: no html")
                    seen_roots.add(home)
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
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
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue

                if not is_us_cafe_site(home, html):
                    if debug: print(f"skip[{home}]: not US independent cafe")
                    seen_roots.add(home)
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue

                if require_contact_on_snippet and not (ig or emails or form):
                    if debug: print(f"skip[{home}]: no contacts found")
                    seen_roots.add(home)
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
                    continue

                ig_key = canon_url(ig) if ig else ""
                if ig_key and ig_key in seen_instas:
                    if debug: print(f"skip[{home}]: dup insta")
                    seen_roots.add(home)
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
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
                    on_add()
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
                        return True
                except Exception as e:
                    print(f"[WARN] スプシ書き込み失敗: {home} -> {e}")
                    traceback.print_exc()
                    seen_roots.add(home)
                    if on_skip():
                        return True
                    if fallback_mode:
                        return False
        return False

    # まず広域クエリをページ巡回しながら収集
    wide_q = os.getenv(
        "WIDE_QUERY",
        f"matcha cafe{NEG_SITE_QUERY}",
    )
    try:
        for it in iter_cse_items(cse, wide_q, num=10, start=1, max_pages=3):
            raw = (it.get("link") or "").strip()
            home = normalize_candidate_url(raw)
            if not home:
                if debug: print(f"skip[{raw}]: blocked or empty")
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue
            if home in seen_roots:
                if debug: print(f"skip[{home}]: already-seen root")
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue
            if home in seen_homes:
                if debug: print(f"skip[{home}]: already-in-sheet")
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue
            if not snippet_ok(it, home):
                if debug: print(f"skip[{home}]: snippet not matcha or platform")
                seen_roots.add(home)
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue

            # ランディング取得
            r = http_get(home)
            html = r.text if (r and r.text) else ""
            if not html:
                if debug: print(f"skip[{home}]: no html")
                seen_roots.add(home)
                if on_skip():
                    return
                if fallback_mode:
                    break
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
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue

            if not is_us_cafe_site(home, html):
                if debug: print(f"skip[{home}]: not US independent cafe")
                seen_roots.add(home)
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue

            if require_contact_on_snippet and not (ig or emails or form):
                if debug: print(f"skip[{home}]: no contacts found")
                seen_roots.add(home)
                if on_skip():
                    return
                if fallback_mode:
                    break
                continue

            ig_key = canon_url(ig) if ig else ""
            if ig_key and ig_key in seen_instas:
                if debug: print(f"skip[{home}]: dup insta")
                seen_roots.add(home)
                if on_skip():
                    return
                if fallback_mode:
                    break
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
                on_add()
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
                if on_skip():
                    return
                if fallback_mode:
                    break
    except Exception as e:
        if debug:
            print(f"search_iter error: {e}")

    # 広域クエリで30件未満、またはスキップが多い場合は州別クエリで補完
    if added < 30 or fallback_mode:
        initial_fallback = fallback_mode
        queries = fallback_queries() if fallback_mode else default_queries()
        if run_query_batch(queries):
            return
        if fallback_mode and not initial_fallback:
            if run_query_batch(fallback_queries()):
                return

    save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
    print(f"[END] 追加 {added} 件で終了")


if __name__ == "__main__":
    main()
