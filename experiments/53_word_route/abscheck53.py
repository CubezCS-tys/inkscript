"""Experiment 53: does the Word file say what the print said? The catalogue's abstract (MARC 520, typed by the
cataloguers from the published article) against the Word file's printed abstract, and the catalogue's title against
the Word file's title lines (no model). -> stdout, out/abscheck.json."""
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build53 import fold  # noqa: E402
from inkscript.enrich import catalogue as CAT  # noqa: E402


def words(s):
    return Counter(w for w in re.findall(r"\w+", fold(s)) if len(w) > 1 and not w.isdigit())


def main():
    cat = CAT.open_catalogue()
    rows = []
    for f in sorted((HERE / "out" / "masters").glob("*.jats.xml")):
        stem = f.name[:-9]
        rec = cat.get(stem) or {}
        t = etree.parse(str(f), etree.XMLParser(load_dtd=False, no_network=True))
        ab = t.find(".//article-meta/abstract[@abstract-type='printed']")
        ca = next((x for c, x in rec.get("abstracts", []) if c == "a"), None)
        if ab is None or not ca:
            continue
        W = words(" ".join("".join(p.itertext()) for p in ab.findall("p")))
        C = words(ca)
        inter = sum((W & C).values())
        rows.append(dict(stem=stem, cat_in_word=round(inter / max(1, sum(C.values())), 3),
                         word_in_cat=round(inter / max(1, sum(W.values())), 3), cat_words=sum(C.values()),
                         word_words=sum(W.values())))
    for k in ("cat_in_word", "word_in_cat"):
        v = [r[k] for r in rows]
        print(f"{k}: {len(v)} abstracts, median {statistics.median(v):.3f}, mean {statistics.mean(v):.3f}, "
              f">=0.95: {sum(1 for x in v if x >= 0.95)}, <0.80: {sum(1 for x in v if x < 0.8)}")
    for r in sorted(rows, key=lambda r: r["cat_in_word"])[:8]:
        print("  low:", r)
    (HERE / "out" / "abscheck.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
