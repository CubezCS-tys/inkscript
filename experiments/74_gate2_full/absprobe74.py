"""Experiment 74: front-matter probe of a Word-route code run (out/J/wJ_code/masters): per article the number of
abstract / trans-abstract elements and their paragraphs, contrib names ending in a note marker, affiliations; prints
the suspicious ones. No calls.   python3 absprobe74.py J"""
import re, sys
from collections import Counter
from pathlib import Path
from lxml import etree
J = sys.argv[1]
M = Path(__file__).resolve().parent / "out" / J / f"w{J}_code" / "masters"
tx = lambda e: " ".join("".join(e.itertext()).split()) if e is not None else ""
c = Counter()
for f in sorted(M.glob("*.jats.xml")):
    r = etree.parse(str(f)).getroot(); am = r.find("front/article-meta")
    ab = am.findall("abstract") + am.findall("trans-abstract")
    nab = len(ab); words = sum(len(tx(a).split()) for a in ab)
    names = [tx(k.find(".//string-name") if k.find(".//string-name") is not None else k.find(".//name")) for k in am.iter("contrib")]
    mark = [n for n in names if re.search(r"[0-9٠-٩*]\s*$", n)]
    affs = am.findall(".//aff")
    body = r.find("body"); bw = len(tx(body).split()) if body is not None else 0
    c["articles"] += 1; c["abstract_elems>2"] += nab > 2; c["abstract_words>600"] += words > 600
    c["name_marker"] += bool(mark); c["no_aff"] += not affs
    if nab > 2 or words > 600 or mark:
        print(f.name[:16], "abstracts", nab, "words", words, "body words", bw, "markers", mark[:2], "affs", len(affs))
print(dict(c))
