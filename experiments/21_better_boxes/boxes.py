"""The cutter's letter boxes after the patch, for experiment 18's sample words, read back from the patched build's
vector PDFs exactly as experiment 18 read today's (collect.pdf_words: each glyph's advance in scan pixels; a glyph
still carrying several letters sliced equally, as Chrome does).

    ../../.venv/bin/python boxes.py [variant=new]     -> out/boxes_<variant>.json  {word id: [[x0, x1], ...] reading order}
"""
import sys, json
from pathlib import Path
import fitz
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]; E18 = REPO / "experiments/18_boxes"
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(E18))
import run18 as R
from build import DOCS


def pdf_words(doc, pno):
    """experiment 18's collect.pdf_words (copied: collect.py imports the feeler's torch stack), plus the word's y."""
    from inkscript.pdf.inspect import page_glyphs
    gl = page_glyphs(doc, pno - 1); words = []; by_font = {}
    for g in gl: by_font.setdefault(g["font"], []).append(g)
    for fn, gs in by_font.items():
        gs = sorted(gs, key=lambda g: g["box_px"][0]); cur = []
        for g in gs:
            if cur and g["box_px"][0] - cur[-1]["box_px"][2] > 0.6: words.append(cur); cur = []
            cur.append(g)
        if cur: words.append(cur)
    out = []
    for ws in words:
        vis = "".join(g["text"] for g in ws); cells = []
        for g in ws:
            x0, x1 = g["box_px"][0], g["box_px"][2]; n = max(1, len(g["text"]))
            cells += [((x0 + (x1 - x0) * i / n), (x0 + (x1 - x0) * (i + 1) / n), n) for i in range(n)]
        if len(cells) != len(vis): continue
        out.append(dict(text=vis[::-1], cells=[(a, b) for a, b, _ in cells][::-1], nchar=[n for _, _, n in cells][::-1],
                        x0=ws[0]["box_px"][0], x1=ws[-1]["box_px"][2], y=sum((g["box_px"][1] + g["box_px"][3]) / 2 for g in ws) / len(ws)))
    return out


def main(variant="new"):
    S = json.load(open(E18 / "out/sample.json")); res = {}; miss = []; cache = {}
    for s, ws in S.items():
        for w in ws:
            key = (w["doc"], w["page"]); path = HERE / f"out/build_{variant}/{w['doc']}/{DOCS[w['doc']]['stem']}_vector.pdf"
            if not path.exists(): continue
            if key not in cache:
                pdf = fitz.open(str(path))
                cache[key] = pdf_words(pdf, w["page"])
            ox0, ox1 = min(a for a, _ in w["cutter"]), max(b for _, b in w["cutter"]); y0, y1 = w["box"][1], w["box"][3]
            best = None
            for pw in cache[key]:
                if pw["text"] != w["text"]: continue
                ov = min(ox1, pw["x1"]) - max(ox0, pw["x0"])
                if ov > 0.6 * min(ox1 - ox0, pw["x1"] - pw["x0"]) and y0 - 10 <= pw["y"] <= y1 + 10 and (best is None or ov > best[0]): best = (ov, pw)
            if best is None: miss.append(R.wid(w)); continue
            res[R.wid(w)] = dict(cells=[list(c) for c in best[1]["cells"]], nchar=best[1]["nchar"])
    json.dump(res, open(HERE / f"out/boxes_{variant}.json", "w"))
    changed = sum(1 for s, ws in S.items() for w in ws if R.wid(w) in res and any(abs(a - c) > 0.5 or abs(b - d) > 0.5 for (a, b), (c, d) in zip(w["cutter"], res[R.wid(w)]["cells"])))
    print(f"{len(res)} words read back, {len(miss)} not found {miss[:10]}; words with any box changed vs experiment 18: {changed}")


if __name__ == "__main__":
    main(*sys.argv[1:])
