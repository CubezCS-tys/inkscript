"""Experiment 66, phase 1: every Gemini fix in the saved answers of the four current runs, with its features.

    collect66.py            out/fixes.jsonl (one fix a line) + out/collect_summary.json
No calls; reads the answers (43_rehearsal/out/<run>/raw), Azure's JSON (words + confidences) and the release DB.
"""
from __future__ import annotations

import gc
import json
import sys
from collections import Counter
from pathlib import Path

import common66 as C

C.e43_path()
import masters43 as M43  # noqa: E402
import replay43 as RP  # noqa: E402
import run43  # noqa: E402
import rules43 as RU  # noqa: E402
import wordlist43 as WL  # noqa: E402
import d30guard43 as G  # noqa: E402
from masters43 import ST  # noqa: E402


def in_master_index():
    """(stem, azure_reading, printed) of every reader fix in the current masters."""
    idx = Counter()
    with C.db() as c:
        for stem, a, p in c.execute(
                "select v.stem, t.azure_reading, t.printed from text_corrections t join versions v using(version_id)"
                " where v.is_current=1 and t.layer='azure-misread'"):
            idx[(stem, a or "", p or "")] += 1
    return idx


def main():
    cur = C.current_stems()
    W = WL.load()
    print("wordlist43:", len(W), flush=True)
    idx = in_master_index()
    out = C.OUT / "fixes.jsonl"
    tot = Counter()
    with open(out, "w", encoding="utf-8") as fo:
        for run, (folder, which) in C.RUNS.items():
            if which in ("b", "c", "d"):
                ST.PAGES = C.E43 / "out" / "pages"
            else:
                ST.PAGES = ST.OUT / "pages"
            arts = [a for a in run43.articles(which) if cur.get(a["stem"]) == run]
            src = C.E43 / "out" / folder / "raw"
            for a in arts:
                words = M43.azure_words(a)
                for x, y in ST.chunks(a):
                    f = src / f"{a['stem']}_c{x:03d}-{y:03d}.json"
                    if not f.exists():
                        tot[f"{run}: chunk missing"] += 1
                        continue
                    rec = ST.jl(f)
                    ans = rec.get("answer") or {}
                    fixes = [z for z in (ans.get("fixes") or []) if isinstance(z, dict)]
                    if not fixes:
                        continue
                    lines = RP.chunk_lines(a, x, y)
                    for k, fx in enumerate(fixes):
                        frm, to = str(fx.get("from") or ""), str(fx.get("to") or "")
                        lid = str(fx.get("line") or "")
                        base = RU.base_of(lid, lines)
                        text = lines[base]["text"] if base else ""
                        ws = G.span_words(text, frm, words(base)) if base else []
                        confs = [w.get("conf") for w in ws]
                        cf, ct = G.changed_tokens(frm, to)
                        page = lines[base]["page"] if base else None
                        box = None
                        if ws:
                            box = [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
                                   max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)]
                        r = dict(run=run, stem=a["stem"], chunk=f.stem, k=k, line=lid, base=base, page=page,
                                 frm=frm, to=to, why=fx.get("why"), text=text, found=bool(text) and frm in text,
                                 azure_words=[w["text"] for w in ws], confs=confs, box=box,
                                 cls=G.edit_class(frm, to), script=G.script_of(frm + to),
                                 from_tok=cf, to_tok=ct,
                                 from_known=[WL.known(t, W) for t in cf], to_known=[WL.known(t, W) for t in ct],
                                 from_wl=[WL.freq(t, W) for t in cf], to_wl=[WL.freq(t, W) for t in ct],
                                 excl=bool(RU.EXCL.search(frm) and RU.EXCL_DIGIT.search(to)),
                                 in_master=idx.get((a["stem"], frm, to), 0) > 0)
                        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
                        tot[f"{run}: fixes"] += 1
                        tot[f"{run}: found"] += r["found"]
                        tot[f"{run}: in_master"] += r["in_master"]
                ST._az.clear()
                gc.collect()
            print(run, {k: v for k, v in tot.items() if k.startswith(run)}, flush=True)
    C.jdump(C.OUT / "collect_summary.json", dict(tot))
    print(dict(tot))


if __name__ == "__main__":
    main()
