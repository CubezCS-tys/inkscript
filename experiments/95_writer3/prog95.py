"""Experiment 95: experiment 87's letter programs, completed for the texts this experiment writes.

87's font programs hold only the glyphs its own texts used.  A sibling, a planted variant or a new journal's line can
need a glyph that is not there, and the writer would write NOTHING for it: a wrong candidate would lose for a reason
that has nothing to do with the ink.  So every glyph HarfBuzz uses on our texts is built the same way as 87's
(fontprog87.glyph_program, unchanged: exp 82's learned centre line cut into edges) and added.

    python prog95.py [cjobs|journals|lines82|all]   -> out/programs/font_<name>.json (87's glyphs + the new ones),
                                                     out/programs/alqalam_strokes.json (copied)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

from common95 import D95, E, OUT, PROG95, jl

sys.path.insert(0, str(E / "87_writer"))
P87 = E / "87_writer/out/programs"
FONTS = E / "78_synthetic_lines/out/fonts"


def texts_of(what: str):
    T = {}
    if what in ("cjobs", "all"):
        for s in ("synth", "pool", "held", "judged"):
            for g in jl(D95 / f"cjobs_{s}.jsonl"):
                for c in g["cands"]:
                    T.setdefault(g["lib"], set()).add(c)
    if what in ("journals", "all"):
        libs = json.loads((D95 / "screen_libs.json").read_text()) if (D95 / "screen_libs.json").exists() else {}
        for r in jl(D95 / "journals.jsonl"):
            for lib in libs.get(r["jcode"], []):
                T.setdefault(lib, set()).add(r["text"])
    if what in ("lines82", "all"):
        for r in jl(D95 / "lines82.jsonl"):
            T.setdefault(r["lib"], set()).add(r["text"])
    return T


def main(what: str):
    import uharfbuzz as hb
    os.environ.setdefault("THREADS", "2")
    import fontprog87 as FP
    PROG95.mkdir(parents=True, exist_ok=True)
    if not (PROG95 / "alqalam_strokes.json").exists():
        shutil.copy(P87 / "alqalam_strokes.json", PROG95 / "alqalam_strokes.json")
    T = texts_of(what)
    for lib, texts in sorted(T.items()):
        if lib == "alqalam":
            continue
        nm = lib[5:]
        dst = PROG95 / f"font_{nm}.json"
        d = json.loads((dst if dst.exists() else P87 / f"font_{nm}.json").read_text())
        fp = FONTS / d["font"]
        f = hb.Font(hb.Face(hb.Blob.from_file_path(str(fp))))
        used = set()
        for t in texts:
            buf = hb.Buffer()
            buf.add_str(t)
            buf.guess_segment_properties()
            hb.shape(f, buf, {})
            used.update(i.codepoint for i in (buf.glyph_infos or []))
        have = {int(k) for k in d["glyphs"]}
        new = sorted(used - have)
        t0 = time.time()
        for g in new:
            strokes, _, _ = FP.glyph_program(fp, g)
            d["glyphs"][str(g)] = strokes
        d["n_glyphs"] = len(d["glyphs"])
        d.setdefault("added95", []).extend(new)
        dst.write_text(json.dumps(d))
        print(f"{nm}: {len(texts)} texts, {len(used)} glyphs used, {len(new)} built ({time.time() - t0:.0f} s)", flush=True)
    # every font 87 has, so the writer finds all of them in one folder
    for p in P87.glob("font_*.json"):
        if not (PROG95 / p.name).exists():
            shutil.copy(p, PROG95 / p.name)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
