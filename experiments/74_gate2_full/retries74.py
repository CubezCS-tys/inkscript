"""Experiment 74 (from retries70.py; usage: retries74.py J [--plan]) retries (copied from the exam): the judge's retry pages, at most 15 drawn at random (seed 4347); the rest are proposals.
One bespoke retry43 call per page (Standard, Argon), every finding of the page joined in one instruction."""
import json, random, subprocess, sys
from pathlib import Path
J = sys.argv[1]
H = Path(__file__).resolve().parent / "out" / J / f"j{J}"
X = Path("/home/appuser/inkscript/experiments/43_rehearsal")
by = {}
for l in (H / "judge_findings.jsonl").read_text().splitlines():
    r = json.loads(l)
    if r["route"] == "retry":
        by.setdefault((r["stem"], r["page"]), []).append(r)
pages = sorted(by)
pick = sorted(random.Random(7047).sample(pages, min(15, len(pages))))
plan = dict(seed=7047, retry_pages=[f"{s}:{p}" for s, p in pages], sent=[f"{s}:{p}" for s, p in pick],
            proposals_only=[f"{s}:{p}" for s, p in pages if (s, p) not in pick])
(H / "retries_plan.json").write_text(json.dumps(plan, indent=1))
print(len(pages), "retry pages;", len(pick), "sent")
if "--plan" in sys.argv:
    sys.exit()
for s, p in pick:
    if (X / "out" / "judge" / "retry" / f"j{J}" / f"{s}_p{p:03d}.json").exists():
        print("done already", s, p); continue
    fs = by[(s, p)]
    ins = " Also: ".join(f.get("instruction") or "" for f in fs)
    ev = " | ".join(f.get("evidence") or "" for f in fs)
    bl = list(dict.fromkeys(b for f in fs for b in f["blocks"]))
    subprocess.run([str(X.parent.parent / ".venv" / "bin" / "python"), str(X / "retry43.py"), "--run", f"j{J}",
                    "--page", f"{s}:{p}", "--instruction", ins, "--evidence", ev, "--blocks", *bl], cwd=X)
