"""The shape alphabet as a witness against the OCR: the same ink should carry
the same text. Words whose ink signature matches another's but whose text
differs are contradictions — one reading is wrong — and go on the review
list, with every number on the page beside them (a wrong digit is the error
that hurts most and shows least)."""
from __future__ import annotations
import json, re, unicodedata
from collections import defaultdict, Counter
from pathlib import Path

from ..text import norm

DIGITS = re.compile(r"[0-9٠-٩۰-۹]")


def review(shapes_json: Path) -> dict:
    doc = json.loads(Path(shapes_json).read_text(encoding="utf-8"))
    groups = defaultdict(list)
    for p in doc["placements"]:
        if p.get("sig"):
            groups[p["sig"]].append(p)
    conflicts = []
    for sig, ps in groups.items():
        texts = Counter(norm(p["text"]) for p in ps)
        if len(texts) > 1:
            top = texts.most_common(1)[0][0]
            conflicts.append(dict(sig=sig, readings={t: n for t, n in texts.items()},
                                  suspects=[dict(page=p["page"], box=p["box"], text=p["text"])
                                            for p in ps if norm(p["text"]) != top]))
    numbers = [dict(page=p["page"], box=p["box"], text=p["text"]) for p in doc["placements"] if DIGITS.search(p["text"])]
    repeated = sum(len(ps) for ps in groups.values() if len(ps) > 1)
    return dict(words=len(doc["placements"]), repeated_ink=repeated, groups=sum(1 for ps in groups.values() if len(ps) > 1),
                conflicts=conflicts, numbers=numbers)
