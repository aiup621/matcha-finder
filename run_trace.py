# run_trace.py  — 主要処理の時間計測・タイムアウト・任意でシート書込みスキップ
import os, time, runpy, socket, importlib, logging, threading, sys

# 文字化け防止
os.environ.setdefault("PYTHONUTF8", "1")

# tqdm 監視スレッドを無効化（進捗バー自体は使えます）。完全無効は TQDM_DISABLE=1 でも可
try:
    import tqdm
    tqdm.tqdm.monitor_interval = 0
except Exception:
    pass

# 追加の診断ログ（pipeline.log とは別に保険用）
os.makedirs("logs", exist_ok=True)
diag_logger = logging.getLogger("diag")
if not diag_logger.handlers:
    fh = logging.FileHandler(os.path.join("logs","diag-extra.log"), encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    diag_logger.setLevel(os.getenv("LOG_LEVEL","INFO"))
    diag_logger.addHandler(fh)
log = diag_logger

# SKIP_SHEETS が指定されている場合は早めに通知
_skip_env = os.getenv("SKIP_SHEETS", "").lower()
if _skip_env in ("1", "true", "yes", "on"):
    log.warning("[trace] SKIP_SHEETS=%s -> Sheets append disabled", _skip_env)

# ---- ネットワーク既定タイムアウト（requests を含む全体）----
socket.setdefaulttimeout(int(os.getenv("SOCKET_TIMEOUT","20")))
try:
    import requests
    _orig_req = requests.Session.request
    def _patched(self, method, url, **kw):
        kw.setdefault("timeout", int(os.getenv("REQUESTS_TIMEOUT","15")))
        return _orig_req(self, method, url, **kw)
    requests.Session.request = _patched
    log.info("[trace] requests patch: default timeout=%ss", os.getenv("REQUESTS_TIMEOUT","15"))
except Exception as e:
    log.warning("[trace] requests patch skipped: %r", e)

# ---- ラッパー: 時間計測してログ ----
def wrap_time(mod, name):
    try:
        f = getattr(mod, name)
    except Exception:
        return
    def wrapped(*a, **kw):
        t0 = time.time()
        log.info("[trace] enter %s", name)
        try:
            r = f(*a, **kw)
            return r
        finally:
            log.info("[trace] leave %s (%.2fs)", name, time.time()-t0)
    setattr(mod, name, wrapped)

# ---- search/crawl/verify/rules/sheet の要点を包む ----
def apply_wrappers():
    try:
        sg = importlib.import_module("search_google")
        # イテレータは1件ごとログ
        if hasattr(sg, "search_candidates_iter"):
            _orig_iter = sg.search_candidates_iter
            def _iter(*a, **kw):
                log.info("[trace] search_candidates_iter start")
                n=0; t0=time.time()
                for x in _orig_iter(*a, **kw):
                    n+=1
                    if n<=10:
                        log.info("[trace] candidate[%d]: %s", n, x)
                    yield x
                log.info("[trace] search_candidates_iter done: %d in %.2fs", n, time.time()-t0)
            sg.search_candidates_iter = _iter
        # 非イテレータ版があれば
        for fn in ("search_candidates",):
            wrap_time(sg, fn)
    except Exception as e:
        log.warning("[trace] search_google wrap skipped: %r", e)

    try:
        cs = importlib.import_module("crawl_site")
        for fn in ("fetch_site_safe","fetch_site"):
            wrap_time(cs, fn)
    except Exception as e:
        log.warning("[trace] crawl_site wrap skipped: %r", e)

    try:
        vm = importlib.import_module("verify_matcha")
        for fn in ("verify_matcha",):
            wrap_time(vm, fn)
    except Exception as e:
        log.warning("[trace] verify wrap skipped: %r", e)

    try:
        rules = importlib.import_module("rules")
        for fn in ("normalize_url","homepage_of","extract_brand_name_v2","extract_brand_name",
                   "instagram_handle","is_independent_strict","is_recent_enough"):
            if hasattr(rules, fn):
                wrap_time(rules, fn)
    except Exception as e:
        log.warning("[trace] rules wrap skipped: %r", e)

    # Sheets: open / existing / append にログとタイムアウト
    try:
        sio = importlib.import_module("sheet_io")
        for fn in ("open_sheet","get_existing_official_urls"):
            wrap_time(sio, fn)

        if hasattr(sio, "append_rows_batched"):
            _orig_append = sio.append_rows_batched
            APP_T = int(os.getenv("APPEND_TIMEOUT","45"))
            SKIP  = _skip_env in ("1", "true", "yes", "on")

            def _wrap_append(ws, rows, *a, **kw):
                try:
                    n = len(rows)
                except Exception:
                    n = "?"
                if SKIP:
                    log.warning("[trace] SKIP Sheets append (len=%s)", n)
                    return None

                log.info("[trace] append_rows_batched start: %s rows (timeout %ss)", n, APP_T)
                res = [None]; err = [None]; done = threading.Event()

                def _run():
                    try:
                        res[0] = _orig_append(ws, rows, *a, **kw)
                    except Exception as e:
                        err[0] = e
                    finally:
                        done.set()

                t = threading.Thread(target=_run, daemon=True)
                t.start()
                if not done.wait(APP_T):
                    log.warning("[trace] append_rows_batched timed out after %ss", APP_T)
                    raise TimeoutError(f"append_rows_batched timed out after {APP_T}s")
                if err[0]:
                    log.error("[trace] append_rows_batched error: %r", err[0])
                    raise err[0]
                log.info("[trace] append_rows_batched done")
                return res[0]

            sio.append_rows_batched = _wrap_append
    except Exception as e:
        log.warning("[trace] sheet_io wrap skipped: %r", e)

apply_wrappers()

# 実行
log.info("[trace] START pipeline")
try:
    runpy.run_path("./pipeline.py", run_name="__main__")
finally:
    log.info("[trace] END pipeline")