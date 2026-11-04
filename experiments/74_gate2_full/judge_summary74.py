"""Experiment 70 (copied from experiment 52) (copied from the exam's judge_summary.py): every judge finding on journal J (exp 74, from exp 70) with its route (decide = the frozen two keys) -> judge_findings.jsonl,
judge_summary.json (by group flagged / random, by route, by type x route)."""
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
J = sys.argv[1]
H = Path(__file__).resolve().parent / "out" / J / f"j{J}"
X = Path("/home/appuser/inkscript/experiments/43_rehearsal")
sys.path.insert(0, str(X))
import judge43 as JG
JG.PV = "v2"
sample = {tuple(l.rsplit(":", 1)) for l in (H / "pages_sample.txt").read_text().split()}
rows, pages = [], defaultdict(Counter)
tr = defaultdict(Counter)
usd = 0
for f in sorted((JG.J / "answers" / "gemini-4-argon_v2" / f"j{J}").glob("*_p[0-9][0-9][0-9].json")):
    rec = json.loads(f.read_text())
    usd += rec.get("usd") or 0
    g = "random" if (rec["stem"], str(rec["page"])) in sample else "flagged"
    fs = JG.decide(rec)
    rs = {x["route"] for x in fs}
    key = "auto" if "auto" in rs else "retry" if "retry" in rs else "human" if "human" in rs else "dismissed" if "dismissed" in rs else "none"
    pages[g][key] += 1
    pages[g]["pages"] += 1
    if not fs:
        rows.append(dict(stem=rec["stem"], page=rec["page"], group=g, n=0, route="none", type=None))
    for x in fs:
        tr[x["type"]][x["route"]] += 1
        rows.append(dict(stem=rec["stem"], page=rec["page"], group=g, n=x["n"], route=x["route"], type=x["type"],
                         subtype=x.get("subtype"), action=x["action"], confidence=x["confidence"], blocks=x["blocks"],
                         evidence=x.get("evidence"), instruction=x.get("instruction"), check=x.get("check"),
                         patch_id=(x.get("patch") or {}).get("id"), apply=(x.get("patch") or {}).get("apply")))
(H / "judge_findings.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
routes = Counter(r["route"] for r in rows if r["n"])
s = dict(pages=dict(pages), findings=sum(1 for r in rows if r["n"]), routes=dict(routes),
         types={t: dict(c) for t, c in sorted(tr.items(), key=lambda kv: -sum(kv[1].values()))}, usd=round(usd, 4))
(H / "judge_summary.json").write_text(json.dumps(s, indent=1))
print(json.dumps(s, indent=1))
