"""Print what the layout title rule sees on page 1 (each paragraph: size vs body, words, furniture/footnote, and
where the loop stops).   PYTHONPATH=src .venv/bin/python experiments/28_scale/front_trace.py STEM..."""
import re, sys
from pathlib import Path
from inkscript.enrich import structure as S
from inkscript.enrich.document import load
OUT = Path(__file__).resolve().parent / "out"
orig = S._front_by_layout
def trace(doc, info, kinds, furniture, note_word, body_h):
    p1 = [i for i, inf in enumerate(info) if inf[0] == min(doc["pages"])]
    print(f"  body_h={body_h:.1f}")
    for i in p1[:25]:
        pg, ws, b, H, Wd, txt = info[i]
        k = S.key(txt); h = S._h(ws)
        tag = "FURN" if i in furniture else ("FOOT" if kinds[i] == "footnote" else "")
        stop = (len(ws) > 12 and h < 1.15 * body_h) or k in S.ABSTRACT or txt.strip().lower().rstrip(":") in S.ABSTRACT
        print(f"  [{i}] {h / body_h:4.2f}x {len(ws):3d}w y={b[1] / H:.2f} {tag:4s} {'STOP' if stop and not tag else ''} {txt[:70]}")
    r = orig(doc, info, kinds, furniture, note_word, body_h)
    print("  ->", r.get("title"))
    return r
S._front_by_layout = trace
for stem in sys.argv[1:]:
    print(stem)
    az = OUT / "azure" / stem
    S.analyse(load(az / f"{stem}.json"), S.read_meta(stem, []), az / f"{stem}.pdf")
