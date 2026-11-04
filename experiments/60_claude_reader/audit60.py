"""Experiment 60: what each reader's raw answer (before rules43) does with Azure's lines, Claude against Argon on
exactly the same chunks (no calls).

  left out   an Azure line of the chunk's pages in no block, cell, hemistich, split or noise list
  twice      a line id used in two places (two blocks, or a block and noise)
  unknown    a line id that is not one of the chunk's Azure lines (an invented id; split parts "3:12a" count as 3:12)
  text added "missed" entries (printed text no Azure line covers: the only way to add words) and "fixes"
             (a change to Azure's text: "from" must be an exact substring of the line - checked here)

    audit60.py --run t1 --set c --argon-raw ../43_rehearsal/out/v33_300b_fix3/raw   -> out/<run>/audit.json
"""
from __future__ import annotations

import argparse
import re
import glob
from collections import Counter
from pathlib import Path

import common60 as K
from common60 import OUT, jdump, jl


def ids_in(b):
    out = list(b.get("lines") or [])
    for h in b.get("hemistichs") or []:
        out += list(h or [])
    for r in b.get("rows") or []:
        for c in r or []:
            if isinstance(c, dict):
                out += list(c.get("lines") or [])
    for it in b.get("items") or []:
        if isinstance(it, dict):
            out += list(it.get("lines") or [])
    return [str(i) for i in out]


def audit(a, ans, ST):
    lines = {}
    for p in range(a_first(ans, a), a_last(ans, a) + 1):
        for L in ST.page_lines(a, p)[0]:
            lines[L["id"]] = L["text"]
    used = Counter()
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if isinstance(b, dict):
                used.update(ids_in(b))
    for s in ans.get("splits") or []:
        if isinstance(s, dict):
            used[str(s.get("line"))] += 0          # a split line is in blocks through its parts
    noise = [str(i) for i in ans.get("noise") or []]
    allu = used + Counter(noise)
    parts = Counter()                       # split parts "3:12a", "3:12b": the line 3:12, used once
    for i in list(allu):
        m = re.match(r"^(\d+:\d+)[a-z]$", i)
        if m and m.group(1) in lines:
            parts[m.group(1)] = max(parts[m.group(1)], 1)
            del allu[i]
    allu = allu + parts
    left = [i for i in lines if allu[i] == 0]
    twice = [i for i, n in allu.items() if n > 1 and i in lines]
    unknown = [i for i in allu if i not in lines]
    fixes = [f for f in ans.get("fixes") or [] if isinstance(f, dict)]
    bad_fix = [f for f in fixes if str(f.get("from") or "") not in lines.get(str(f.get("line")), "")]
    missed = [m for m in ans.get("missed") or [] if isinstance(m, dict)]
    return dict(lines=len(lines), left_out=len(left), twice=len(twice), unknown=len(unknown), noise=len(noise),
                fixes=len(fixes), fixes_not_substring=len(bad_fix), missed=len(missed),
                missed_chars=sum(len(str(m.get("text") or "")) for m in missed),
                sic=len(ans.get("sic") or []), left_ids=left[:20], unknown_ids=unknown[:20])


def a_first(ans, a):
    return min(int(p["page"]) for p in ans.get("pages") or [] if isinstance(p, dict) and "page" in p)


def a_last(ans, a):
    return max(int(p["page"]) for p in ans.get("pages") or [] if isinstance(p, dict) and "page" in p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--set", default="c")
    ap.add_argument("--argon-raw", required=True)
    a = ap.parse_args()
    P = K.pipeline()
    ST = P.ST
    arts = K.articles(a.set)
    rows = []
    tot = {"claude": Counter(), "argon": Counter()}
    for f in sorted(glob.glob(str(OUT / a.run / "raw" / "*.json"))):
        if f.endswith(".failed.json"):
            continue
        name = Path(f).name
        g = Path(a.argon_raw) / name
        if not g.exists():
            continue
        stem = name.rsplit("_c", 1)[0]
        art = arts[stem]
        r = dict(chunk=name[:-5])
        for who, src in (("claude", f), ("argon", g)):
            rec = jl(src)
            x = audit(art, rec["answer"], ST)
            r[who] = x
            for k, v in x.items():
                if isinstance(v, int):
                    tot[who][k] += v
            tot[who]["chunks"] += 1
            tot[who]["pages"] += rec["pages"]
        ST._az.pop(stem, None)
        rows.append(r)
    jdump(OUT / a.run / "audit.json", dict(totals={k: dict(v) for k, v in tot.items()}, chunks=rows))
    for who in tot:
        print(who, dict(tot[who]))


if __name__ == "__main__":
    main()
