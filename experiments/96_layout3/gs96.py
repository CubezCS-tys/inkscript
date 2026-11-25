"""Experiment 96's GPU session: experiment 94's gs94.py (copied 2026-11-10), pointed at this folder ($5 GPU cap;
code: prep94.py, prep96.py, yolo96.py, host96.sh; experiment 94's two models as the starting point).  gs91's lineage:
experiment 75's gpu_session.py imported unchanged, with its own session file, spend log and keeper.

    python3 gs96.py offers | start CARD|OFFER | status | budget MIN | stop [REASON]   (as gpu_session.py)
    python3 gs96.py upload LOCAL_DIR REMOTE_DIR        parallel scp of every file (4 streams), then a size check
    python3 gs96.py run 'CMD'                          start CMD on the host in the background (log: /work/job.log)
    python3 gs96.py follow PATTERN                     touch activity while a remote process matching PATTERN lives
    python3 gs96.py get REMOTE LOCAL                   scp a file back
    python3 gs96.py spent                              all exp-96 GPU sessions so far, $

Same rules as experiment 75 (datacenter, verified, reliability >= 99.5 %, >= 300 Mbps + link test, keeper, destroy by
`vastai destroy instance ID -y` and check none of ours is left); idle limit 20 minutes.  The lead rents the host
(agents' rentals are refused by the permission system); this file is then used for upload / run / follow / get.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "75_ocr_lab"))
import gpu_session as gs  # noqa: E402

TOTAL_CAP = 5.0
OUT = HERE / "out" / "gpu"
OUT.mkdir(parents=True, exist_ok=True)
gs.OUT = OUT
gs.SESSION = OUT / "gpu_session.json"
gs.SPEND = OUT / "gpu_spend.jsonl"
gs.ACTIVITY = OUT / "gpu_last_activity"
gs.RATE = OUT / "gpu_rate.json"
gs.BAD = OUT / "gpu_bad_machines.json"
gs.IDLE_MIN = 20.0
gs.DISK_GB = 150                                   # ~3 GB of PDFs, ~14 GB of page images, checkpoints
# rendering and the YOLO loaders want >= 16 real CPUs
gs.QUERY = gs.QUERY.replace("cpu_ram>=32", "cpu_ram>=96 cpu_cores_effective>=16").replace("disk_space>=80", "disk_space>=150")
if not gs.BAD.exists() and (HERE.parent / "75_ocr_lab/out/gpu_bad_machines.json").exists():
    gs.BAD.write_text((HERE.parent / "75_ocr_lab/out/gpu_bad_machines.json").read_text())


def spent_total() -> float:
    """Every ended exp-96 session's cost plus the open one's so far."""
    tot = 0.0
    for f in OUT.glob("gpu_session_*_ended.json"):
        tot += json.loads(f.read_text()).get("usd", 0.0)
    s = gs.session()
    if s:
        tot += gs.spent(s)
    return tot


def _closed_total() -> float:
    return sum(json.loads(f.read_text()).get("usd", 0.0) for f in OUT.glob("gpu_session_*_ended.json"))


gs.CAP_USD = TOTAL_CAP - _closed_total()


def _spawn_keeper():
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "keeper"], stdin=subprocess.DEVNULL,
                         stdout=open(OUT / "gpu_keeper.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
    s = gs.session()
    s["keeper_pid"] = p.pid
    gs.SESSION.write_text(json.dumps(s, indent=1))


def upload_workers(s: dict):
    """Our code and a setup script in place of the lab's workers (start() runs workers/setup_gpu.sh)."""
    import tarfile
    tgz = OUT / "code96.tgz"
    setup = OUT / "setup_gpu96.sh"
    setup.write_text("#!/bin/bash\ncd /work && bash host96.sh setup\necho SETUP_DONE\n")
    with tarfile.open(tgz, "w:gz") as t:
        for f in ("prep96.py", "yolo96.py", "host96.sh"):
            t.add(HERE / f, arcname=f)
        t.add(HERE.parent / "94_layout2/prep94.py", arcname="prep94.py")
        t.add(setup, arcname="workers/setup_gpu.sh")
        t.add(HERE.parent / "94_layout2/out/gpu/run_lay/best.pt", arcname="init/lay94.pt")
        t.add(HERE.parent / "94_layout2/out/gpu/run_line/best.pt", arcname="init/line94.pt")
    gs.scp_to(s, str(tgz), "/work/code96.tgz")
    subprocess.run(gs.ssh_base(s) + ["cd /work && tar xzf code96.tgz"], check=True, timeout=120)


