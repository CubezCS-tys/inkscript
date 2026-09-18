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
    strip = lambda t: re.sub(r"[\u064B-\u0652\u0670\W_]", "", t)
    for sig, ps in groups.items():
        texts = Counter(norm(p["text"]) for p in ps)
        if len(texts) > 1:
            top = texts.most_common(1)[0][0]
            # What kind of disagreement? A reading that merely EXTENDS the other
            # (`وهو` beside `هو`, `فقال` beside `قال`) is almost always Azure's
            # box covering only the shared ligature while the extra letter's
            # ink sits outside it — a box artefact, not a reading to judge.
            # Readings that differ by a substitution (`379`/`973`, `نوه`/`ذوه`)
            # are the ones worth a person's second.
            bases = {strip(t) for t in texts}
            kind = "substitution"
            if len(bases) == 1:
                kind = "marks-or-punctuation"
            elif (core := min(bases, key=len)) and all(core in b for b in bases):
                kind = "extension"
            conflicts.append(dict(sig=sig, kind=kind, readings={t: n for t, n in texts.items()},
                                  suspects=[dict(page=p["page"], box=p["box"], text=p["text"], rot=p.get("rot", 0))
                                            for p in ps if norm(p["text"]) != top]))
    order = {"substitution": 0, "marks-or-punctuation": 1, "extension": 2}
    conflicts.sort(key=lambda c: order[c["kind"]])
    numbers = [dict(page=p["page"], box=p["box"], text=p["text"], rot=p.get("rot", 0)) for p in doc["placements"] if DIGITS.search(p["text"])]
    repeated = sum(len(ps) for ps in groups.values() if len(ps) > 1)
    return dict(words=len(doc["placements"]), repeated_ink=repeated, groups=sum(1 for ps in groups.values() if len(ps) > 1),
                conflicts=conflicts, kinds=dict(Counter(c["kind"] for c in conflicts)), numbers=numbers)
