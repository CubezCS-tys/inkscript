"""Experiment 69, step 1: the pages that hold experiment 66's judged fixes, with their features, and the stratified
choice of ~40 pages.  -> out/candidates.json, out/pages69.json (the windows run69 sends: one page each)

Page quality ("faded / poor") is measured from Azure's words on the page: the share of words read below 0.80
confidence and the median confidence (a worn, faded or tan scan lowers both), and checked by eye on the renders.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict

import common69 as C
import run43  # noqa: E402  (43_rehearsal)
from masters43 import ST  # noqa: E402


def page_quality(a: dict, p: int) -> dict:
    az = ST.azure(a)
    ws = [w.get("confidence") for w in az["pages"][p - 1].get("words", []) if w.get("confidence") is not None]
    ST._az.pop(a["stem"], None)
    if not ws:
        return dict(words=0, med=None, low=None)
    return dict(words=len(ws), med=round(statistics.median(ws), 3), low=round(sum(c < 0.8 for c in ws) / len(ws), 3))


def saved_fixes_on_page(run_folder, a, chunk, p):
    rec = json.loads((C.E43 / "out" / run_folder / "raw" / f"{chunk}.json").read_text(encoding="utf-8"))
    n = sum(1 for f in rec["answer"].get("fixes") or [] if isinstance(f, dict) and str(f.get("line", "")).split(":")[0] == str(p))
    return n, rec.get("prompt"), rec.get("mode")


def main():
    J = C.judged()
    arts = {}
    for run, (folder, which) in C.RUNS.items():
        for a in run43.articles(which):
            arts[(run, a["stem"])] = a
    pages = defaultdict(list)
    for r in J.values():
        pages[(r["run"], r["stem"], r["page"], r["chunk"])].append(r)
    cands = []
    for (run, stem, p, chunk), rs in pages.items():
        a = arts[(run, stem)]
        folder, which = C.RUNS[run]
        ST.PAGES = (C.E43 / "out" / "pages") if which in "bcd" else (ST.OUT / "pages")
        q = page_quality(a, p)
        nfix, prompt, mode = saved_fixes_on_page(folder, a, chunk, p)
        labs = Counter(r["lab"] for r in rs)
        cands.append(dict(run=run, stem=stem, page=p, chunk=chunk, journal=a.get("journal"), year=a.get("year"),
                          decade=a.get("decade"), sids=[r["sid"] for r in rs], labs=dict(labs), q=q,
                          saved_fixes_on_page=nfix, saved_prompt=prompt, saved_mode=mode,
                          image=str(ST.page_image(a, p))))
    C.jdump(C.OUT / "candidates.json", cands)
    print(len(cands), "candidate pages")

    def h(c):
        return hashlib.md5(f"{c['stem']}:{c['page']}".encode()).hexdigest()

    def poor(c):
        return (c["q"]["low"] or 0) >= 0.12 or (c["q"]["med"] or 1) < 0.95

    def kind(c):
        L = c["labs"]
        if L.get("B"):
            return "bad"
        if L.get("M"):
            return "misprint"
        if L.get("G"):
            return "good_poor" if poor(c) else "good_clean"
        return "unclear"
    for c in cands:
        c["stratum"], c["poor"] = kind(c), poor(c)
    by = defaultdict(list)
    for c in cands:
        if c["saved_fixes_on_page"] <= 25:            # a page with dozens of fixes would swamp the judging
            by[c["stratum"]].append(c)
    print({k: len(v) for k, v in by.items()}, "poor among bad/misprint:",
          sum(c["poor"] for c in by["bad"] + by["misprint"]))
    want = dict(bad=12, misprint=12, good_poor=10, good_clean=10)
    chosen = []
    for s, n in want.items():
        pool = sorted(by[s], key=h)
        # spread over journals: one page per journal first, then the rest
        seen, first, rest = set(), [], []
        for c in pool:
            (rest if c["stem"][:4] in seen else first).append(c)
            seen.add(c["stem"][:4])
        chosen += (first + rest)[:n]
    C.jdump(C.OUT / "pages69.json", chosen)
    print(len(chosen), "chosen", Counter(c["stratum"] for c in chosen), Counter(c["run"] for c in chosen),
          Counter(c["decade"] for c in chosen), "journals", len({c["stem"][:4] for c in chosen}),
          "poor", sum(c["poor"] for c in chosen), "saved fixes", sum(c["saved_fixes_on_page"] for c in chosen))


if __name__ == "__main__":
    main()
