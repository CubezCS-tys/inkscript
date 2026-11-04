"""Experiment 74 (from judge_pages70.py) for journal J: pages for the judge (every flagged page of out/J/jJ/flags.json
+ 50 random unflagged pages, seed 7445) and the 10 pages for the look beside the scan (seed 7446). No calls.

    python3 judge_pages74.py J"""
import json, random, sys
from pathlib import Path
J = sys.argv[1]
H = Path(__file__).resolve().parent / "out" / J
R = H / f"j{J}"
arts = json.loads((H / "sample.json").read_text())["articles"]
F = json.loads((R / "flags.json").read_text())["articles"]
flagged = sorted({(s, f["page"]) for s, a in F.items() for f in a.get("flags") or [] if isinstance(f.get("page"), int)
                  and (R / "masters" / f"{s}.jats.xml").exists()})   # an article with no master (unread) has no view
allp = [(a["stem"], p) for a in arts if (R / "masters" / f"{a['stem']}.jats.xml").exists()
        for p in range(a["first"], a["last"] + 1)]
fs = set(flagged)
rest = [x for x in allp if x not in fs]
sample = sorted(random.Random(7445).sample(rest, 50))
(R / "pages_flagged.txt").write_text("".join(f"{s}:{p}\n" for s, p in flagged))
(R / "pages_sample.txt").write_text("".join(f"{s}:{p}\n" for s, p in sample))
(R / "pages_judge.txt").write_text("".join(f"{s}:{p}\n" for s, p in flagged + sample))
look = sorted(random.Random(7446).sample(allp, 10))
(H / "look10.json").write_text(json.dumps(dict(seed=7446, how="random.Random(7446).sample over every page of every article with a master", pages=look), indent=1))
print(len(allp), "pages;", len(flagged), "flagged;", len(sample), "random unflagged (seed 7445); look:", look)
