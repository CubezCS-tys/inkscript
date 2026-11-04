"""Experiment 52: pages for the judge, as the exam drew them (out/v33_300b/judge_pages.py): every flagged page of
out/j0130/flags.json (any severity) + 50 random unflagged pages (seed 5245). And the 10 pages for the look beside the
scan (seed 5246, any page of any article with a master). No calls."""
import json, random
from pathlib import Path
H = Path(__file__).resolve().parent / "out"
R = H / "j0130"
arts = json.loads((H / "sample52.json").read_text())["articles"]
F = json.loads((R / "flags.json").read_text())["articles"]
flagged = sorted({(s, f["page"]) for s, a in F.items() for f in a.get("flags") or [] if isinstance(f.get("page"), int)})
allp = [(a["stem"], p) for a in arts if (R / "masters" / f"{a['stem']}.jats.xml").exists()
        for p in range(a["first"], a["last"] + 1)]
fs = set(flagged)
rest = [x for x in allp if x not in fs]
sample = sorted(random.Random(5245).sample(rest, 50))
(R / "pages_flagged.txt").write_text("".join(f"{s}:{p}\n" for s, p in flagged))
(R / "pages_sample.txt").write_text("".join(f"{s}:{p}\n" for s, p in sample))
(R / "pages_judge.txt").write_text("".join(f"{s}:{p}\n" for s, p in flagged + sample))
look = sorted(random.Random(5246).sample(allp, 10))
(H / "look10.json").write_text(json.dumps(dict(seed=5246, how="random.Random(5246).sample over every page of every article with a master", pages=look), indent=1))
print(len(allp), "pages;", len(flagged), "flagged;", len(sample), "random unflagged (seed 5245); look:", look)
