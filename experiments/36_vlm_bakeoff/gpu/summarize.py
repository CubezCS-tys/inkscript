"""Per-model totals of the GPU run from out/raw/<tag>/: pages ok / failed records / cap hits, pages per hour,
cost per 1,000 pages at the instance's $/h.   python3 summarize.py [DPH]"""
import json, os, sys
RAW = "/home/yassine/inkscript/experiments/36_vlm_bakeoff/out/raw"
DPH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.469
for tag in sorted(os.listdir(RAW)):
    d = f"{RAW}/{tag}"; files = os.listdir(d)
    ok = [json.load(open(f"{d}/{f}")) for f in files if f.endswith(".json") and f.count(".") == 1 and f != "run.json"]
    fails = [f for f in files if f.count(".") == 2]
    run = json.load(open(f"{d}/run.json")) if "run.json" in files else {}
    pph = run.get("pages_per_hour")
    cap = sum(bool(r.get("hit_cap")) for r in ok)
    toks = [r.get("completion_tokens") or 0 for r in ok]
    secs = sorted(r["seconds"] for r in ok)
    nobox = sum(1 for r in ok if tag.startswith("qwen") and "data-bbox" not in (r.get("output") or ""))
    print(f"{tag:22s} ok {len(ok):3d}  failed-records {len(fails):3d}  cap {cap:3d}  tokens {sum(toks):7d}  "
          f"median s {secs[len(secs)//2] if secs else 0:6.1f}  max s {secs[-1] if secs else 0:6.1f}  pages/h {pph}  "
          f"$/1000p {round(1000 / pph * DPH, 3) if pph else None}  conc {run.get('concurrency', run.get('chunk'))}"
          + (f"  no data-bbox {nobox}" if tag.startswith("qwen") else ""))
