"""Experiment 70: metadata and reference spot checks on the final masters of both routes (seed 7071): for 10 random
articles of each route, title / authors / affiliations / dates / doc type side by side with the catalogue; for 20
random references of each route, the printed entry beside the parsed fields. -> out/spot70.txt (read by hand)."""
import json, random, sqlite3
from pathlib import Path
from lxml import etree
H = Path(__file__).resolve().parent / "out"
MARC = sqlite3.connect("file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1", uri=True)
def tx(e): return " ".join("".join(e.itertext()).split()) if e is not None else ""
def ec(r):
    e = r.find("element-citation")
    if e is None: return "(none)"
    return e.get("publication-type") + " | " + " | ".join(f"{x.tag}={tx(x)[:50]}" for x in e.iter() if x is not e and not len(x) and tx(x))
out = []
for route, d in (("scan", H / "j0165" / "masters"), ("word", H / "w0165_final" / "masters")):
    fs = sorted(d.glob("*.jats.xml"))
    rnd = random.Random(7071)
    for f in rnd.sample(fs, 10):
        s = f.name[:16]
        r = etree.parse(str(f)).getroot(); am = r.find("front/article-meta")
        c = MARC.execute("select r.title, r.year_int, r.page_first, r.page_last from records r join pdf_ids p on p.rec=r.rec where p.stem=?", (s,)).fetchone()
        out.append(f"== {route} {s} type={r.get('article-type')}\n  title: {tx(am.find('title-group/article-title'))}\n  catalogue: {c}")
        for k in am.iter("contrib"):
            out.append(f"  contrib: {tx(k.find('.//string-name') if k.find('.//string-name') is not None else k.find('.//name'))} | id={tx(k.find('contrib-id'))} | aff={tx(k.find('aff'))[:120]} | role={tx(k.find('role'))}")
        out.append(f"  pages: {tx(am.find('fpage'))}-{tx(am.find('lpage'))} year {tx(am.find('pub-date/year'))} abstracts {len(am.findall('abstract'))}+{len(am.findall('trans-abstract'))} kwd {len(am.findall('kwd-group'))}")
    refs = [(f.name[:16], x) for f in fs for x in etree.parse(str(f)).getroot().iter("ref")]
    for s, x in random.Random(7072).sample(refs, 20):
        out.append(f"-- {route} ref {s}\n  PRINTED: {tx(x.find('mixed-citation'))[:260]}\n  FIELDS : {ec(x)}")
(H / "spot70.txt").write_text("\n".join(out), encoding="utf-8")
print(len(out))
