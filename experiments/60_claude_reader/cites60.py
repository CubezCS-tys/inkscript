"""Experiment 60, test 1: the proof pack's sampled citations (out/plan_t1_cites.json "kept"), Claude's parse
against Argon's (no calls). Each sampled citation is found again in a master by its printed text (the proof's
cites_draw.py extraction, run on that master); fields that equal Argon's take the proof's verdict, the others
are written out to be judged by hand (out/t1/cites_review.json -> verdicts in out/t1/cite_verdicts.json).

    cites60.py [--masters out/t1/build/masters] [--tag claude]
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from common60 import E43, OUT, jdump, jl

PROOF = E43 / "out" / "proof"


def txt(e):
    return re.sub(r"\s+", " ", "".join(e.itertext())).strip()


def items_of(f: Path) -> list[dict]:
    """cites_draw.py's extraction, unchanged."""
    t = ET.parse(f)
    parent = {c: p for p in t.iter() for c in p}
    items = []
    for ec in t.iter("element-citation"):
        p = parent[ec]
        if p.tag == "ref":
            mc = p.find("mixed-citation")
            printed = txt(mc) if mc is not None else ""
            where = "ref " + p.get("id", "")
        else:
            fn = parent[p]
            ps = [x for x in fn.findall("p") if x.get("content-type") != "parsed-citations"]
            printed = " ".join(txt(x) for x in ps)
            where = "fn " + fn.get("id", "")
            n = len(p.findall("element-citation"))
            if n > 1:
                where += f" ({list(p).index(ec) + 1} of {n})"
        fields = []
        for c in ec:
            if c.tag == "person-group":
                fields.append((c.get("person-group-type", "") + "s", " ; ".join(txt(n) for n in c)))
            else:
                fields.append((c.tag + (("/" + c.get("pub-id-type")) if c.get("pub-id-type") else ""), txt(c)))
        items.append(dict(where=where, type=ec.get("publication-type"), printed=printed, fields=fields))
    return items


def best(items, printed, where):
    """The item whose printed text matches; for one footnote holding several works, the same position."""
    pos = re.search(r"\((\d+) of", where)
    cand = []
    for it in items:
        r = difflib.SequenceMatcher(None, it["printed"][:400], printed[:400]).ratio()
        p2 = re.search(r"\((\d+) of", it["where"])
        same_pos = (p2.group(1) if p2 else None) == (pos.group(1) if pos else None)
        cand.append((r + (0.05 if same_pos else 0), r, it))
    if not cand:
        return None, 0
    cand.sort(key=lambda c: -c[0])
    return cand[0][2], cand[0][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--masters", default=str(OUT / "t1" / "build" / "masters"))
    ap.add_argument("--tag", default="claude")
    a = ap.parse_args()
    M = Path(a.masters)
    kept = set(jl(OUT / "plan_t1_cites.json")["kept"])
    draw = {x["i"]: x for x in jl(PROOF / "cites_draw.json")["sample"]}
    score = {x["i"]: x for x in jl(PROOF / "cites_score.json")["items"]}
    rows, cache = [], {}
    for i in sorted(kept):
        d = draw[i]
        f = M / f"{d['stem']}.jats.xml"
        if d["stem"] not in cache:
            cache[d["stem"]] = items_of(f) if f.exists() else []
        it, r = best(cache[d["stem"]], d["printed"], d["where"])
        argon = dict((k, v) for k, v in d["fields"])
        mine = dict((k, v) for k, v in it["fields"]) if it and r >= 0.6 else {}
        same = mine == argon
        rows.append(dict(i=i, stem=d["stem"], where=d["where"], match=round(r, 3), printed=d["printed"],
                         argon=d["fields"], argon_type=d["type"], mine=it["fields"] if mine else None,
                         mine_type=it["type"] if mine else None, mine_where=it["where"] if mine else None,
                         same=same, argon_verdicts=score[i]["verdicts"], argon_all_right=score[i]["all_right"],
                         argon_notes=score[i].get("notes")))
    jdump(OUT / "t1" / f"cites_{a.tag}.json", rows)
    print(f"{len(rows)} citations: same as Argon {sum(r['same'] for r in rows)}, "
          f"not found {sum(r['mine'] is None for r in rows)}")


if __name__ == "__main__":
    main()
