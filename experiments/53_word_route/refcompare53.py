"""Experiment 53: references per article, Word route vs the scan route's v33 masters of education journals.

Scan side: experiment 43's 600 v3.3 masters (v33_300_final, v33_300b_fix3; read only), the research articles
(catalogue type بحوث ومقالات) whose catalogue databases include EduSearch, years >= 2000. Per article: ref elements,
works parsed in footnotes (fn element-citations), refs with element-citation. Word side: out/masters.
-> stdout, out/refcompare.json.
"""
import glob
import json
import statistics
import sys
from pathlib import Path

from lxml import etree

from inkscript.enrich import catalogue as CAT

HERE = Path(__file__).resolve().parent
X = HERE.parents[0] / "43_rehearsal" / "out"


def counts(f):
    t = etree.parse(f, etree.XMLParser(load_dtd=False, no_network=True))
    refs = t.findall(".//ref")
    return dict(refs=len(refs), refs_ec=sum(1 for r in refs if r.find("element-citation") is not None),
                fn_works=len(t.findall(".//fn//element-citation")), heads=len(t.findall(".//body//sec/title")),
                fns=len(t.findall(".//fn")), tables=len(t.findall(".//table-wrap")))


def summ(rows, k):
    v = [r[k] for r in rows]
    return f"mean {statistics.mean(v):.1f} median {statistics.median(v)}"


def main():
    cat = CAT.open_catalogue()
    scan = []
    for run in ("v33_300_final", "v33_300b_fix3"):
        for f in sorted(glob.glob(str(X / run / "masters" / "*.jats.xml"))):
            stem = Path(f).name[:-9]
            r = cat.get(stem) or {}
            y = int((r.get("year") or "0")[:4] or 0) if (r.get("year") or "")[:4].isdigit() else 0
            if "EduSearch" in ",".join(r.get("db", [])) and r.get("type") == "بحوث ومقالات" and y >= 2000:
                scan.append(dict(stem=stem, run=run, **counts(f)))
    word = []
    for f in sorted(glob.glob(str(HERE / "out" / "masters" / "*.jats.xml"))):
        word.append(dict(stem=Path(f).name[:-9], **counts(f)))
    for name, rows in (("scan v33 EduSearch research 2000+", scan), ("Word route 0130 2009-2016", word)):
        with_refs = [r for r in rows if r["refs"]]
        print(f"{name}: {len(rows)} articles; with a ref list {len(with_refs)}; refs/article {summ(rows, 'refs')}; "
              f"of those with a list {summ(with_refs, 'refs') if with_refs else '-'}; refs with fields "
              f"{sum(r['refs_ec'] for r in rows)}/{sum(r['refs'] for r in rows)}; works in notes "
              f"{sum(r['fn_works'] for r in rows)}; headings {summ(rows, 'heads')}; notes {summ(rows, 'fns')}; "
              f"tables {summ(rows, 'tables')}")
    (HERE / "out" / "refcompare.json").write_text(json.dumps(dict(scan=scan, word=word), indent=1))


if __name__ == "__main__":
    sys.exit(main())
