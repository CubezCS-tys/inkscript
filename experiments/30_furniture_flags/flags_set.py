"""Flagged share on experiment 28's 205 documents, before and after the block-level marks, by kind of document.

The 'before' marks are the build's own (each document's ALTO in experiment 28's out/set: trust.* and why.* on every
String, Azure's confidence as WC), so the ink signals (speck, ornament) need no scan here; 'after' applies
trust.regions + trust.in_region to those same reasons.

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/flags_set.py   -> out/flags_set.json
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

from inkscript.enrich import trust as T
from inkscript.enrich.document import ARABIC, load

HERE = Path(__file__).resolve().parent
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
A = "{http://www.loc.gov/standards/alto/ns-v4#}"
HAR = re.compile(r"[ً-ْ]")

RELS = (0.0, 0.25, 0.35, 0.5)
docs = {}
pages_out = []
for d in sorted((DATA / "azure").iterdir()):
    stem = d.name
    alto = next(iter(DATA.glob(f"set/w*/{stem}.alto.xml")), None)
    if alto is None:
        continue
    doc = load(d / f"{stem}.json")
    reg = T.regions(doc)
    byid = {w["id"]: w for w in doc["words"]}
    c = Counter()
    per_page = defaultdict(Counter)
    for s in etree.parse(str(alto)).iter(A + "String"):
        tr = (s.get("TAGREFS") or "").split()
        mark = next((t[6:] for t in tr if t.startswith("trust.")), None)
        if mark is None:
            continue
        w = byid.get(s.get("ID"))
        if w is None:
            continue
        why = [t[4:] for t in tr if t.startswith("why.")]
        after = mark
        alt = {}
        if mark == "flagged":
            ctx = T.context(doc, reg, w)
            if not T.in_region(why, dict(conf=w["conf"]), ctx):
                after = "covered"
            for rel in RELS:
                alt[f"after_{rel}"] = bool(T.in_region(why, dict(conf=w["conf"]), ctx, rel=rel))
                alt[f"after_{rel}_notail"] = bool(T.in_region(why, dict(conf=w["conf"]), ctx, rel=rel, tail=False))
        marked = bool(reg["blocks"].get(w["para"]))
        for m in reg["blocks"].get(w["para"], []):
            c[f"{m}_words"] += 1
            c[f"{m}_before"] += mark == "flagged"
            c[f"{m}_after"] += after == "flagged"
        for k, v in (("words", 1), ("before", mark == "flagged"), ("after", after == "flagged"), ("marked", marked),
                     ("covered", after == "covered"), *alt.items()):
            c[k] += v
            per_page[w["page"]][k] += v
    ar = [w for w in doc["words"] if ARABIC.search(w["text"])]
    vow = sum(bool(HAR.search(w["text"])) for w in ar) / max(1, len(ar))
    kind = ("handwritten pages" if reg["pages"] else
            "over 50% vowelled" if vow > 0.5 else "20-50% vowelled" if vow > 0.2 else
            "5-20% vowelled" if vow > 0.05 else "under 5% vowelled")
    docs[stem] = dict(c, vowelled=round(vow, 4), kind=kind, hw_pages=sorted(reg["pages"]),
                      marked_blocks=Counter(m for ms in reg["blocks"].values() for m in ms))
    for pn, pc in per_page.items():
        pages_out.append(dict(doc=stem, page=pn, hw=reg["pages"].get(pn), **pc))
    print(stem, kind, dict(c), flush=True)

by_mark = Counter()
for r in docs.values():
    for k, v in r.items():
        if isinstance(v, int) and k.split("_")[0] in ("vowelled", "handwritten", "decorative"):
            by_mark[k] += v
for m in ("vowelled", "handwritten", "decorative"):
    if by_mark[f"{m}_words"]:
        print(f"in {m} blocks: words {by_mark[m + '_words']} flagged {by_mark[m + '_before'] / by_mark[m + '_words']:.1%} -> "
              f"{by_mark[m + '_after'] / by_mark[m + '_words']:.1%}")
kinds = defaultdict(Counter)
for s, r in docs.items():
    for k in ("words", "before", "after", "marked", "covered", *(f"after_{x}" for x in RELS), *(f"after_{x}_notail" for x in RELS)):
        kinds[r["kind"]][k] += r[k]
        kinds["all"][k] += r[k]
    kinds[r["kind"]]["docs"] += 1
    kinds["all"]["docs"] += 1
for k, v in kinds.items():
    print(f"{k:20s} docs {v['docs']:3d} words {v['words']:7d} flagged {v['before'] / v['words']:6.1%} -> {v['after'] / v['words']:6.1%}"
          f"  in marked blocks {v['marked'] / v['words']:6.1%}  " + " ".join(f"{x}:{v[f'after_{x}'] / v['words']:.1%}/{v[f'after_{x}_notail'] / v['words']:.1%}" for x in RELS))
(HERE / "out" / "flags_set.json").write_text(json.dumps(dict(kinds=kinds, by_mark=by_mark, docs=docs, pages=pages_out), ensure_ascii=False),
                                             encoding="utf-8")
