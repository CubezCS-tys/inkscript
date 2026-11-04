"""Experiment 60: the metadata fields the proof pack scored (title, authors, year, pages, affiliation), read from
two sets of masters and compared field by field (no calls).

    meta60.py --a out/t1/argon_build/masters --b out/t1/build/masters --stems-from proof   -> out/t1/meta.json
"""
from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from common60 import E43, OUT, jdump, jl


def t(e):
    return re.sub(r"\s+", " ", " ".join(e.itertext())).strip() if e is not None else None


def front(f: Path) -> dict:
    if not f.exists():
        return {}
    r = ET.parse(f).getroot()
    am = r.find(".//article-meta")
    tg = am.find("title-group")
    names = []
    for c in am.iter("contrib"):
        n = c.find(".//name")
        sn = c.find(".//string-name")
        nm = t(n) if n is not None else t(sn)
        names.append(f"{c.get('contrib-type')}: {nm}")
    years = [f"{d.get('calendar') or ''}{':' if d.get('calendar') else ''}{t(d.find('year'))}"
             for d in am.findall("pub-date")]
    return dict(title=t(tg.find("article-title")) if tg is not None else None,
                subtitle=t(tg.find("subtitle")) if tg is not None else None,
                authors=names, year=years,
                pages=f"{t(am.find('fpage'))}-{t(am.find('lpage'))}",
                affiliation=[t(a) for a in am.iter("aff")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default=str(OUT / "t1" / "argon_build" / "masters"))
    ap.add_argument("--b", default=str(OUT / "t1" / "build" / "masters"))
    ap.add_argument("--out", default=str(OUT / "t1" / "meta.json"))
    ap.add_argument("--stems", nargs="*")
    a = ap.parse_args()
    stems = a.stems or [x["stem"] for x in jl(E43 / "out" / "proof" / "meta_draw.json")]
    sc = {x["stem"]: x for x in jl(E43 / "out" / "proof" / "meta_score.json")["items"]}
    rows = []
    for s in stems:
        A, B = front(Path(a.a) / f"{s}.jats.xml"), front(Path(a.b) / f"{s}.jats.xml")
        diff = {k: dict(argon=A.get(k), claude=B.get(k)) for k in A if A.get(k) != B.get(k)}
        rows.append(dict(stem=s, same=not diff, diff=diff, argon=A, claude=B,
                         proof=sc.get(s, {}).get("verdicts"), proof_notes=sc.get(s, {}).get("notes")))
    jdump(Path(a.out), rows)
    print(f"{len(rows)} articles; metadata the same: {sum(r['same'] for r in rows)}; fields differing: "
          f"{sorted({k for r in rows for k in r['diff']})}")


if __name__ == "__main__":
    main()