gs._spawn_keeper = _spawn_keeper
gs.upload_workers = upload_workers


def upload(local: str, remote: str, streams: int = 4):
    s = gs.session()
    files = sorted(p for p in Path(local).iterdir() if p.is_file())
    subprocess.run(gs.ssh_base(s) + [f"mkdir -p {remote}"], check=True, timeout=60)
    groups = [files[k::streams] for k in range(streams)]
    t0 = time.time()
    procs = [subprocess.Popen(["scp", "-q", "-i", gs.KEY, "-P", str(s["port"]), "-o", "StrictHostKeyChecking=accept-new",
                               *map(str, g), f"root@{s['host']}:{remote}/"]) for g in groups if g]
    while any(p.poll() is None for p in procs):
        gs.touch()
        time.sleep(20)
    if any(p.returncode for p in procs):
        raise SystemExit("an scp stream failed")
    mb = sum(p.stat().st_size for p in files) / 1e6
    el = time.time() - t0
    r = subprocess.run(gs.ssh_base(s) + [f"du -sb {remote} | cut -f1"], capture_output=True, text=True, timeout=60)
    gs.log(dict(event="upload", files=len(files), mb=round(mb, 1), seconds=round(el), mb_s=round(mb / el, 2),
                remote_bytes=r.stdout.strip()))
    print(f"uploaded {len(files)} files, {mb:.0f} MB in {el:.0f} s ({mb / el:.1f} MB/s); remote {r.stdout.strip()} bytes")


def run(cmd: str):
    s = gs.session()
    gs.touch()
    subprocess.run(gs.ssh_base(s) + [f"cd /work && (setsid nohup bash -c {json.dumps(cmd)} > /work/job.log 2>&1 < /dev/null &)"],
                   check=True, timeout=60)


def follow(pattern: str, every: int = 60):
    """Touch activity while the remote job lives; print the log's last line each time.  PATTERN must be a bracket
    pattern ('[h]ost96.sh') so pgrep never matches its own shell."""
    if "[" not in pattern:
        raise SystemExit("follow needs a bracket pattern, e.g. '[h]ost96.sh'")
    s = gs.session()
    while True:
        r = subprocess.run(gs.ssh_base(s) + [f"pgrep -f {json.dumps(pattern)} >/dev/null && echo ALIVE; tail -n 1 /work/job.log"],
                           capture_output=True, text=True, timeout=120)
        alive = "ALIVE" in r.stdout
        gs.touch()
        print(time.strftime("%H:%M:%S"), f"${spent_total():.2f}", r.stdout.replace("ALIVE\n", "").strip()[-200:], flush=True)
        if not alive:
            return
        time.sleep(every)


def get(remote: str, local: str):
    gs.scp_from(gs.session(), remote, local, timeout=3600)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "status"
    if c == "upload":
        upload(sys.argv[2], sys.argv[3])
    elif c == "run":
        run(sys.argv[2])
    elif c == "follow":
        follow(sys.argv[2])
    elif c == "get":
        get(sys.argv[2], sys.argv[3])
    elif c == "spent":
        print(f"exp 96 GPU: ${spent_total():.3f} of ${TOTAL_CAP}")
    elif c == "start":
        if TOTAL_CAP - spent_total() < 1.0:
            raise SystemExit("less than $1 of the $5 GPU cap left")
        gs.start(sys.argv[2])
    elif c == "offers":
        gs.offers()
    elif c == "status":
        gs.status()
    elif c == "budget":
        sys.exit(0 if gs.budget(float(sys.argv[2])) else 1)
    elif c == "ssh":
        gs.ssh_cmd(sys.argv[2])
    elif c == "stop":
        gs.stop(" ".join(sys.argv[2:]) or "exp 96: done with the host")
    elif c == "keeper":
        gs.keeper()
    elif c == "touch":
        gs.touch()
    else:
        raise SystemExit(__doc__)
