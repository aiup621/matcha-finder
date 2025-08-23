# debug_run.py
import os, sys, runpy, faulthandler, cProfile, pstats, time
os.makedirs("logs", exist_ok=True)
ts = time.strftime("%Y%m%d-%H%M%S")
hang_path = os.path.join("logs", f"hangdump-{ts}.log")
prof_path = os.path.join("logs", f"run-{ts}.prof")
txt_path  = os.path.join("logs", f"profile-top-{ts}.txt")

# ハング時のスタックダンプ（全スレッド）を定期出力
sec = int(os.getenv("HANG_DUMP_SEC","45"))
f = open(hang_path, "w", encoding="utf-8")
faulthandler.enable(file=f, all_threads=True)
faulthandler.dump_traceback_later(sec, repeat=True, file=f)

# プロファイル
pr = cProfile.Profile()
try:
    pr.enable()
    runpy.run_path("./pipeline.py", run_name="__main__")
finally:
    faulthandler.cancel_dump_traceback_later()
    pr.disable()
    pr.dump_stats(prof_path)
    with open(txt_path, "w", encoding="utf-8") as out:
        p = pstats.Stats(pr, stream=out).sort_stats("cumtime")
        p.print_stats(40)
    f.close()
    print(f"[debug] hang dump: {hang_path}")
    print(f"[debug] profile raw: {prof_path}")
    print(f"[debug] profile top: {txt_path}")