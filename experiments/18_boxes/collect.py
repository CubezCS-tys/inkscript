"""Every word of the chosen pages with three sets of letter boxes: the built PDF's, the feeler's, equal slices.

A letter's box is what a drag-select highlights: a stretch of the line in page x (the line's height is not at
issue — Chrome highlights the font's height). Three ways of placing it, on the same word:

  cutter    the built vector PDF, read back: each glyph's advance [origin, origin + width] in scan pixels; a glyph
            carrying several letters (an uncut piece) is sliced into equal parts per character, as Chrome does.
            This is exactly what a reader of today's PDF gets.
  equal     the free baseline (D7): the word's whole span (the union of its glyphs' advances) sliced equally per
            character — what Chrome shows when the word is one glyph (experiments/15_placement/build_baseline.py).
  feeler    experiment 16's hybrid_ctc_geo: on every joined piece of the word, the feeler reads the piece and cuts it
            on its pen path; its cuts become page x the way the cutter's do (penpath.letter_blobs: a cut point's
            column on the trunk; proportional where the path doubles back). Single-letter pieces keep the PDF's
            box (it is the piece, the same in every method). Only where the feeler reads every joined piece of the
            word exactly as Azure does; otherwise the word has no feeler boxes (and the reason is kept).

Pages: the fixture's five pages (cutter and equal only: the feeler trained, tuned and was tested on them) and the
bench books' pages that no feeler trained, tuned or tested on (experiment 17's list).

    experiments/16_feel/out/torchenv/bin/python collect.py            # writes out/words/<doc>_p<page>.json
One process; peak about 1.5 GB (the feeler's model and one page).
"""
import sys, json, time, resource, importlib.util
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
FEEL = REPO / "experiments/16_feel"
sys.path.insert(0, str(FEEL)); sys.path.insert(0, str(REPO / "experiments/10_atlas_reader")); sys.path.insert(0, str(REPO / "src"))
OUT = HERE / "out"

import bench                                                                     # noqa: E402  (imported, not edited)

_spec = importlib.util.spec_from_file_location("x17", REPO / "experiments/17_judge/extract.py")
X17 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(X17)       # pieces_with_words, eligible

TRY = REPO / "experiments/14_vs_azure/out/tryout_2026-10-05"
PDF = {"0582": TRY / "fixture_r2l/0582-004-009-012_vector.pdf", "0618": TRY / "native_r2l/0618-021-002-004_vector.pdf",
       "1036": TRY / "native/1036-010-038-007_vector.pdf", "0772": TRY / "native/0772-033-037-005_vector.pdf"}
# 17's judged pages (its PAGES after its eligibility guard; the ones it actually extracted)
UNSEEN = {"0618": [1, 16], "1036": [1, 10], "0772": [6, 14, 16, 18, 20, 23, 25, 27]}
FIXTURE = {"0582": [1, 2, 3, 4, 5]}

ARABIC = lambda c: "ء" <= c <= "ي" and c not in "ـ"                  # letters only: no tatweel, no harakat


def pdf_words(doc, pno):
    """The page's words as the PDF has them: per word its glyphs (visual order) and per letter (reading order) the
    cutter's box [x0, x1] in scan pixels and the glyph's letter count."""
    from inkscript.pdf.inspect import page_glyphs
    gl = page_glyphs(doc, pno - 1); words = []
    by_font = {}
    for g in gl: by_font.setdefault(g["font"], []).append(g)
    for fn, gs in by_font.items():
        gs = sorted(gs, key=lambda g: g["box_px"][0]); cur = []
        for g in gs:
            if cur and g["box_px"][0] - cur[-1]["box_px"][2] > 0.6: words.append(cur); cur = []
            cur.append(g)
        if cur: words.append(cur)
    out = []
    for ws in words:
        vis = "".join(g["text"] for g in ws)
        cells = []                                                                # visual order, one per character
        for g in ws:
            x0, x1 = g["box_px"][0], g["box_px"][2]; n = max(1, len(g["text"]))
            cells += [((x0 + (x1 - x0) * i / n), (x0 + (x1 - x0) * (i + 1) / n), n) for i in range(n)]
        if len(cells) != len(vis): continue
        # ink y-range from the glyph outlines (PDF points -> scan px through the page's own transform)
        out.append(dict(text=vis[::-1], cells=[(a, b) for a, b, _ in cells][::-1], nchar=[n for _, _, n in cells][::-1],
                        x0=ws[0]["box_px"][0], x1=ws[-1]["box_px"][2], font=fn))
    return out


def feeler_cells(q, cuts, n):
    """The feeler's cuts on the piece's pen path -> page-x cells, reading order; exactly penpath.letter_blobs' rule."""
    x_off, _ = q["off"]; S = q["G"]["W"]; trunk = q["trunk"]
    ys, xs = np.where(q["ink_s"] >= 0)
    X = lambda s: int(xs.min()) if s <= 0 else int(xs.max()) + 1 if s >= S else int(trunk[s][1])
    bounds = [0] + list(cuts) + [S]; bx = [X(s) for s in bounds]; prop = False
    if any(b - a < 2 for a, b in zip(bx, bx[1:])):
        bx = [int(round(bx[0] + (bx[-1] - bx[0]) * s / S)) for s in bounds]; prop = True
        if any(b - a < 2 for a, b in zip(bx, bx[1:])): return None, prop
    cell = dict(zip(bounds, bx))
    return [(cell[bounds[n - 1 - k]] + x_off, cell[bounds[n - k]] + x_off) for k in range(n)], prop


