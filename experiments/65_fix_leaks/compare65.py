"""Experiment 65: prove that no printed text changed. For every master of a run, old folder vs new folder:

  * ALTO: every String's CONTENT, page by page, in order (the words as printed) - must be identical;
  * JATS: the text of every element the ALTO points at (TextBlock @id / xlink:href targets: titles, paragraphs,
    cells, references, notes, front-matter blocks ...) - must be identical;
  * word counts (ALTO Strings; JATS body + back text).

    compare65.py OLD_MASTERS NEW_MASTERS [--out report.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

A = "{http://www.loc.gov/standards/alto/ns-v4#}"


def tx(el) -> str:
    return " ".join("".join(el.itertext()).split())


def alto_words(p: Path) -> list[str]:
    root = etree.parse(str(p), etree.XMLParser(huge_tree=True)).getroot()
    out = []
    for pg in root.iter(A + "Page"):
        out.append(f"#page {pg.get('ID')}")
        out += [s.get("CONTENT") or "" for s in pg.iter(A + "String")]
    return out


def alto_targets(p: Path) -> set[str]:
    root = etree.parse(str(p), etree.XMLParser(huge_tree=True)).getroot()
    ids = set()
    for tb in root.iter(A + "TextBlock"):
        ids.add(tb.get("ID"))
        for k, v in tb.attrib.items():
            if k.endswith("href") and "#" in v:
                ids.add(v.rsplit("#", 1)[1])
    return ids


def jats_blocks(p: Path, want: set[str]) -> dict:
    root = etree.parse(str(p)).getroot()
    return {e.get("id"): (e.tag, tx(e)) for e in root.iter() if isinstance(e.tag, str) and e.get("id") in want}


def subsequence(a: str, b: str) -> bool:
    """a's words in order inside b's (a contrib the ALTO points at: experiment 65 adds fields beside its name)."""
    it = iter(b.split())
    return all(w in it for w in a.split())


def body_words(p: Path) -> int:
    root = etree.parse(str(p)).getroot()
    n = 0
    for tag in ("body", "back"):          # the printed text: parsed citations (element-citation) are fields
        el = root.find(tag)
        if el is not None:
            for ec in list(el.iter("element-citation")):
                ec.getparent().remove(ec)
            n += len(tx(el).split())
    return n


def compare(old: Path, new: Path) -> dict:
    rep = dict(articles=0, alto_same=0, blocks_same=0, missing=[], diffs=[], words_old=0, words_new=0,
               body_words_old=0, body_words_new=0)
    for oj in sorted(old.glob("*.jats.xml")):
        stem = oj.name[:-len(".jats.xml")]
        nj = new / oj.name
        if not nj.exists():
            rep["missing"].append(stem)
            continue
        rep["articles"] += 1
        oa, na = old / f"{stem}.alto.xml", new / f"{stem}.alto.xml"
        wo, wn = alto_words(oa), alto_words(na)
        rep["words_old"] += sum(not w.startswith("#page") for w in wo)
        rep["words_new"] += sum(not w.startswith("#page") for w in wn)
        d = dict(stem=stem)
        if wo == wn:
            rep["alto_same"] += 1
        else:
            c = Counter(wo)
            c.subtract(Counter(wn))
            d["alto"] = {k: v for k, v in c.items() if v}
        want = alto_targets(oa) | alto_targets(na)
        bo, bn = jats_blocks(oj, want), jats_blocks(nj, want)
        bd, added = {}, 0
        for k in set(bo) | set(bn):
            if bo.get(k) == bn.get(k):
                continue
            o, n = bo.get(k), bn.get(k)
            if o and n and o[0] == n[0] == "contrib" and subsequence(o[1], n[1]):
                added += 1                                 # the name as printed, with new fields beside it
                continue
            bd[k] = (o and o[1], n and n[1])
        rep["contribs_with_fields_added"] = rep.get("contribs_with_fields_added", 0) + added
        if not bd:
            rep["blocks_same"] += 1
        else:
            d["blocks"] = {k: [str(a)[:200], str(b)[:200]] for k, (a, b) in sorted(bd.items())[:20]}
            d["n_blocks"] = len(bd)
        rep["body_words_old"] += body_words(oj)
        rep["body_words_new"] += body_words(nj)
        if len(d) > 1:
            rep["diffs"].append(d)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("--out")
    a = ap.parse_args()
    rep = compare(Path(a.old), Path(a.new))
    s = {k: v for k, v in rep.items() if k != "diffs"}
    s["articles_differing"] = [d["stem"] for d in rep["diffs"]]
    print(json.dumps(s, ensure_ascii=False))
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0)


if __name__ == "__main__":
    main()
