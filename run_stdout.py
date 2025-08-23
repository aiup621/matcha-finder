import logging, runpy, sys
root = logging.getLogger()
for h in list(root.handlers):
    root.removeHandler(h)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
root.addHandler(sh)
root.setLevel("WARNING")
runpy.run_path("./pipeline.py", run_name="__main__")