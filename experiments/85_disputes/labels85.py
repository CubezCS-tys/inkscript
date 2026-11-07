"""Experiment 85, step 3a: training labels for the settled disputes.

    .venv/bin/python experiments/85_disputes/labels85.py     -> out/labels/labels_v6.jsonl (+ summary)

The label of a settled line is Azure's own line with its LETTERS made to follow the settled reading, and Azure's
punctuation kept where it is (the judge was told to ignore punctuation; the trainer has always seen Azure's
punctuation).  `project(azure, truth)` aligns Azure's words (punctuation peeled off each word) with the truth's words
(comparison form) and replaces only the letters; where the word count differs (a space split or joined), the truth's
words replace the run and the run's outer punctuation is kept.  The result's comparison form must equal the truth's;
otherwise the line falls back to the truth candidate's own text (counted).

Settled lines:
  rule85   hamza on alif only, Azure writes the hamza, v1 and v3 a bare alif -> v1's alifs (42,404 lines, all eras);
  judged   the judge's truth: the candidate it called right, or its own corrected reading when its blind reading
           said the same; unreadable lines and "none" verdicts that changed the blind reading are dropped.
Every other held line stays dropped (labels: null), as in v3's training set.  Locked / held-out journals refused.
"""
from __future__ import annotations

import difflib
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common85 import OUT, clean_label, guard, sform  # noqa: E402

L = OUT / "labels"
_ISP = lambda c: unicodedata.category(c)[0] in "PS" or c == "_"  # noqa: E731
ALIFS = set("اأإآٱ")


def split_tok(tok: str):
    """'((دمشق)،' -> ('((', 'دمشق', ')،'); a token with punctuation inside keeps it in the core."""
    i, j = 0, len(tok)
    while i < j and _ISP(tok[i]):
        i += 1
    while j > i and _ISP(tok[j - 1]):
        j -= 1
    return tok[:i], tok[i:j], tok[j:]


def project(azure: str, truth: str) -> str | None:
    A = clean_label(azure).split(" ")
    parts = [split_tok(t) for t in A]
    core_idx = [k for k, p in enumerate(parts) if p[1]]
    acore = [sform(parts[k][1]) for k in core_idx]
    T = sform(truth).split(" ") if sform(truth) else []
    out = list(A)
    sm = difflib.SequenceMatcher(a=acore, b=T, autojunk=False)
    repl = {}
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal":
            continue
        if op == "replace" and a1 - a0 == b1 - b0:
            for x, y in zip(range(a0, a1), range(b0, b1)):
                k = core_idx[x]
                pre, core, suf = parts[k]
                if sform(core) != core.replace(" ", ""):         # punctuation inside the core: give up on it
                    if any(_ISP(c) for c in core):
                        return None
                repl[k] = pre + T[y] + suf
        elif op in ("replace", "delete"):
            ks = [core_idx[x] for x in range(a0, a1)]
            pre, suf = parts[ks[0]][0], parts[ks[-1]][2]
            if any(_ISP(c) for k in ks for c in parts[k][1]):
                return None
            repl[ks[0]] = (pre + " ".join(T[b0:b1]) + suf) if b1 > b0 else (pre + suf)
            for k in ks[1:]:
                repl[k] = parts[k][0] + parts[k][2]
        elif op == "insert":
            # new words before Azure's core word a0 (or after the last one)
            if a0 < len(core_idx):
                k = core_idx[a0]
                repl[k] = " ".join(T[b0:b1]) + " " + repl.get(k, A[k])
            elif core_idx:
                k = core_idx[-1]
                repl[k] = repl.get(k, A[k]) + " " + " ".join(T[b0:b1])
            else:
                return None
    for k, v in repl.items():
        out[k] = v
    lab = re.sub(r"\s+", " ", " ".join(x for x in out if x)).strip()
    return lab if sform(lab) == sform(truth) else None


def alif_transfer(azure: str, v1: str) -> str | None:
    """Azure's line with each alif-family letter replaced by v1's corresponding one (same order)."""
    a, b = clean_label(azure), clean_label(v1)
    ba = [c for c in b if c in ALIFS]
    if sum(c in ALIFS for c in a) != len(ba):
        return None
    it = iter(ba)
    lab = "".join(next(it) if c in ALIFS else c for c in a)
    return lab if sform(lab) == sform(v1) else None


def judged_ok() -> dict[str, str]:
    """Judged truths usable as labels: a candidate the judge called right, or its own reading when the verdict is
    "none" AND its blind reading already said the same (self-consistent); changed-its-mind "none" lines are left out."""
    from est85 import jl, truth_of
    out = {}
    for a in jl(OUT / "judge/answers.jsonl"):
        t = truth_of(a)
        if t is None or not sform(t):
            continue
        if a["verdict"] == "match" or sform(a["blind"]) == sform(a["reading"]):
            out[a["key"]] = t
    return out


def main():
    """Three label files (every held key; label null = dropped as in v3's training):
      labels_v6r.jsonl  judged + rule85        labels_v6j.jsonl  judged only        labels_ctl.jsonl  none (v3's set)"""
    L.mkdir(parents=True, exist_ok=True)
    T = judged_ok()
    c = Counter()
    rows = []
    with gzip.open(OUT / "types/held_typed.jsonl.gz", "rt", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            k = d["key"]
            lab, how = None, "held"
            if k in T:
                t = T[k]
                for cand in (d["azure"], d["v1"], d["v3"]):
                    if sform(cand) == sform(t):
                        t = cand
                        break
                lab, how = project(d["azure"], t), "judged"
                if lab is None:
                    lab, how = clean_label(t), "judged_fallback"
            elif d["type"] == "hamza_alif" and d["dir"] == "az" and d["vote"] == "v1":
                lab = alif_transfer(d["azure"], d["v1"])
                how = "rule85" if lab is not None else "rule85_failed"
            c[how] += 1
            rows.append(dict(key=k, label=lab, how=how))
    guard([r["key"] for r in rows if r["label"] is not None], "training label")
    keep = {"v6r": ("judged", "judged_fallback", "rule85"), "v6j": ("judged", "judged_fallback"), "ctl": ()}
    for name, hows in keep.items():
        with open(L / f"labels_{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(dict(key=r["key"], label=r["label"] if r["how"] in hows else None),
                                   ensure_ascii=False) + "\n")
    (L / "labels_summary.json").write_text(json.dumps(c, indent=1))
    print(dict(c))


if __name__ == "__main__":
    main()
