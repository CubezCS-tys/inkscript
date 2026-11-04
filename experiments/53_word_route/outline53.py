"""Experiment 53: a short text outline of a master, to read beside the legacy PDF (no model)."""
import sys
from pathlib import Path
from lxml import etree

HERE = Path(__file__).resolve().parent


def tx(e):
    return " ".join("".join(e.itertext()).split()) if e is not None else ""


def main(stem):
    t = etree.parse(str(HERE / "out" / "masters" / f"{stem}.jats.xml"), etree.XMLParser(load_dtd=False, no_network=True))
    am = t.find(".//article-meta")
    print("TITLE:", tx(am.find("title-group/article-title")))
    for a in am.findall("title-group/alt-title"):
        print("  alt", a.get("alt-title-type"), ":", tx(a)[:120])
    for g in am.findall("title-group/trans-title-group"):
        print("  trans", g.get("specific-use"), ":", tx(g)[:120])
    for c in am.findall("contrib-group/contrib"):
        print("  contrib", c.findtext("contrib-id"), "|", tx(c.find(".//string-name")), "|", tx(c.find("aff"))[:90])
    for a in am.findall("abstract") + am.findall("trans-abstract"):
        print("  ", a.tag, a.get("abstract-type"), len(a.findall("p")), "p", tx(a)[:80])
    for k in am.findall("kwd-group"):
        print("  kwd", k.get("kwd-group-type"), len(k.findall("kwd")))
    for cm in am.findall(".//custom-meta"):
        if cm.findtext("meta-name") == "front-matter-block":
            print("  front-block:", cm.findtext("meta-value")[:100])

    def walk(e, d):
        for c in e:
            if c.tag in ("sec", "app", "ack"):
                print("  " * d + f"[{c.tag} L{c.get('disp-level', '')}] {(c.findtext('label') or '')} {tx(c.find('title'))[:90]}"
                      f"  (p {len(c.findall('p'))}, list {len(c.findall('list'))}, tables {len(c.findall('table-wrap'))}, figs {len(c.findall('fig'))})")
                walk(c, d + 1)
            elif c.tag == "app-group":
                walk(c, d)
    print("BODY: top-level p", len(t.findall("body/p")))
    walk(t.find("body"), 1)
    for tw in t.findall(".//table-wrap"):
        rows = tw.findall(".//tr")
        print("  table", tw.findtext("label"), tx(tw.find("caption"))[:70], f"{len(rows)} rows x {max((len(r) for r in rows), default=0)}")
    b = t.find("back")
    if b is not None:
        walk(b, 1)
        refs = b.findall(".//ref")
        print("REFS", len(refs))
        for r in refs[:3] + refs[-2:]:
            ec = r.find("element-citation")
            print("   -", tx(r.find("mixed-citation"))[:110])
            if ec is not None:
                print("      ", ec.get("publication-type"), {x.tag: tx(x)[:40] for x in ec if x.tag != "person-group"},
                      [tx(n) for n in ec.findall("person-group/name")][:3])
        for fn in b.findall(".//fn"):
            print("  fn", fn.get("id"), fn.findtext("label"), tx(fn)[:80])


if __name__ == "__main__":
    main(sys.argv[1])
