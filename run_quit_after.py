import os, sys, runpy, threading, logging

LIMIT = int(os.getenv("MAX_RUNTIME_SEC","120"))

def _kill():
    try:
        logging.warning("time limit reached; stopping")
    finally:
        os._exit(0)

t = threading.Timer(LIMIT, _kill)
t.daemon = True
t.start()

# 可能なら標準出力ログに寄せる（pipeline側が上書きする場合あり）
root = logging.getLogger()
for h in list(root.handlers):
    root.removeHandler(h)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
root.addHandler(sh)
root.setLevel(os.getenv("LOG_LEVEL","INFO"))

print(f"SKIP_SHEETS={os.getenv('SKIP_SHEETS','0')}, TARGET_NEW={os.getenv('TARGET_NEW','')}", flush=True)

runpy.run_path("./pipeline.py", run_name="__main__")