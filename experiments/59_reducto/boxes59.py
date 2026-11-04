"""Experiment 59: can Reducto's word boxes anchor values to the ink?  (r1 word citations against Azure's lines)

    /home/appuser/inkscript/.venv/bin/python boxes59.py   -> out/boxes_scores.json

For every page sent: share of Reducto words that have a box; share of those boxes lying on an Azure line (>= 50% of
the word box inside one Azure line box, Azure = the boxes our ALTO and faithful PDFs use); and, for words whose text
matches an Azure word on that line (folded), whether the box also lies inside Azure's word box (>= 50%).
Also the Extract citations: share of extracted values with at least one box, and how big the box is (a whole block
or the value's own words).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "41_azure_structure"))
import score41 as S  # noqa: E402
from structure import azure  # noqa: E402
from inkscript.gold.text import folded  # noqa: E402

OUT = HERE / "out"


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def az_page(stem, p, sample):
    pg = azure(sample[stem])["pages"][p - 1]
    s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
    W, H = pg["width"] * s, pg["height"] * s
    lines = []
    for ln in pg.get("lines", []):
        xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
        lines.append([min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s])
    words = []
    for w in pg.get("words", []):
        xs, ys = w["polygon"][0::2], w["polygon"][1::2]
        words.append(([min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s], folded(w["content"])))
    return W, H, np.array(lines, float).reshape(-1, 4), words


def frac_inside(b, B):
    if not len(B):
        return np.zeros(0)
    w = np.clip(np.minimum(b[2], B[:, 2]) - np.maximum(b[0], B[:, 0]), 0, None)
    h = np.clip(np.minimum(b[3], B[:, 3]) - np.maximum(b[1], B[:, 1]), 0, None)
    return w * h / max((b[2] - b[0]) * (b[3] - b[1]), 1.0)


def main():
    sample = {a["stem"]: a for a in S.sample()}
    sample.update({a["stem"]: a for a in jl(E / "43_rehearsal/sample43b.json")["articles"]})
    tot = dict(words=0, with_box=0, on_line=0, same_word=0, same_word_inside=0)
    per = []
    for u in jl(OUT / "units59.json"):
        stem, p = u["id"].rsplit("_p", 1)
        p = int(p)
        W, H, L, AW = az_page(stem, p, sample)
        AWB = np.array([w[0] for w in AW], float).reshape(-1, 4)
        j = jl(OUT / "reducto/r1" / f"{u['id']}.json")
        t = dict(words=0, with_box=0, on_line=0, same_word=0, same_word_inside=0)
        for ch in j["chunks_full"]:
            for b in ch["blocks"]:
                for w in (b.get("extra") or {}).get("word_citations") or []:
                    t["words"] += 1
                    bb = w.get("bbox")
                    if not bb:
                        continue
                    t["with_box"] += 1
                    box = [bb["left"] * W, bb["top"] * H, (bb["left"] + bb["width"]) * W, (bb["top"] + bb["height"]) * H]
                    if len(L) and frac_inside(box, L).max() >= 0.5:
                        t["on_line"] += 1
                    fw = folded(w["text"])
                    if not len(AWB):
                        continue
                    fi = frac_inside(box, AWB)
                    # the Azure word with the same text nearest to this box
                    cand = [k for k, (_, tx) in enumerate(AW) if tx == fw]
                    if cand:
                        t["same_word"] += 1
                        if max(fi[k] for k in cand) >= 0.5:
                            t["same_word_inside"] += 1
        for k in tot:
            tot[k] += t[k]
        per.append(dict(id=u["id"], **t))
    # Extract citations
    ex = dict(values=0, with_box=0, word_level=0)
    for d in (OUT / "extract").glob("*_*"):
        for f in d.glob("*.json"):
            r = jl(f)["result"]

            def walk(x):
                if isinstance(x, dict) and "value" in x and "citations" in x:
                    if x["value"] not in (None, "", []):
                        ex["values"] += 1
                        c = x["citations"] or []
                        if c:
                            ex["with_box"] += 1
                            pb = c[0].get("parentBlock") or {}
                            bb, pbb = c[0].get("bbox") or {}, pb.get("bbox") or {}
                            if pbb and bb and bb.get("width", 1) * bb.get("height", 1) < 0.8 * pbb.get("width", 1) * pbb.get("height", 1):
                                ex["word_level"] += 1
                    walk(x["value"])
                elif isinstance(x, dict):
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            walk(r)
    res = dict(parse=tot, extract=ex, pages=per)
    (OUT / "boxes_scores.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(dict(parse=tot, extract=ex), indent=1))
    print(f"words with a box {tot['with_box'] / tot['words']:.3f}; on an Azure line {tot['on_line'] / tot['with_box']:.3f}; "
          f"inside the same Azure word {tot['same_word_inside'] / max(tot['same_word'], 1):.3f}")


if __name__ == "__main__":
    main()
