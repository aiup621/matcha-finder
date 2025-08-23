# run_nohang.py  — tqdm の監視スレッドを止めてから pipeline を実行
import os, runpy
os.environ.setdefault("PYTHONUTF8", "1")  # 文字化け/入出力の安全策
try:
    import tqdm
    # 監視スレッド(背景で動く進捗監視)を無効化。進捗バー自体は使えます。
    tqdm.tqdm.monitor_interval = 0
except Exception:
    pass
runpy.run_path("./pipeline.py", run_name="__main__")