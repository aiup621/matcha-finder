import os, json, traceback, re
from dotenv import load_dotenv
from cse_client import CSEClient, DailyQuotaExceeded
from sheet_io_v2 import append_row_in_order, load_existing_keys
from light_extract import (
    canon_root, canon_url, http_get, html_text, is_media_or_platform,
    is_blocked, normalize_candidate_url, find_menu_links, one_pdf_text_from,
    extract_contacts, is_us_cafe_site, guess_brand, MATCHA_WORDS
)

load_dotenv()

SEEN_PATH = ".seen_roots.json"  # 既に検証したルートを保存（同じ結果の再検証を避ける）

# スニペット判定用（ベーカリー単独は除外）
SNIPPET_CAFE_HINTS = re.compile(
    r"\b(cafe|coffee|tea|teahouse|boba|bubble\s*tea)\b|カフェ|コーヒー|珈琲|喫茶",
    re.I,
)

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)

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
        data = cse.search(q, start=1, num=10, safe="off", lr="lang_en", cr="countryUS")
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

def default_queries():
    # US に寄せるクエリ（繰り返しでもバリエーションが出るようランダム化）
    base = [
        "matcha latte cafe {kw} -yelp -ubereats -doordash -tripadvisor -opentable -facebook -linktr.ee",
        "matcha cafe {kw} -yelp -ubereats -doordash -tripadvisor -opentable -facebook -linktr.ee",
        "抹茶 カフェ {kw} -yelp -ubereats -tripadvisor -opentable -facebook -linktr.ee",
    ]
    states = [s.strip() for s in os.getenv("STATES","CA,NY,TX,FL,WA,MA,IL,CO,OR").split(",") if s.strip()]
    cities = {
        "CA": ["Los Angeles","San Francisco","San Diego","San Jose","Sacramento"],
        "NY": ["New York","Brooklyn","Queens","Buffalo","Rochester"],
        "TX": ["Houston","Dallas","Austin","San Antonio","Fort Worth"],
        "FL": ["Miami","Orlando","Tampa","Jacksonville","St Petersburg"],
        "WA": ["Seattle","Tacoma","Bellevue"],
        "MA": ["Boston","Cambridge","Worcester"],
        "IL": ["Chicago","Naperville","Evanston"],
        "CO": ["Denver","Boulder","Colorado Springs"],
        "OR": ["Portland","Eugene","Salem"],
    }
    out=[]
    for st in states:
        out += [tmpl.format(kw=st) for tmpl in base]
        for city in cities.get(st, [])[:5]:
            out += [tmpl.format(kw=f"{city} {st}") for tmpl in base]
    import random
    random.shuffle(out)
    return out

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

    existing = load_existing_keys(sheet_id, ws_name)
    seen_homes  = set(existing["homes"])
    seen_instas = set(existing["instas"])

    seen = load_json(SEEN_PATH, {"roots": []})
    seen_roots = set(seen.get("roots", []))

    queries = default_queries()
    added = 0
    cse = CSEClient(api_key, cx, max_daily=int(os.getenv("MAX_DAILY_CSE_QUERIES","100")))
    max_queries = int(os.getenv("MAX_QUERIES_PER_RUN", "50"))

    for idx, q in enumerate(queries):
        if idx >= max_queries:
            if debug:
                print("[STOP] per-run query cap reached")
            break
        try:
            data = cse.search(q, start=1, num=10, safe="off", lr="lang_en", cr="countryUS")
        except DailyQuotaExceeded:
            print("[STOP] Google CSE 日次上限/レート制限に到達。")
            break
        except Exception as e:
            if debug: print(f"search error: {e}")
            continue

        for it in (data.get("items") or []):
            raw = (it.get("link") or "").strip()
            home = normalize_candidate_url(raw)
            if not home:
                if debug: print(f"skip[{raw}]: blocked or empty")
                continue
            if home in seen_roots:
                if debug: print(f"skip[{home}]: already-seen root")
                continue
            if home in seen_homes:
                if debug: print(f"skip[{home}]: already-in-sheet")
                continue

            pagemap = it.get("pagemap") or {}
            meta_texts = []
            meta_ig = ""
            meta_emails = set()
            for mt in pagemap.get("metatags", []):
                if not isinstance(mt, dict):
                    continue
                for v in mt.values():
                    if not isinstance(v, str):
                        continue
                    meta_texts.append(v)
                    lv = v.lower()
                    if not meta_ig and "instagram.com" in lv:
                        meta_ig = canon_url(v)
                    if lv.startswith("mailto:"):
                        meta_emails.add(lv.replace("mailto:", "").split("?")[0])
                    for em in EMAIL_RE.findall(v):
                        meta_emails.add(em)
            for img in pagemap.get("cse_image", []):
                if not isinstance(img, dict):
                    continue
                src = img.get("src") or ""
                lv = src.lower()
                if not meta_ig and "instagram.com" in lv:
                    meta_ig = canon_url(src)
                if lv.startswith("mailto:"):
                    meta_emails.add(lv.replace("mailto:", "").split("?")[0])
                for em in EMAIL_RE.findall(src):
                    meta_emails.add(em)
            meta_text = " ".join(meta_texts)
            meta_hit = bool(MATCHA_WORDS.search(meta_text) or "instagram.com" in meta_text.lower())

            # 1) スニペット/メタタグ事前判定（US向け/プラットフォーム除外）
            if not (snippet_ok(it, home) or meta_hit):
                if debug: print(f"skip[{home}]: snippet/metatag not matcha")
                seen_roots.add(home)
                continue

            # 2) ランディング取得
            r = http_get(home)
            html = r.text if (r and r.text) else ""
            if not html:
                if debug: print(f"skip[{home}]: no html")
                seen_roots.add(home)
                continue

            # 3) マッチャ証拠：本文/メニュー/PDF or サイト内ミニ検索
            ok = bool(MATCHA_WORDS.search(html_text(html)))
            if not ok:
                for m in find_menu_links(html, home, limit=3):
                    r2 = http_get(m)
                    if r2 and r2.text and MATCHA_WORDS.search(html_text(r2.text)):
                        ok = True; break
            if not ok:
                pdf_text = one_pdf_text_from(html, home)
                if pdf_text and MATCHA_WORDS.search(pdf_text.lower()):
                    ok = True
            if not ok:
                ok = mini_site_matcha(cse, home)

            if not ok:
                if debug: print(f"skip[{home}]: no matcha evidence (html+menu+pdf+site)")
                seen_roots.add(home)
                continue

            # 4) US の独立カフェらしさ
            if not is_us_cafe_site(home, html):
                if debug: print(f"skip[{home}]: not US independent cafe")
                seen_roots.add(home)
                continue

            # 5) 連絡先抽出（必須）
            ig = meta_ig
            emails = sorted(meta_emails)
            form = ""
            if not (ig or emails):
                ig, emails, form = extract_contacts(home, html)
            if require_contact_on_snippet and not (ig or emails or form):
                if debug: print(f"skip[{home}]: no contacts found")
                seen_roots.add(home)
                continue

            # 6) IG 重複／シート重複チェック
            ig_key = canon_url(ig) if ig else ""
            if ig_key and ig_key in seen_instas:
                if debug: print(f"skip[{home}]: dup insta")
                seen_roots.add(home)
                continue

            brand = guess_brand(home, html, it.get("title") or "")
            row = {
                "店名": brand,
                "国": "US",
                "公式サイトURL": home,
                "Instagramリンク": ig,
                "問い合わせアドレス": (emails[0] if emails else ""),
                "問い合わせフォームURL": form
            }

            try:
                append_row_in_order(sheet_id, ws_name, row)
                added += 1
                seen_homes.add(home)
                if ig_key: seen_instas.add(ig_key)
                seen_roots.add(home)
                print(f"[ADD] {brand} -> {home} contacts: ig={ig or '-'} email={(emails[0] if emails else '-')} form={form or '-'} （累計 {added}）")
                if added >= target:
                    save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
                    print("[DONE] 目標件数に到達。終了します。")
                    return
            except Exception as e:
                print(f"[WARN] スプシ書き込み失敗: {home} -> {e}")
                traceback.print_exc()
                seen_roots.add(home)

    save_json(SEEN_PATH, {"roots": sorted(seen_roots)})
    print(f"[END] 追加 {added} 件で終了")


if __name__ == "__main__":
    main()