def collect(doc, pages, with_feeler, model=None):
    import fitz
    from reader import blind
    from methods import hybrid_ctc_geo as H
    cfg = bench.SUITE[doc]; pdf = fitz.open(str(PDF[doc]))
    for pn in pages:
        dst = OUT / "words" / f"{doc}_p{pn}.json"
        if dst.exists(): continue
        t = time.time(); pw = pdf_words(pdf, pn)
        # the Azure words with their pieces (as experiment 16/17 extract them)
        az = {}
        for pn_, li, wi, w, pcs, k, pc, (units, forms), lg in X17.pieces_with_words(str(cfg["azure"]), str(cfg["scan"]), [pn]):
            e = az.setdefault((li, wi), dict(line=li, word=wi, text=X17.__dict__.get("plain", lambda s: s)(w["text"].strip()),
                                             box=X17.box_of(w["blobs"]), npieces=len(pcs), pieces={}))
            rec = dict(units=[bench.base(u) for u in units], box=X17.box_of(pc["blobs"]), feel=None, why=None)
            if with_feeler and len(units) >= 2:
                if not lg or lg["rise"] < 10: rec["why"] = "line too small"
                else:
                    q = blind(pc, lg)
                    if q is None: rec["why"] = "no pen path"
                    else:
                        q.pop("cache", None)
                        r = dict(doc=doc, page=pn, units=units, forms=forms, rise=float(lg["rise"]), q=q)
                        letters, cuts = H.read(model, r)
                        got = [bench.base(x) for x in letters]
                        if got != rec["units"]: rec["why"] = "read differently"; rec["feel_read"] = "".join(got)
                        else:
                            cells, prop = feeler_cells(q, cuts, len(units))
                            if cells is None: rec["why"] = "cells collapse"
                            else: rec["feel"] = cells; rec["prop"] = prop
            e["pieces"][k] = rec
        # match PDF words to Azure words: same letters, overlapping x and the PDF word's x inside the Azure box
        words = []; used = set()
        for e in az.values():
            letters = "".join(u for k in sorted(e["pieces"]) for u in e["pieces"][k]["units"])
            if len(e["pieces"]) != e["npieces"]: continue                         # a piece was filtered out upstream
            x0, y0, x1, y1 = e["box"]
            best = None
            for i, w in enumerate(pw):
                if i in used or w["text"] != letters: continue
                ov = min(x1, w["x1"]) - max(x0, w["x0"])
                if ov > 0.6 * min(x1 - x0, w["x1"] - w["x0"]) and (best is None or ov > best[0]): best = (ov, i)
            if best is None: continue
            used.add(best[1]); w = pw[best[1]]
            n = len(letters); span = (w["x0"], w["x1"])
            # equal slicing: reading order goes right to left
            equal = [(span[1] - (span[1] - span[0]) * (k + 1) / n, span[1] - (span[1] - span[0]) * k / n) for k in range(n)]
            piece_of, joined = [], []
            for k in sorted(e["pieces"]):
                u = e["pieces"][k]["units"]; piece_of += [k] * len(u); joined += [len(u) >= 2] * len(u)
            feel = None; why = None
            if with_feeler:
                feel = []
                for k in sorted(e["pieces"]):
                    p = e["pieces"][k]; m = len(p["units"]); start = len(feel)
                    if m == 1: feel.append(tuple(w["cells"][start]))
                    elif p["feel"] is None: why = p["why"]; feel = None; break
                    else: feel += [tuple(c) for c in p["feel"]]
            words.append(dict(doc=doc, page=pn, line=e["line"], word=e["word"], text=letters, box=e["box"],
                              cutter=[tuple(c) for c in w["cells"]], nchar=w["nchar"], equal=equal, feeler=feel, feel_why=why,
                              piece_of=piece_of, joined=joined, feel_read=[p.get("feel_read") for p in e["pieces"].values() if p.get("feel_read")],
                              split=("unseen" if with_feeler else "fixture"),
                              lig=any(u == "لا" for p in e["pieces"].values() for u in p["units"])))
        (OUT / "words").mkdir(parents=True, exist_ok=True)
        json.dump(words, open(dst, "w"), ensure_ascii=False)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
        nf = sum(w["feeler"] is not None for w in words)
        print(f"{doc} p{pn}: PDF words {len(pw)}, matched {len(words)}, with feeler boxes {nf}, {time.time() - t:.0f}s, peak {peak:.2f} GB", flush=True)


def main():
    for doc, pages in FIXTURE.items(): collect(doc, pages, False)
    from methods import hybrid_ctc_geo as H
    for doc, pages in UNSEEN.items():
        if all((OUT / "words" / f"{doc}_p{p}.json").exists() for p in pages): continue
        data = bench.load(doc); model = H.learn(data["train"]); del data
        collect(doc, pages, True, model); del model


if __name__ == "__main__":
    main()
