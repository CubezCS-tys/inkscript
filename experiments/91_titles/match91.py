"""Experiment 91: find an article's TITLE lines on its page 1 by matching the catalogue title (marc.db 245 $a, $b) to
Azure's lines.  Pure functions (stdlib + rapidfuzz + exp 77's common77 + the scorer's `folded`), used locally to
develop the rule and on the GPU host (title91.py) to cut the lines.

MATCH RULE (fixed on experiment 77/80 training documents before any host run):
  - Page 1's non-empty Azure lines (common77.nonempty_lines, Azure order), with height (polygon) and top (share of
    the page).  The page's median line height is the body size.
  - Targets: the folded catalogue title T1, and T2 = title + subtitle when there is a subtitle.  Folded = the
    scorer's inkscript.gold.text.folded (vowel marks, hamza/alef forms, ى/ي, ة/ه, punctuation removed).
  - Every run of 1..6 CONSECUTIVE lines (Azure order) is compared with each target, word by word (difflib opcodes on
    the folded words).  Score = character similarity of the run's folded text to the target (rapidfuzz
    Levenshtein normalized similarity).  The best run wins (ties: the larger lines).
  - A run is CONFIDENT when: similarity >= 0.85; it covers the whole target title T1 (no more than 15% of T1's
    characters unmatched); its first line starts in the top 60% of the page (exp 89's title rule); every line is at
    median Arabic line is >= 0.9x the body size (running heads that repeat the title in small type fail here), or the
    page has <= 6 lines (a title page).  (Looked at on 900 local training documents: bold body-size titles are real
    titles, so the first draft's 1.1x was lowered.)
  - Inside a confident run, each line gets a verdict:
      agree    - every folded word of the line is matched to the catalogue, in order (opcode `equal`; a difference of
                 spacing only, و علم / وعلم, counts as equal; a footnote mark the catalogue lacks is tolerated);
      differ   - its words differ from the catalogue only by word-for-word replacements with character similarity
                 >= 0.5 (a misread word), at most max(1, min(2, words // 3)) per line; the catalogue words are kept
                 for the 3-way check (title91.py labels);
      extra    - the line has words the catalogue lacks (author, "عنوان البحث", a series name ...) -> not used;
      small    - the line is under 0.85x the body size (on pages with > 6 lines) -> not used;
      short    - fewer than 3 Arabic letters -> not used.
  - Label (strict, AS PRINTED): an `agree` line's label is Azure's own line (clean_label), because it matches the
    catalogue in folded form and Azure's letters, marks and punctuation are what the print shows; a `differ` line
    is decided in title91.py labels by the reader's vote (catalogue words where the reader's reading of the ink
    agrees with the catalogue in folded form, in the reader's own spelling; otherwise the line is dropped).
"""
from __future__ import annotations

import re
import statistics
import sys
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
for p in (HERE.parent / "77_scratch_reader", HERE / "x/e77", HERE.parent.parent / "src", HERE / "src"):
    if p.exists():
        sys.path.insert(0, str(p))
from common77 import clean_label, nonempty_lines  # noqa: E402
from inkscript.gold.text import folded  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
MAX_RUN = 6
SIM_MIN = 0.85
T1_MISS_MAX = 0.15
TOP_MAX = 0.60
LINE_REL_MIN = 0.85
RUN_REL_MIN = 0.90
WORD_SIM_MIN = 0.5
FOOTNOTE = re.compile(r"\d{1,2}|[a-z*]")


def fw(s: str) -> list[str]:
    return folded(clean_label(s or "")).split()


def sim(a: str, b: str) -> float:
    return Levenshtein.normalized_similarity(a, b)


def geom(pg: dict) -> list[dict]:
    L = nonempty_lines(pg)
    H = pg.get("height") or 1.0
    for l in L:
        p = l["poly"] or [0] * 8
        ys = p[1::2]
        l["hh"], l["y"] = max(ys) - min(ys), min(ys) / H
    return L


