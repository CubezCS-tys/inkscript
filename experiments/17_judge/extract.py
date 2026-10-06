"""Read unseen pages with the feeler and keep every piece: Azure's reading, the feeler's, and the ink to show a judge.

Pages: the bench books' pages outside every split of bench.SUITE (never trained, tuned or tested on), minus
sideways pages (Azure angle ~ 90) and pages whose words are mostly Latin. Pieces are extracted exactly as
bench.build_cache does (reader.pieces_of + reader.blind, the same filters); the only addition is that the word a
piece belongs to is kept, so the judge can be shown the whole word in its line.

    out/torchenv python extract.py [DOC:PAGES ...]       # default: every eligible page
Writes out/pieces/<doc>_p<page>.json (+ crops are made later by judge.py from the page image).
Run with experiments/16_feel/out/torchenv/bin/python (CPU torch). One process at a time.
"""
import sys, json, time, resource
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
FEEL = HERE.parent / "16_feel"
sys.path.insert(0, str(FEEL)); sys.path.insert(0, str(HERE.parent / "10_atlas_reader"))
OUT = HERE / "out"

import bench                                                            # noqa: E402  (16_feel/bench.py, imported, not edited)

# Pages never used by experiment 16 (bench.SUITE splits), upright, mostly Arabic (checked 2026-10-06 from Azure's
# JSON: angle and the share of words carrying an Arabic letter). 0582 has no unused page (all five are in splits).
PAGES = {
    "0618": [1, 16],
    "1036": [1, 10],
    "0772": [6, 14, 16, 17, 18, 19, 20, 22, 23, 25, 27, 29, 30, 32, 34, 35, 36, 37, 39, 40, 41],
}


def eligible(doc, pages):
    """Guard: refuse any page that is in a bench split, sideways, or mostly Latin."""
    cfg = bench.SUITE[doc]; used = set(cfg["train"]) | set(cfg["dev"]) | set(cfg["test"])
    j = json.load(open(cfg["azure"])); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
    ok = []
    for pn in pages:
        p = az[pn]; ws = p.get("words", [])
        arab = sum(1 for w in ws if any("؀" <= c <= "ۿ" for c in w["content"]))
        if pn in used or abs(p.get("angle", 0) or 0) > 45 or not ws or arab < 0.6 * len(ws):
            print(f"skip {doc} p{pn}", flush=True); continue
        ok.append(pn)
    return ok


def pieces_with_words(azure, scan, pages):
    """reader.pieces_of, verbatim in what it yields, plus the word and the piece's place in it."""
    import json as _j, cv2, fitz
    from reader import load_azure, page_blobs, layout_page, line_geometry, MARKS, split_word, P
    words, _, dims = load_azure(Path(azure)); j = _j.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
    doc = fitz.open(scan)
    for pn in pages:
        pw = [w for w in words if w["page"] == pn]; pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
        W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
        for li, L in enumerate(lines):
            bl = [b for w in L if w["blobs"] for b in w["blobs"]]
            if not bl: continue
            lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
            for wi, w in enumerate(L):
                if not w["blobs"] or MARKS.search(w["text"]): continue
                pcs = split_word(w, lh)
                for k, pc in enumerate(pcs):
                    uf = P.units_forms(pc["text"].strip())
                    if uf and len(set(uf[1]) & {"iso"}) <= 1 and uf[1].count("init") <= 1:
                        yield pn, li, wi, w, pcs, k, pc, uf, lg


def box_of(blobs):
    return [int(min(b["x"] for b in blobs)), int(min(b["y"] for b in blobs)),
            int(max(b["x"] + b["w"] for b in blobs)), int(max(b["y"] + b["h"] for b in blobs))]


def main(args):
    from reader import blind
    from methods import hybrid_ctc_geo as H
    todo = {}
    for a in args:
        d, ps = a.split(":"); todo[d] = [int(x) for x in ps.split(",")]
    todo = todo or PAGES
    (OUT / "pieces").mkdir(parents=True, exist_ok=True)
    for doc, pages in todo.items():
        pages = [p for p in eligible(doc, pages) if not (OUT / "pieces" / f"{doc}_p{p}.json").exists()]
        if not pages: continue
        t0 = time.time(); data = bench.load(doc); model = H.learn(data["train"]); del data
        print(doc, "model ready", round(time.time() - t0, 1), "s", flush=True)
        cfg = bench.SUITE[doc]
        for pn in pages:
            recs = []; t = time.time()
            for pn_, li, wi, w, pcs, k, pc, (units, forms), lg in pieces_with_words(str(cfg["azure"]), str(cfg["scan"]), [pn]):
                if not lg or lg["rise"] < 10: continue                   # bench.build_cache's filter
                q = blind(pc, lg)
                if q is None: continue                                   # bench scores these as unread; nothing to judge
                q.pop("cache", None)
                rec = dict(doc=doc, page=pn, units=units, forms=forms, rise=float(lg["rise"]), q=q)
                letters, cuts = H.read(model, rec)
                word_text = w["text"].strip() or w.get("az", "")
                recs.append(dict(
                    doc=doc, page=pn, line=li, word=wi, piece=k, npieces=len(pcs),
                    azure_piece=pc["text"].strip(), azure_units=[bench.base(u) for u in units],
                    feel_units=[bench.base(x) for x in letters],
                    word_text=word_text, piece_texts=[p["text"].strip() for p in pcs], piece_toks=[p.get("tok", 0) for p in pcs],
                    word_box=box_of(w["blobs"]), piece_box=box_of(pc["blobs"]), rise=float(lg["rise"])))
            n = len(recs); dis = sum(r["azure_units"] != r["feel_units"] for r in recs)
            json.dump(recs, open(OUT / "pieces" / f"{doc}_p{pn}.json", "w"), ensure_ascii=False)
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
            print(f"{doc} p{pn}: {n} pieces, {dis} disagree ({100 * dis / max(1, n):.1f}%), {time.time() - t:.0f}s, peak {peak:.2f} GB", flush=True)
        del model


if __name__ == "__main__":
    main(sys.argv[1:])
