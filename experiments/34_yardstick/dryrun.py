"""A dry run of the correcting, by the agent (not the owner): how often is neither reading right? (experiment 34)

    PYTHONPATH=src python dryrun.py sample     -> out/dryrun/sheet_<k>.png (numbered line crops) + out/dryrun/items.json
    (the agent looks at each crop and writes its verdicts into out/dryrun/verdicts.json: {"<n>": "azure" | "gemini" |
     "both" | "neither" | "delete" | "unclear"}; delete = not text, one key)
    PYTHONPATH=src python dryrun.py tally      -> out/dryrun.json (share of disagreements needing typing)

40 lines where the readers differ, drawn at random (seed 34) from the dev split only (the test split is never
looked at by anyone tuning anything; the dry run tunes the estimate). The verdicts are the agent's reading of the
ink, not gold.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")
D = OUT / "dryrun"


def sample() -> int:
    D.mkdir(exist_ok=True)
    items = []
    for f in sorted((OUT / "gold").glob("*_p[0-9][0-9][0-9].json")):
        g = json.loads(f.read_text())
        if g.get("split") != "dev":
            continue
        for ln in g["lines"]:
            if ln.get("disagree"):
                items.append(dict(page_id=g["page_id"], line=ln["id"], box=ln["box"], azure=ln["text"],
                                  gemini=ln["draft"].get("gemini", ""), flags=ln["flags"]))
    random.Random(34).shuffle(items)
    items = items[:40]
    for n, it in enumerate(items, 1):
        it["n"] = n
    strips = []
    for it in items:
        img = cv2.imread(str(OUT / "gold" / f"{it['page_id']}.jpg"), cv2.IMREAD_GRAYSCALE)
        x0, y0, x1, y1 = (int(v) for v in it["box"])
        pad = int(0.15 * (y1 - y0))
        c = img[max(0, y0 - pad):y1 + pad, max(0, x0 - 6):x1 + 6]
        s = 1100 / max(1, c.shape[1]) if c.shape[1] > 1100 else 1.0
        c = cv2.resize(c, (int(c.shape[1] * s), int(c.shape[0] * s)))
        band = np.full((c.shape[0] + 6, 1180), 255, np.uint8)
        band[3:3 + c.shape[0], 70:70 + c.shape[1]] = c
        cv2.putText(band, str(it["n"]), (8, min(band.shape[0] - 8, 40)), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)
        cv2.line(band, (0, band.shape[0] - 1), (1180, band.shape[0] - 1), 160, 1)
        strips.append(band)
    for k in range(0, len(strips), 10):
        cv2.imwrite(str(D / f"sheet_{k // 10 + 1}.png"), np.vstack(strips[k:k + 10]))
    (D / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=1))
    for it in items:
        print(it["n"], "A:", it["azure"], "\n   G:", it["gemini"])
    return 0


def tally() -> int:
    items = json.loads((D / "items.json").read_text())
    v = json.loads((D / "verdicts.json").read_text())
    from collections import Counter
    c = Counter(v.get(str(it["n"]), "unclear") for it in items)
    judged = sum(c[k] for k in ("azure", "gemini", "both", "neither", "delete"))
    res = dict(lines=len(items), verdicts=dict(c), share_typed=round(c["neither"] / judged, 3) if judged else None,
               share_gemini=round(c["gemini"] / judged, 3) if judged else None,
               share_azure=round(c["azure"] / judged, 3) if judged else None,
               note="the agent's reading of the ink on 40 dev-split disagreements; not gold")
    (OUT / "dryrun.json").write_text(json.dumps(res, indent=1))
    print(res)
    return 0


if __name__ == "__main__":
    sys.exit(sample() if sys.argv[1] == "sample" else tally())
