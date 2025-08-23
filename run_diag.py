# run_diag.py
import os, runpy, socket, importlib, logging, threading

# 文字化け/IO安全
os.environ.setdefault("PYTHONUTF8", "1")

# tqdm の監視スレッドを無効化（進捗バー自体は使えます）
try:
    import tqdm
    tqdm.tqdm.monitor_interval = 0
except Exception:
    pass

# ---- ネットワークの既定タイムアウトを強制 ----
socket.setdefaulttimeout(int(os.getenv("SOCKET_TIMEOUT","20")))

# requests にデフォルト timeout を注入（指定が無い呼び出しへ）
try:
    import requests
    _orig = requests.Session.request
    def _patched(self, method, url, **kw):
        kw.setdefault("timeout", int(os.getenv("REQUESTS_TIMEOUT","15")))
        return _orig(self, method, url, **kw)
    requests.Session.request = _patched
except Exception:
    pass

# Sheets 追記にタイムアウト＆ログ（sheet_io.append_rows_batched を包む）
try:
    sio = importlib.import_module("sheet_io")
    if hasattr(sio, "append_rows_batched"):
        _orig_append = sio.append_rows_batched
        APP_T = int(os.getenv("APPEND_TIMEOUT","45"))
        def _wrap_append(rows, *a, **kw):
            log = logging.getLogger(__name__)
            try:
                n = len(rows)
            except Exception:
                n = "?"
            log.info(f"[diag] append_rows_batched start: {n} rows (timeout {APP_T}s)")
            res = [None]; err = [None]; done = threading.Event()
            def _run():
                try:
                    res[0] = _orig_append(rows, *a, **kw)
                except Exception as e:
                    err[0] = e
                finally:
                    done.set()
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            if not done.wait(APP_T):
                log.warning(f"[diag] append_rows_batched timed out after {APP_T}s")
                raise TimeoutError(f"append_rows_batched timed out after {APP_T}s")
            if err[0]:
                log.error(f"[diag] append_rows_batched error: {err[0]}")
                raise err[0]
            log.info("[diag] append_rows_batched done")
            return res[0]
        sio.append_rows_batched = _wrap_append
except Exception:
    pass

# 実行
runpy.run_path("./pipeline.py", run_name="__main__")