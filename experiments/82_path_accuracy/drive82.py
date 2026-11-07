"""Experiment 82: run host stages back to back with no idle gap (the keeper destroys a host idle 20 minutes).

    python3 drive82.py genreader feats readers        (after gs82.py start; uploads out/learned/u1/model.pt first)
Per stage: start it, touch the activity file every 30 s ONLY while the stage runs, fetch /work/out as a tarball into
out/host/ when it ends; stop at the first failed stage.  Never touches after the last stage: the lead or `gs82.py stop`
ends the session.
"""
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.argv, stages = sys.argv[:1], sys.argv[1:]
import gs82  # noqa: E402

gs = gs82.gs


def sh(cmd, timeout=600):
    return subprocess.run(gs.ssh_base(gs.session()) + [cmd], capture_output=True, text=True, timeout=timeout).stdout


def fetch():
    sh("cd /work && tar czf /work/out82.tgz out")
    (HERE / "out/host").mkdir(parents=True, exist_ok=True)
    gs.scp_from(gs.session(), "/work/out82.tgz", str(HERE / "out/host/out82.tgz"), timeout=3600)
    subprocess.run(["tar", "xzf", "out82.tgz"], cwd=HERE / "out/host", check=True)


m = HERE / "out/learned/u1/model.pt"
if m.exists():
    sh("mkdir -p /work/out/u1")
    gs.scp_to(gs.session(), str(m), "/work/out/u1/model.pt")
for st in stages:
    gs82.run(f"bash experiments/82_path_accuracy/host82.sh {st}")
    t0 = time.time()
    while True:
        time.sleep(30)
        gs.touch()
        log = sh("tail -c 3000 /work/job.log", 120)
        if f"STAGE {st} DONE" in log:
            break
        if "Traceback" in log:
            print(log[-1500:], flush=True)
            fetch()
            raise SystemExit(f"stage {st} failed")
    print(time.strftime("%H:%M:%S"), f"stage {st} done in {(time.time() - t0) / 60:.1f} min, ${gs82.spent_total():.2f}", flush=True)
    fetch()
print("ALL DONE", flush=True)
