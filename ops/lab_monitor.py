#!/usr/bin/env python3
"""Lab monitor for rented Vast GPUs (2026-11-05, after two runs lost their results with their machines).

Every 5 minutes, for every running Vast instance:
  - finds which experiment owns it (experiments/*/out/gpu/gpu_session.json);
  - checks the host answers over ssh and reads its GPU use (nvidia-smi);
  - every 10 minutes MIRRORS the host's results to experiments/<exp>/out/mirror/<instance>/ (rsync of /work, without the
    big uploaded data), so a machine that dies loses at most ~10 minutes of results;
  - Telegrams the owner, once per problem: host unreachable twice in a row, an instance no experiment owns,
    GPU idle over 30 minutes, an instance older than 8 hours.
Writes ops/lab_status.json each round. Never destroys anything (the keepers and ops/vast_guard.sh do that).
Run: setsid nohup nice -n 19 python3 ops/lab_monitor.py >/dev/null 2>&1 &
"""
import glob, json, os, subprocess, time
from datetime import datetime, timezone

ROOT = "/home/appuser/inkscript"
V = os.path.expanduser("~/.local/venvs/vast/bin/vastai")
KEY = os.path.expanduser("~/.ssh/id_ed25519_vast")
STATUS = f"{ROOT}/ops/lab_status.json"
LOG = f"{ROOT}/ops/lab_monitor.log"
# Only results are mirrored: out/ and run_*/ folders plus top-level logs and json; uploaded data never comes back.
INCLUDE = ["/out/***", "/run_*/***", "/*.log", "/*.json", "/*.jsonl", "/*.txt"]
SSH = ["ssh", "-i", KEY, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]
alerted, unreach, idle_since, last_mirror = set(), {}, {}, {}


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")


def tg(msg):
    subprocess.run(["/home/appuser/bin/tg", msg], capture_output=True, timeout=60)
    log("TELEGRAM " + msg.replace("\n", " | "))


def alert(key, msg):
    if key not in alerted:
        alerted.add(key)
        tg(msg)


def owners():
    out = {}
    for f in glob.glob(f"{ROOT}/experiments/*/out/gpu/gpu_session.json"):
        try:
            d = json.load(open(f))
            out[int(d["instance"])] = dict(exp=f.split("/experiments/")[1].split("/")[0], host=d["host"], port=d["port"])
        except Exception:
            pass
    return out


def ssh(host, port, cmd, timeout=40):
    return subprocess.run(SSH + ["-p", str(port), f"root@{host}", cmd], capture_output=True, text=True, timeout=timeout)


def mirror(exp, iid, host, port):
    dst = f"{ROOT}/experiments/{exp}/out/mirror/{iid}/"
    os.makedirs(dst, exist_ok=True)
    cmd = ["rsync", "-a", "--partial", "--timeout=120", "-e", " ".join(SSH + ["-p", str(port)])]
    cmd += ["--max-size=800M", "--exclude", "__pycache__/"]
    for e in INCLUDE:
        cmd += ["--include", e]
    cmd += ["--exclude", "*"]
    cmd += [f"root@{host}:/work/", dst]
    r = subprocess.run(["nice", "-n", "19", "ionice", "-c3"] + cmd, capture_output=True, text=True, timeout=1500)
    return r.returncode, r.stderr[-300:]


def round_once():
    try:
        inst = json.loads(subprocess.run([V, "show", "instances", "--raw"], capture_output=True, text=True,
                                         timeout=60).stdout or "[]")
    except Exception as e:
        log(f"vast list failed: {e}")
        return
    own, now, rows = owners(), time.time(), []
    for i in inst:
        iid = int(i["id"]); age_h = (now - (i.get("start_date") or now)) / 3600
        o = own.get(iid)
        row = dict(instance=iid, gpu=i.get("gpu_name"), dph=round(i.get("dph_total", 0), 3), age_h=round(age_h, 2),
                   exp=o["exp"] if o else None)
        if not o:
            alert(f"orphan{iid}", f"Lab monitor: GPU instance {iid} ({i.get('gpu_name')}, ${i.get('dph_total', 0):.2f}/h) "
                                  f"belongs to no experiment. Check it, or it keeps billing.")
            rows.append(row); continue
        if age_h > 8:
            alert(f"old{iid}", f"Lab monitor: {o['exp']} GPU {iid} has run {age_h:.1f} h. Is that intended?")
        try:
            r = ssh(o["host"], o["port"], "nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits; cut -d' ' -f1 /proc/loadavg")
            ok = r.returncode == 0
        except Exception:
            ok = False
        if not ok:
            unreach[iid] = unreach.get(iid, 0) + 1
            row["reachable"] = False
            if unreach[iid] >= 2:
                alert(f"unreach{iid}", f"Lab monitor: {o['exp']} GPU {iid} is not answering (twice in a row). "
                                       f"Its last mirrored results are in experiments/{o['exp']}/out/mirror/{iid}/.")
            rows.append(row); continue
        unreach[iid] = 0
        lines = [l for l in r.stdout.strip().splitlines() if "," in l or l.replace(".", "", 1).isdigit()]
        util, mem = [x.strip() for x in lines[0].split(",")[:2]]
        load = float(lines[-1]) if len(lines) > 1 else 0.0
        row.update(reachable=True, gpu_util=int(float(util)), mem_mb=int(float(mem)), cpu_load=load)
        # a host busy on its CPUs (cutting lines, rendering) is working, not idle (2026-11-06)
        if row["gpu_util"] < 5 and load < 4:
            idle_since.setdefault(iid, now)
            if now - idle_since[iid] > 1800:
                alert(f"idle{iid}", f"Lab monitor: {o['exp']} GPU {iid} has been idle over 30 min (still billing).")
        else:
            idle_since.pop(iid, None)
        if now - last_mirror.get(iid, 0) >= 600:
            try:
                rc, err = mirror(o["exp"], iid, o["host"], o["port"])
                last_mirror[iid] = now
                row["mirror"] = "ok" if rc == 0 else f"rc {rc}"
                log(f"mirror {o['exp']} {iid}: rc {rc} {err.strip()[:200]}")
            except Exception as e:
                row["mirror"] = f"error {e}"; log(f"mirror {o['exp']} {iid} failed: {e}")
        rows.append(row)
    json.dump(dict(time=datetime.now(timezone.utc).isoformat(timespec="seconds"), instances=rows,
                   hourly=round(sum(r["dph"] for r in rows), 2)), open(STATUS, "w"), indent=1)


if __name__ == "__main__":
    log("monitor started")
    while True:
        try:
            round_once()
        except Exception as e:
            log(f"round failed: {e}")
        time.sleep(300)
