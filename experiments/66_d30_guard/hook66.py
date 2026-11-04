"""Experiment 66: the proposed hook, end to end on real saved answers, in memory only (nothing written).

    hook66.py STEM [STEM ...]   for each article: today's rules43 (with the letter fix, as lettersfix43 runs it) with
                                and without the guard, then experiment 41's Store over the chunk answers; prints the
                                fixes applied / refused and the sic flags Store accepts, and the lines whose text changes
The guard is installed the way the patch would call it: just before rules43's last rule `fixes(ans, log)`.
"""
from __future__ import annotations

import sys

import common66 as C

C.e43_path()
import masters43 as M43  # noqa: E402
import replay43 as RP  # noqa: E402
import rules43 as RU  # noqa: E402
import run43  # noqa: E402
import letters43 as LT  # noqa: E402
import d30guard43 as G  # noqa: E402
from masters43 import ST  # noqa: E402

cur = C.current_stems()
orig_tmc, orig_fixes = RU.table_missed_cells, RU.fixes


def tmc(ans, lines, words, log):                      # the letter fix, as lettersfix43.install adds it
    orig_tmc(ans, lines, words, log)
    LT.letters_fix(ans, lines, log)


RU.table_missed_cells = tmc
STATE = {"words": None, "lines": None, "on": False}


def fixes_with_guard(ans, log):
    if STATE["on"]:
        G.guard(ans, STATE["lines"], STATE["words"], log)
    orig_fixes(ans, log)


RU.fixes = fixes_with_guard


def build(a, folder, on):
    STATE["on"] = on
    answers = []
    for x, y in ST.chunks(a):
        rec = ST.jl(C.E43 / "out" / folder / "raw" / f"{a['stem']}_c{x:03d}-{y:03d}.json")
        STATE["lines"], STATE["words"] = RP.chunk_lines(a, x, y), M43.azure_words(a)
        ans, log = RU.normalize(rec["answer"], STATE["lines"], STATE["words"])
        answers.append(ans)
    pages = list(range(a["first"], a["last"] + 1))
    return ST.Store(a, pages, answers), answers


for stem in sys.argv[1:]:
    run = cur[stem]
    folder, which = C.RUNS[run]
    ST.PAGES = C.E43 / "out" / "pages" if which != "a" else ST.OUT / "pages"
    a = next(x for x in run43.articles(which) if x["stem"] == stem)
    s0, _ = build(a, folder, False)
    s1, ans1 = build(a, folder, True)
    sug = [s for v in s1.sic.values() for s in v if s.get("kind") == "model-suggestion"]
    print(f"{stem} ({run}): fixes applied {len(s0.applied)} -> {len(s1.applied)}; sic flags "
          f"{sum(map(len, s0.sic.values()))} -> {sum(map(len, s1.sic.values()))} (model suggestions {len(sug)}); "
          f"sic rejected {len(s1.sic_rejected)}")
    for lid in s1.lines:
        t0, t1 = s0.lines.get(lid, {}).get("text"), s1.lines[lid]["text"]
        if t0 != t1:
            print(f"  {lid}: today «{t0}»\n  {' ' * len(lid)}  guard «{t1}»")
    ST._az.clear()
