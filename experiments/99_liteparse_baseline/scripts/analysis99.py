#!/usr/bin/env python3
"""Experiment 99 breakdowns (repo .venv python): R1 per mode split by where the PDF's text layer came from
(born digital: Word / InDesign / Distiller ...; scanned with an OCR text layer: ScanToPDF / Image2PDF / PaperStream /
Photoshop ...), and the kinds of text-layer failure (line doubled, empty, exact, close, far).
-> out/scores/breakdown.json"""
import collections as C
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert99 as V  # noqa: E402
sys.path.insert(0, V.P97)
import score97 as S  # noqa: E402
from common97 import lev  # noqa: E402

E = V.E
inv = {r["stem"]: r for r in json.load(open(f"{E}/out/inventory.json"))}
SCAN = ("ScanToPDF", "Image2PDF", "PaperStream", "Adobe Photoshop")


def origin(stem):
    c = (inv[stem]["creator"] or "") + " " + (inv[stem]["producer"] or "")
    return "scan + OCR text layer" if any(k in c for k in SCAN) else "born digital"


def main():
    out = {}
    for m in ("text", "tess", "nano"):
        f = f"{E}/out/scores/r1_lines_{m}.jsonl"
        if not os.path.exists(f):
            continue
        acc = C.defaultdict(lambda: [0, 0, 0, 0, 0])
        kinds = C.Counter()
        for x in open(f):
            r = json.loads(x)
            t = r["truth"]
            if not t:
                continue
            stem = r["id"].rsplit("_p", 1)[0]
            o = origin(stem)
            for key, txt in ((o + ", as returned", r["liteparse"]), (o + ", pieces right to left", r["liteparse_rtl_reordered"])):
                a = S.no_punct(S.r1_fold(txt or "")); b = S.no_punct(S.r1_fold(t))
                z = acc[key]
                z[0] += lev(a, b); z[1] += len(b); z[2] += lev(a.split(), b.split()); z[3] += len(b.split()); z[4] += 1
            L = r["liteparse"] or ""
            k = ("empty" if not L else "exact" if L == t else "doubled (text twice)" if len(L) > 1.6 * len(t) else
                 "close (< 15% letters off)" if lev(L, t) < 0.15 * len(t) else "far")
            kinds[(o, k)] += 1
        out[m] = dict(folded_no_punct={k: dict(lines=v[4], letter_error=round(v[0] / max(1, v[1]), 4),
                                               word_error=round(v[2] / max(1, v[3]), 4)) for k, v in sorted(acc.items())},
                      line_kinds={f"{o}: {k}": n for (o, k), n in sorted(kinds.items())})
    pages = C.Counter(origin(a["stem"]) for a in json.load(open(f"{V.P97}/LOCKED_EVAL.json"))["articles"]
                      for _ in set(a["pages"].values()))
    out["exam_pages_by_origin"] = dict(pages)
    json.dump(out, open(f"{E}/out/scores/breakdown.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
