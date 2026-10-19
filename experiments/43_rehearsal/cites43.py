"""Experiment 43: audit of prompt v3.2's parsed references / note citations (no model calls).

    cites43.py dump  --run v32_test            -> out/<run>/cites_raw.json + cites_raw.txt
        builds the run's masters with today's code (pictures43.build into out/<run>/) while recording, for every work
        the answer returned ("parsed" on a reference, "cites" on a note): the holder (ref / fn and its label), the
        printed entry the code checks against, the model's W, and per field kept / dropped (not a substring).
        Also lists every ref / fn of the JATS with whether it got element-citations (for "cites missing" checks).
    cites43.py score --run v32_test            -> out/<run>/cites_score.json
        reads the hand judgments out/<run>/cites_judged.json ({work key: {field: right|wrong|missing|invented|na}})
        and counts them per field.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out"
FIELDS = ["authors", "year", "title", "source", "volume", "issue", "pages", "publisher", "place", "doi", "url"]


def dump(run: str, stems):
    import refs43
    import pictures43
    from lxml import etree
    rec, cur = [], {}
    orig_cit, orig_add = refs43.citation, refs43.add_parsed

    def citation(w, printed, st, lang):
        before = Counter(st)
        e = orig_cit(w, printed, st, lang)
        dropped = {k.replace("refs_dropped_not_printed_", ""): v for k, v in (Counter(st) - before).items()
                   if k.startswith("refs_dropped_not_printed_")}
        rec.append(dict(cur, printed=printed, w=w, dropped=dropped, written=e is not None,
                        xml=etree.tostring(e, encoding="unicode") if e is not None else None))
        return e

    def add_parsed(Mo, A, raw_dir=None, answers=None):
        cur.clear()
        cur["stem"] = Mo.a["stem"]
        # which holder each block lands in: wrap parsed_blocks to note the line id
        orig_pb = refs43.parsed_blocks

        def pb(ans):
            for key, lid, works in orig_pb(ans):
                tgt = {t.get("id"): t for t in A.iter("target") if t.get("id")}
                t = tgt.get(Mo.tl_of.get(lid))
                h = next((e for e in t.iterancestors() if e.tag in ("ref", "fn")), None) if t is not None else None
                cur.update(kind=key, line=lid, holder=h.tag if h is not None else None,
                           holder_id=h.get("id") if h is not None else None,
                           label=(h.findtext("label") or "") if h is not None else "")
                if h is None:
                    rec.append(dict(cur, printed=None, w=works, dropped={}, written=False, xml=None,
                                    note="block not in a ref / fn"))
                yield key, lid, works
        refs43.parsed_blocks = pb
        try:
            return orig_add(Mo, A, raw_dir, answers)
        finally:
            refs43.parsed_blocks = orig_pb

    refs43.citation = citation
    refs43.add_parsed = add_parsed
    pictures43.build(run, "raw", OUT / run, stems)
    # every ref / fn in the masters, with or without parts
    holders = []
    for j in sorted((OUT / run / "masters").glob("*.jats.xml")):
        r = etree.parse(str(j), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
        for h in r.iter("ref", "fn"):
            txt = " ".join(" ".join("".join(p.itertext()) for p in h if p.tag in ("p", "mixed-citation")
                                    and p.get("content-type") != "parsed-citations").split())
            holders.append(dict(stem=j.name.split(".")[0], tag=h.tag, id=h.get("id"), label=h.findtext("label") or "",
                                text=txt, n_parts=len(h.findall(".//element-citation"))))
    (OUT / run / "cites_raw.json").write_text(json.dumps(dict(works=rec, holders=holders), ensure_ascii=False,
                                                         indent=1), encoding="utf-8")
    lines = []
    for i, r in enumerate(rec):
        lines.append(f"[{i}] {r.get('stem')} {r.get('kind')} {r.get('holder')} {r.get('holder_id')} "
                     f"label={r.get('label')!r} dropped={r.get('dropped')}")
        lines.append(f"   PRINTED: {r.get('printed')}")
        lines.append(f"   W: {json.dumps(r.get('w'), ensure_ascii=False)}")
    (OUT / run / "cites_raw.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(rec)} works recorded; {len(holders)} refs / notes in the masters")


def score(run: str):
    J = json.loads((OUT / run / "cites_judged.json").read_text(encoding="utf-8"))
    per = defaultdict(Counter)
    for k, v in J["works"].items():
        for f, verdict in v.get("fields", {}).items():
            per[f][verdict] += 1
    tot = Counter()
    for f in per:
        tot.update(per[f])
    res = dict(per_field={f: dict(per[f]) for f in FIELDS if f in per}, total=dict(tot), n_works=len(J["works"]))
    (OUT / run / "cites_score.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["dump", "score"])
    ap.add_argument("--run", default="v32_test")
    ap.add_argument("--stems", nargs="*")
    a = ap.parse_args()
    dump(a.run, a.stems) if a.cmd == "dump" else score(a.run)
