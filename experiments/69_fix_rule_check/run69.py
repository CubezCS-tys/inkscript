"""Experiment 69, step 2: run a prompt variant on the chosen pages (out/pages69.json), one page per request (a window,
as experiment 65's v3.6 check did: Image 1 = the article's first page for context, page 1's lines as context, the
metadata asked), through experiment 43's run43 machinery (same request builder, Batch, cap, spend log).

    run69.py --variant v3.6 --tag v36 --cap 4 [--mode batch|standard] [--dry-run]

Answers: out/<tag>/raw/<stem>_cPPP-PPP.json (never experiment 43's folders). Spend: experiment 43's
out/gemini_spend.jsonl as usual (run43.C.SPEND is left where run43 points it). Page renders are read from the
existing render folders (symlinks in out/pages; nothing re-rendered).
"""
from __future__ import annotations

import argparse
import json
import os

import common69 as C
import prompts69
import run43
from masters43 import ST

P = run43.P
prompts69.install()
run43.OUT = C.OUT                       # raw_file / batch state / truncated answers -> experiment 69's out/
assert str(run43.C.SPEND).endswith("43_rehearsal/out/gemini_spend.jsonl")
run43.C.CACHE = C.OUT / "gemini_cache.jsonl"    # Standard mode's cache stays here too
# one page per request: answers are ~2k tokens (experiment 65's 13 windows: at most 3.2k); 6,000 keeps two variants'
# worst case in flight together under the $4 cap (run43's 9,000 would not)
MAX_OUT = int(os.environ.get("EXP69_MAX_OUT", "6000"))
run43.max_out = lambda n_pages: MAX_OUT


def windows() -> list[dict]:
    arts = {}
    for run, (folder, which) in C.RUNS.items():
        for a in run43.articles(which):
            arts[(run, a["stem"])] = (a, which)
    out, seen = [], set()
    pages = C.OUT / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    for c in json.load(open(C.OUT / "pages69.json", encoding="utf-8")):
        a, which = arts[(c["run"], c["stem"])]
        src = (C.E43 / "out" / "pages") if which in "bcd" else (ST.OUT / "pages")
        for p in {1, c["page"]}:
            f = f"{a['stem']}_p{p:03d}.jpg"
            if not (pages / f).exists():
                assert (src / f).exists(), src / f
                os.symlink(src / f, pages / f)
        key = (c["stem"], c["page"])
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(a, kind="window", first=c["page"], last=c["page"], n=1,
                        pages_total=a.get("pages_total") or a.get("n")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["v3.6", "v3.6-nofix", "v3.6-faded"])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--cap", type=float, default=4.0, help="USD for ALL of experiment 69 (from out/baseline_spend.json)")
    ap.add_argument("--mode", choices=["batch", "standard"], default="batch")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--poll", type=int, default=60)
    args = ap.parse_args()
    P.use(args.variant)
    ST.PAGES = C.OUT / "pages"
    arts = [a for a in windows() if not args.stems or a["stem"] in args.stems]
    if args.dry_run:
        e = run43.estimate(arts, args.tag, run43.calibration())
        print(json.dumps(dict(requests=e["requests"], pages=e["pages"], tin=e["input_tokens"],
                              tout=e["output_tokens_expected"], usd=e["usd"]), indent=1))
        return
    bf = C.OUT / "baseline_spend.json"
    if not bf.exists():
        C.jdump(bf, dict(spent_before_exp69=run43.C.spent()))
    base = json.load(open(bf))["spent_before_exp69"]
    cap = base + args.cap                # run43's cap is on the whole log's total
    print(f"exp 69 so far ${run43.C.spent() - base:.3f} of ${args.cap}", flush=True)
    print(f"{args.tag}: {len(arts)} windows, prompt {P.PROMPT_VERSION}, {args.mode}, cap ${args.cap}; "
          f"spent so far ${run43.C.spent():.3f}", flush=True)
    if args.mode == "standard":
        run43.run_standard(arts, args.tag, cap, 4)
    else:
        run43.run_batch(arts, args.tag, cap, False, args.poll, 4_500_000)
    print(f"spent ${run43.C.spent():.3f}; experiment 69 ${run43.C.spent() - base:.3f}")


if __name__ == "__main__":
    main()
