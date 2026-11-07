"""Experiment 76, step 1b: on the 202 yardstick pages, how often is a whole PAGE or a whole REGION clean
(every line: Azure == blind Gemini)? Decides whole pages vs region crops vs loss-masked pages. Read only."""
import json, re, sys, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))
from consensus76 import POL, GOLD  # noqa: E402
res = {}
for p, fn in POL.items():
    pages_full = 0; pages = 0; reg = collections.Counter(); share = []
    for f in sorted(GOLD.glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        L = [x for x in g["lines"] if "gemini" in (x.get("draft") or {}) and (x["draft"].get("azure") or "").strip()]
        if not L:
            continue
        pages += 1
        ok = [fn(x["draft"]["azure"]) == fn(x["draft"]["gemini"]) for x in L]
        share.append(sum(ok) / len(ok))
        pages_full += all(ok)
        byr = collections.defaultdict(list)
        for x, o in zip(L, ok):
            byr[x.get("region")].append(o)
        for r, v in byr.items():
            reg["regions"] += 1; reg["full"] += all(v); reg["lines_in_full"] += len(v) if all(v) else 0
    share.sort()
    res[p] = dict(pages=pages, pages_all_lines_agree=pages_full, regions=reg["regions"], regions_all_agree=reg["full"],
                  lines_in_clean_regions=reg["lines_in_full"], median_page_line_share=share[len(share) // 2],
                  pages_ge_90pct=sum(s >= .9 for s in share), pages_ge_75pct=sum(s >= .75 for s in share))
    print(p, res[p])
(HERE / "out/pagelevel76.json").write_text(json.dumps(res, indent=1))
