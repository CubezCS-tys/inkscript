"""Experiment 43: experiment 41's Layout view (views.build_layout, read from masters by mread.load) drawn from a
masters folder of this experiment, with text of another article (ALTO role.otherArticle) faded and labelled
"another article", and ornaments (ALTO role.ornament) left to the scan. No model calls; nothing in experiment 41 changes.

    views43.py --masters out/masters_sim --stems 0656-016-001-011 0747-001-003-001 [--out out/views_sim]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43  # noqa: E402,F401  (paths to experiment 41)
import views as V  # noqa: E402
import mread as MR  # noqa: E402
from structure import art_of  # noqa: E402

CSS43 = r"""
.pc.t-other_article{opacity:.38;outline:1px dashed #888}
.pc.t-other_article::before{content:"another article";position:absolute;top:-1.2em;right:0;font:600 10px/1.2 system-ui,
sans-serif;color:#555;background:#f3f3f3;padding:1px 5px;border-radius:3px;opacity:1;direction:ltr}
body.blocks .pc.t-other_article{outline:2px dashed #777}
"""


def load43(a):
    doc = MR.load(a)
    other, orn = set(), set()
    for b in doc["D"].A.iter(MR._q("TextBlock")):
        if "role.otherArticle" in (b.get("TAGREFS") or ""):
            other.add(b.get("ID"))
        if "role.ornament" in (b.get("TAGREFS") or ""):
            orn.add(b.get("ID"))
    for rec in doc["blocks"]:
        if rec.get("alto") in other:
            rec["type"] = "other_article"
    doc["blocks"] = [r for r in doc["blocks"] if r.get("alto") not in orn]     # ornaments: ink only (the scan)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--masters", required=True)
    ap.add_argument("--out", default=str(HERE / "out" / "views"))
    ap.add_argument("--stems", nargs="+", required=True)
    a = ap.parse_args()
    MR.MAST = Path(a.masters).resolve()
    V.VIEWS = Path(a.out).resolve()
    V.MIRROR_CSS = V.MIRROR_CSS + CSS43
    V.write_layout_print = lambda *x, **k: None              # the print page is not part of this check
    for s in a.stems:
        st = V.build_layout(art_of(s), load43(art_of(s)))
        print(s, st, "->", V.VIEWS / "mirror" / f"{s}.html")


if __name__ == "__main__":
    main()