def match_page(pg: dict, title: str, subtitle: str = "") -> dict:
    """The best confident catalogue run on one page, with per-line verdicts.  Returns {ok, reason, ...}."""
    L = geom(pg)
    t1 = fw(title)
    if len("".join(t1)) < 6:
        return dict(ok=False, reason="title_short")
    targets = [("t", t1)]
    if subtitle and fw(subtitle):
        targets.append(("ts", t1 + fw(subtitle)))
    if not L:
        return dict(ok=False, reason="no_lines")
    med = statistics.median(l["hh"] for l in L) or 1.0
    W = [fw(l["text"]) for l in L]
    best = None
    for s in range(len(L)):
        if not W[s]:
            continue
        for n in range(1, MAX_RUN + 1):
            if s + n > len(L):
                break
            rw = [w for k in range(s, s + n) for w in W[k]]
            rt = " ".join(rw)
            for tn, tw in targets:
                sc = sim(rt, " ".join(tw))
                if best is None or sc > best[0] + 1e-9 or (abs(sc - best[0]) < 1e-9 and
                                                          statistics.median(L[k]["hh"] for k in range(s, s + n)) >
                                                          statistics.median(L[k]["hh"] for k in range(best[1], best[1] + best[2]))):
                    best = (sc, s, n, tn, tw)
    if best is None:
        return dict(ok=False, reason="no_words")
    sc, s, n, tn, tw = best
    run = L[s:s + n]
    rel = [l["hh"] / med for l in run]
    out = dict(sim=round(sc, 3), target=tn, start=s, n=n, top=round(run[0]["y"], 3), rel=[round(r, 2) for r in rel],
               lines_on_page=len(L))
    # word alignment of the run with the target
    rw, owner = [], []
    for k in range(s, s + n):
        for w in W[k]:
            rw.append(w)
            owner.append(k)
    sm = SequenceMatcher(None, rw, tw, autojunk=False)
    t1_chars = sum(len(w) for w in t1)
    t1_hit = 0
    per = {k: dict(eq=0, rep=[], ins=0, n=len(W[k])) for k in range(s, s + n)}
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal":
            for a in range(a0, a1):
                per[owner[a]]["eq"] += 1
            t1_hit += sum(len(tw[b]) for b in range(b0, b1) if b < len(t1))
        elif op == "replace":
            A, B = rw[a0:a1], tw[b0:b1]
            ks = {owner[a] for a in range(a0, a1)}
            if "".join(A) == "".join(B):              # spacing only (و علم / وعلم): the print's spacing is Azure's
                for a in range(a0, a1):
                    per[owner[a]]["eq"] += 1
                t1_hit += sum(len(tw[b]) for b in range(b0, b1) if b < len(t1))
            elif len(ks) == 1 and sim("".join(A), "".join(B)) >= WORD_SIM_MIN and len(A) <= 2 and len(B) <= 2:
                per[owner[a0]]["rep"].append((" ".join(A), " ".join(B), a0 - min(a for a in range(len(owner)) if owner[a] == owner[a0])))
                t1_hit += sum(len(tw[b]) for b in range(b0, b1) if b < len(t1))   # a misread word covers its place
            else:
                for a in range(a0, a1):
                    per[owner[a]]["ins"] += 1
        elif op == "insert":                        # catalogue words with no Azure word
            pass
        elif op == "delete":                        # Azure words the catalogue lacks (a footnote mark is fine)
            for a in range(a0, a1):
                if not FOOTNOTE.fullmatch(rw[a]):
                    per[owner[a]]["ins"] += 1
    miss = 1 - t1_hit / max(1, t1_chars)
    out["t1_miss"] = round(miss, 3)
    reasons = []
    if sc < SIM_MIN:
        reasons.append("sim")
    if miss > T1_MISS_MAX:
        reasons.append("t1_miss")
    if run[0]["y"] > TOP_MAX:
        reasons.append("low")
    arel = [r for r, l in zip(rel, run) if len(AR.findall(l["text"])) >= 3] or rel
    if len(L) > 6 and statistics.median(arel) < RUN_REL_MIN:
        reasons.append("size")
    out["ok"] = not reasons
    out["reason"] = "+".join(reasons) or "ok"
    lines = []
    for k in range(s, s + n):
        l, p = L[k], per[k]
        lab = clean_label(l["text"])
        if len(AR.findall(lab)) < 3:
            v = "short"
        elif l["hh"] / med < LINE_REL_MIN and len(L) > 6:
            v = "small"
        elif p["ins"]:
            v = "extra"
        elif p["rep"]:
            v = "differ" if len(p["rep"]) <= max(1, min(2, p["n"] // 3)) else "extra"
        else:
            v = "agree"
        lines.append(dict(i=l["i"], verdict=v, azure=lab, rep=p["rep"], rel=round(l["hh"] / med, 2), poly=l["poly"]))
    out["lines"] = lines
    return out
