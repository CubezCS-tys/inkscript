"""Replay the cutter offline on captured pieces (capture.py), exactly as the build does: plan every piece in build
order; the first LEARN_FROM plans teach the atlas (penpath.solve); every later one is cut against it (penpath.apply).
Pieces after the atlas that are not on the wanted pages are skipped (they do not influence anything).

    from replay import replay; plans = replay("0582", pages={1,2,3})   # list of (rec, plan) for the wanted pages
"""
import sys, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "experiments/21_better_boxes"))
from inkscript.geometry import penpath as P
from build import DOCS

LEARN_FROM = 1500
_PAGES = {}


def page_of(doc):
    if doc not in _PAGES:
        from inkscript.ocr.azure import load_azure
        d = DOCS[doc]; az = Path(d["args"][1]) / d["stem"] / f"{d['stem']}.json"
        _PAGES[doc] = {w["off"]: w["page"] for w in load_azure(az)[0]}
    return _PAGES[doc]


def records(doc):
    rec = pickle.load(open(HERE / "out/cap" / f"{doc}.pkl", "rb")); pg = page_of(doc)
    for r in rec: r["page"] = pg.get(r["word"]["off"]) if r["word"] else None
    return rec


def replay(doc, pages=None, keep_learn=False, every=False):
    """-> (kept, atlas): kept = [(rec, plan)] on `pages` (all pages if None), cut as the build cuts them."""
    rec = records(doc); live = []; kept = []; atlas = None
    for r in rec:
        if atlas is not None and pages is not None and r["page"] not in pages: continue
        p = P.plan(r["units"], r["blobs"], r["line"], r["forms"])
        if not p: continue
        if atlas is None:
            live.append((r, p))
            if len(live) >= LEARN_FROM:
                atlas = P.solve([q for _, q in live]); kept += [(rr, q) for rr, q in live if pages is None or rr["page"] in pages or keep_learn]; live = []
        else:
            P.apply(p, atlas); kept.append((r, p))
    if atlas is None:
        atlas = P.solve([q for _, q in live]); kept += [(rr, q) for rr, q in live if pages is None or rr["page"] in pages or keep_learn]
    for _, q in kept: q["cache"] = {}; q.pop("fcache", None)                # the pictures of every possible cut: memory
    return kept, atlas
