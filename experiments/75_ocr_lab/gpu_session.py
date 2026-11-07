"""Experiment 75: one rented GPU for a WORKING SESSION (several documents), with a minute-by-minute spend log and an
idle timer.  Run with any python3 (standard library only).

    python3 gpu_session.py offers                 cheapest offers that pass the rules (no rental)
    python3 gpu_session.py start OFFER_ID|CARD    (CARD e.g. RTX_5090: the cheapest passing offer at that moment) rent, link test (~20 MB up and down), upload workers, start setup,
                                                  start the keeper (spend log + idle timer + cap)
    python3 gpu_session.py status                 instance, minutes, spend so far, idle minutes, cap left
    python3 gpu_session.py touch                  mark activity (every inference run does this)
    python3 gpu_session.py budget MINUTES         would MINUTES more of rental stay under the cap? (exit 1 if not)
    python3 gpu_session.py worker ENGINE          the worker argv (JSON) for `labocr run --worker-json`
    python3 gpu_session.py ssh 'CMD'              run a fixed maintenance command on the host
    python3 gpu_session.py stop [REASON]          DESTROY the instance (never stop), verify none is left, log the end

Rules (owner, 2026-11-04): secure-cloud / datacenter offers only, reliability >= 99.5 %, inet up/down >= 300 Mbps,
32 GB+ (filter 31: Vast reports a 5090 as 31.8 GB) from the second session on (owner, 2026-11-04: prefer an RTX 5090, a 48 GB+ card when it passes the rules at a sensible price; document 1 ran on a 16 GB RTX 4060 Ti, LAB_GPU_MIN_GB=16); link test right after renting, destroy below 0.5 MB/s; HARD CAP $10 per
session including idle time; destroy when the owner ends the session, after 90 minutes without inference, or
before the cap would be passed.  The keeper logs every minute to out/gpu_spend.jsonl.  Processes are only ever
stopped by exact PID.  The ops/vast_guard.sh safety net runs independently.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SESSION = OUT / "gpu_session.json"
SPEND = OUT / "gpu_spend.jsonl"
ACTIVITY = OUT / "gpu_last_activity"
RATE = OUT / "data" / "gpu_rate.json"
BAD = OUT / "gpu_bad_machines.json"          # machines that failed a link test: never rented again
V = str(Path.home() / ".local/venvs/vast/bin/vastai")
KEY = str(Path.home() / ".ssh/id_ed25519_vast")
CAP_USD = float(os.environ.get("LAB_GPU_CAP", "10"))
IDLE_MIN = float(os.environ.get("LAB_GPU_IDLE_MIN", "90"))
IMAGE = "pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime"     # exp 36's proven base image (CUDA 12.8)
DISK_GB = 80
QUERY = (f"num_gpus=1 gpu_ram>={os.environ.get('LAB_GPU_MIN_GB', '31')} datacenter=True verified=True reliability>=0.995 inet_down>=300 inet_up>=300 "
         "cuda_max_good>=12.8 disk_space>=80 cpu_ram>=32 rentable=True")


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(ev: dict):
    SPEND.parent.mkdir(parents=True, exist_ok=True)
    with open(SPEND, "a") as f:
        f.write(json.dumps(dict(time=now_iso(), **ev)) + "\n")


def vast(*args, raw=True, check=True) -> object:
    cmd = [V, *args] + (["--raw"] if raw else [])
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if check and p.returncode != 0:
        raise RuntimeError(f"vastai {args[0]} failed: {p.stderr.strip()[:500]}")
    if raw:
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError:
            return p.stdout
    return p.stdout


def session() -> dict | None:
    return json.loads(SESSION.read_text()) if SESSION.exists() else None


def ssh_base(s: dict) -> list[str]:
    return ["ssh", "-i", KEY, "-p", str(s["port"]), "-o", "StrictHostKeyChecking=accept-new", "-o",
            "ConnectTimeout=20", "-o", "ServerAliveInterval=30", "-o", "BatchMode=yes", f"root@{s['host']}"]


def scp_to(s: dict, local: str, remote: str, timeout: float = 900):
    subprocess.run(["scp", "-q", "-i", KEY, "-P", str(s["port"]), "-o", "StrictHostKeyChecking=accept-new",
                    local, f"root@{s['host']}:{remote}"], check=True, timeout=timeout)


def scp_from(s: dict, remote: str, local: str, timeout: float = 900):
    subprocess.run(["scp", "-q", "-i", KEY, "-P", str(s["port"]), "-o", "StrictHostKeyChecking=accept-new",
                    f"root@{s['host']}:{remote}", local], check=True, timeout=timeout)


LINK_TIMEOUT = 45          # 20 MB at the 0.5 MB/s floor takes 40 s: a transfer slower than that fails the test at once


def spent(s: dict) -> float:
    return (time.time() - s["started_ts"]) / 3600 * s["dph"]


# ------------------------------------------------------------------------------------------------ commands

def offers(limit=10):
    d = vast("search", "offers", QUERY, "-o", "dph+")
    rows = []
    for o in d[:limit]:
        rows.append(dict(id=o["id"], gpu=o["gpu_name"], gpu_gb=round(o["gpu_ram"] / 1024), dph=round(o["dph_total"], 3),
                         rel=round(o.get("reliability2", o.get("reliability", 0)), 4), down=round(o["inet_down"]),
                         up=round(o["inet_up"]), cuda=o.get("cuda_max_good"), geo=o.get("geolocation"),
                         disk=round(o.get("disk_space", 0)), cc=o.get("compute_cap")))
    print(json.dumps(rows, indent=1))
    return rows


def destroy(s: dict, reason: str):
    iid = s["instance"]
    out = vast("destroy", "instance", str(iid), "-y", raw=False, check=False)
    left = vast("show", "instances")
    still = [i["id"] for i in left] if isinstance(left, list) else ["?"]
    usd = spent(s)
    log(dict(event="end", instance=iid, minutes=round((time.time() - s["started_ts"]) / 60, 1), dph=s["dph"],
             usd=round(usd, 4), reason=reason, destroy_output=str(out).strip()[:200], instances_left=still))
    s["ended"] = now_iso()
    s["end_reason"] = reason
    s["usd"] = round(usd, 4)
    SESSION.rename(OUT / f"gpu_session_{iid}_ended.json")
    (OUT / f"gpu_session_{iid}_ended.json").write_text(json.dumps(s, indent=1))
    print(f"destroyed {iid} ({reason}); ${usd:.3f}; instances left: {still}")
    return still


def start(offer_id: str):
    if session():
        raise SystemExit("a session is already open: status / stop it first")
    bad = set(json.loads(BAD.read_text())) if BAD.exists() else set()
    found = vast("search", "offers", QUERY, "-o", "dph+")
    if str(offer_id).isdigit():
        od = [o for o in found if str(o["id"]) == str(offer_id)]
    else:   # a card name (e.g. RTX_5090): the cheapest offer passing the rules right now, skipping failed machines
        od = [o for o in found if o["gpu_name"].replace(" ", "_") == offer_id and o.get("machine_id") not in bad][:1]
        if od:
            offer_id = od[0]["id"]
    if not od:
        raise SystemExit("offer not found or no longer passing the rules")
    o = od[0]
    dph = float(o["dph_total"])
    est = dph * 1.0
    print(f"offer {offer_id}: {o['gpu_name']} {round(o['gpu_ram']/1024)} GB ${dph:.3f}/h; an hour = ${est:.2f}; "
          f"cap ${CAP_USD} = {CAP_USD/dph*60:.0f} minutes")
    r = vast("create", "instance", str(offer_id), "--image", IMAGE, "--disk", str(DISK_GB), "--ssh", "--direct")
    iid = r["new_contract"]
    t0 = time.time()
    s = dict(instance=iid, offer=int(offer_id), machine=o.get("machine_id"), gpu=o["gpu_name"], gpu_gb=round(o["gpu_ram"] / 1024), dph=dph,
             started=now_iso(), started_ts=t0, cap_usd=CAP_USD, idle_min=IDLE_MIN, geo=o.get("geolocation"))
    SESSION.write_text(json.dumps(s, indent=1))
    log(dict(event="start", instance=iid, offer=int(offer_id), gpu=o["gpu_name"], dph=dph))
    ACTIVITY.write_text(now_iso())
    _spawn_keeper()
    s = session()                 # now carries keeper_pid
    try:
        for _ in range(90):
            d = vast("show", "instance", str(iid), check=False)
            if isinstance(d, dict) and d.get("actual_status") == "running" and d.get("ssh_host"):
                break
            time.sleep(10)
        else:
            raise RuntimeError("instance did not reach running in 15 minutes")
        url = vast("ssh-url", str(iid), raw=False).strip()          # ssh://root@HOST:PORT
        hp = url.split("@", 1)[1]
        s["host"], s["port"] = hp.rsplit(":", 1)
        s["port"] = int(s["port"])
        SESSION.write_text(json.dumps(s, indent=1))
        for _ in range(18):
            if subprocess.run(ssh_base(s) + ["mkdir -p /work/in /work/out"], capture_output=True, timeout=60).returncode == 0:
                break
            time.sleep(10)
        else:
            raise RuntimeError("ssh never answered")
        # link test: ~20 MB each way
        tmp = OUT / "linktest.bin"
        tmp.write_bytes(os.urandom(20_000_000))
        try:
            a = time.time()
            scp_to(s, str(tmp), "/work/linktest.bin", timeout=LINK_TIMEOUT)
            up = 20 / (time.time() - a)
            a = time.time()
            scp_from(s, "/work/linktest.bin", str(tmp), timeout=LINK_TIMEOUT)
            down = 20 / (time.time() - a)
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            log(dict(event="link_test", instance=iid, failed=str(e)[:200]))
            BAD.write_text(json.dumps(sorted((set(json.loads(BAD.read_text())) if BAD.exists() else set())
                                             | {s.get("machine")} - {None})))
            destroy(s, f"link test failed or slower than 0.5 MB/s ({type(e).__name__})")
            raise SystemExit(2)
        tmp.unlink()
        s["link_mb_s"] = dict(up=round(up, 2), down=round(down, 2))
        SESSION.write_text(json.dumps(s, indent=1))
        log(dict(event="link_test", instance=iid, up_mb_s=round(up, 2), down_mb_s=round(down, 2)))
        print(f"link test: up {up:.2f} MB/s, down {down:.2f} MB/s")
        if min(up, down) < 0.5:
            BAD.write_text(json.dumps(sorted((set(json.loads(BAD.read_text())) if BAD.exists() else set())
                                             | {s.get("machine")} - {None})))
            destroy(s, f"slow link {min(up, down):.2f} MB/s")
            raise SystemExit(2)
        upload_workers(s)
        subprocess.run(ssh_base(s) + ["cd /work && rm -f linktest.bin && (setsid nohup bash workers/setup_gpu.sh "
                                      "> setup.out 2>&1 < /dev/null &)"], check=True, timeout=60)
        RATE.parent.mkdir(parents=True, exist_ok=True)
        RATE.write_text(json.dumps(dict(usd_per_hour=dph, currency="USD", gpu=f"{o['gpu_name']} "
                                        f"{round(o['gpu_ram']/1024)} GB (Vast.ai offer {offer_id}, datacenter)",
                                        date=now_iso()[:10], instance=iid)))
        print(json.dumps(dict(instance=iid, host=s["host"], port=s["port"]), indent=1))
    except BaseException as e:
        if session():
            destroy(session(), f"start failed: {e}")
        raise


def upload_workers(s: dict):
    import tarfile
    tgz = OUT / "workers.tgz"
    with tarfile.open(tgz, "w:gz") as t:
        t.add(HERE / "workers", arcname="workers")
        t.add(HERE / "labocr/adapters/worker_base.py", arcname="workers/worker_base.py")
    scp_to(s, str(tgz), "/work/workers.tgz")
    subprocess.run(ssh_base(s) + ["cd /work && tar xzf workers.tgz"], check=True, timeout=60)


def status():
    s = session()
    if not s:
        print("no open session")
        return
    idle = (time.time() - datetime.fromisoformat(ACTIVITY.read_text().strip()).timestamp()) / 60 if ACTIVITY.exists() else None
    d = vast("show", "instance", str(s["instance"]), check=False)
    st = d.get("actual_status") if isinstance(d, dict) else "unknown"
    usd = spent(s)
    print(json.dumps(dict(instance=s["instance"], gpu=s["gpu"], status=st, minutes=round((time.time() - s["started_ts"]) / 60, 1),
                          usd=round(usd, 3), cap=CAP_USD, cap_left=round(CAP_USD - usd, 3),
                          idle_min=round(idle, 1) if idle is not None else None, idle_limit=IDLE_MIN,
                          keeper_pid=s.get("keeper_pid")), indent=1))


def budget(minutes: float) -> bool:
    s = session()
    if not s:
        print("no open session")
        return False
    proj = spent(s) + minutes / 60 * s["dph"]
    ok = proj < CAP_USD
    print(f"now ${spent(s):.3f}; +{minutes} min -> ${proj:.3f} of ${CAP_USD} cap: {'OK' if ok else 'WOULD PASS THE CAP'}")
    return ok


def touch():
    ACTIVITY.write_text(now_iso())


def worker(engine: str):
    s = session()
    if not s:
        raise SystemExit("no open session")
    env = {"paddle_vl": "PADDLE_PDX_MODEL_SOURCE=huggingface PADDLE_VL_REVISION=c5630abae1d940eafe0697512a0325494b02ab42 "
                        "PADDLE_VL_DIR=/work/models/PaddleOCR-VL-1.6 PADDLE_LAYOUT_DIR=/work/models/PP-DocLayoutV3 "
                        "/opt/paddle/bin/python /work/workers/paddle_vl_worker.py",
           "nuqta": "HF_HOME=/work/hf HF_HUB_OFFLINE=1 NUQTA_REVISION=6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c "
                    "NUQTA_DIR=/work/models/Nuqta-Arabic-OCR-4B /opt/nuqta/bin/python /work/workers/nuqta_worker.py",
           # the same model with the card's fast kernels (nuqta-ocr[fast]); /opt/nuqta_fast is built by hand, see README
           "nuqta_fast": "HF_HOME=/work/hf HF_HUB_OFFLINE=1 NUQTA_REVISION=6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c "
                         "NUQTA_DIR=/work/models/Nuqta-Arabic-OCR-4B /opt/nuqta_fast/bin/python /work/workers/nuqta_worker.py"}[engine]
    print(json.dumps(ssh_base(s) + [f"cd /work && {env}"]))


def ssh_cmd(cmd: str):
    s = session()
    if not s:
        raise SystemExit("no open session")
    p = subprocess.run(ssh_base(s) + [cmd], capture_output=True, text=True, timeout=600)
    sys.stdout.write(p.stdout)
    sys.stderr.write(p.stderr[-2000:])


def stop(reason: str):
    s = session()
    if not s:
        print("no open session;", vast("show", "instances"))
        return
    destroy(s, reason)


# ------------------------------------------------------------------------------------------------ keeper

def _spawn_keeper():
    p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "keeper"], stdin=subprocess.DEVNULL,
                         stdout=open(OUT / "gpu_keeper.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
    s = session()
    s["keeper_pid"] = p.pid
    SESSION.write_text(json.dumps(s, indent=1))


def keeper():
    """Every minute: log the spend; destroy at the idle limit or before the cap; exit when the session ends."""
    while True:
        s = session()
        if not s:
            print(now_iso(), "session closed; keeper exits", flush=True)
            return
        usd = spent(s)
        idle = (time.time() - datetime.fromisoformat(ACTIVITY.read_text().strip()).timestamp()) / 60 if ACTIVITY.exists() else 0
        log(dict(event="minute", instance=s["instance"], minutes=round((time.time() - s["started_ts"]) / 60, 1),
                 dph=s["dph"], usd=round(usd, 4), idle_min=round(idle, 1)))
        try:
            if idle >= IDLE_MIN:
                destroy(s, f"idle {idle:.0f} min without inference")
                return
            if usd + s["dph"] * 2 / 60 >= CAP_USD:          # two minutes of margin
                destroy(s, f"cap: ${usd:.2f} of ${CAP_USD}")
                return
        except Exception as e:  # noqa: BLE001
            print(now_iso(), "keeper error", e, flush=True)
        time.sleep(60)


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "status"
    if c == "offers":
        offers()
    elif c == "start":
        start(sys.argv[2])
    elif c == "status":
        status()
    elif c == "touch":
        touch()
    elif c == "budget":
        sys.exit(0 if budget(float(sys.argv[2])) else 1)
    elif c == "worker":
        worker(sys.argv[2])
    elif c == "ssh":
        ssh_cmd(sys.argv[2])
    elif c == "stop":
        stop(" ".join(sys.argv[2:]) or "owner ended the session")
    elif c == "keeper":
        keeper()
    else:
        raise SystemExit(__doc__)
