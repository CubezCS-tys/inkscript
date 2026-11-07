"""Experiment 79: the signal reader on the real held-out test lines, by era, beside Azure on the same lines.

    python analyse79.py out/res/<name>_pred_real.jsonl [...]     -> printed table + out/res/<name>_real_by_era.json

Line-level CER under `no_punct` (punctuation removed, spaces collapsed) against the owner's truth where the yardstick
maps the line (and lab doc 2's lines are compared to Azure only: the lab truth is page text, not lines).  Azure's own
CER on the same lines against the same truth is the image-side yardstick (Azure is experiment 77's label source, not
experiment 77's model; the image model's numbers come when experiment 77's predictions exist).
Eras from the yardstick's decades: 2000s -> modern; 1960s-1990s -> 1950-1999; pre-1960 -> pre-1960.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
_P = re.compile(r"[^\w\s]|_", re.UNICODE)
_W = re.compile(r"\s+")


def np_(s):
    return _W.sub(" ", _P.sub(" ", unicodedata.normalize("NFC", s or ""))).strip()


def era_of(dec):
    if dec == "2000s":
        return "modern"
    if dec == "pre-1960":
        return "pre-1960"
    return "1950-1999" if dec else "?"


def main(files):
    pages = json.loads((HERE.parent / "77_scratch_reader/out/test/pages.json").read_text(encoding="utf-8"))
    dec = {p["page_id"]: p.get("decade") for p in pages}
    for f in files:
        R = [json.loads(l) for l in open(f, encoding="utf-8")]
        agg = defaultdict(lambda: [0, 0, 0, 0])               # signal errors, azure errors, chars, lines
        for r in R:
            if not r.get("truth"):
                continue
            e = era_of(dec.get(r["page_id"]))
            t = np_(r["truth"])
            if not t:
                continue
            for k in (e, "all"):
                a = agg[k]
                a[0] += Levenshtein.distance(np_(r["pred"]), t)
                a[1] += Levenshtein.distance(np_(r["label"]), t)
                a[2] += len(t)
                a[3] += 1
        out = {k: dict(lines=v[3], chars=v[2], signal_cer=round(100 * v[0] / v[2], 2), azure_cer=round(100 * v[1] / v[2], 2))
               for k, v in agg.items()}
        name = Path(f).name.replace("_pred_real.jsonl", "")
        (Path(f).parent / f"{name}_real_by_era.json").write_text(json.dumps(out, indent=1))
        print(name, json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1:])
