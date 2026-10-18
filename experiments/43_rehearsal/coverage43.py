"""Experiment 43: which JATS slots the masters fill (no model calls).

    coverage43.py build --run v2_55 --out out/v3_test/v2_now     today's rules + masters on a run's answers (rules/),
                                                                  DTD + XSD check, out/<...>/slots.json
    coverage43.py count out/v2_55/masters out/v3_test/v2_now      per slot: articles that have it / occurrences,
                                                                  one column per folder (markdown table)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43 as M43  # noqa: E402
from lxml import etree  # noqa: E402

XL = "{http://www.w3.org/1999/xlink}"
LANG = "@xml:lang"

# (slot, XPath from the article root); the order of jats_coverage.md
SLOTS = [
    ("front", "DOI  article-id[@pub-id-type='doi']", "front/article-meta/article-id[@pub-id-type='doi']"),
    ("front", "catalogue record id  article-id[@custom-type]", "front/article-meta/article-id[@custom-type='mandumah-record']"),
    ("front", "subjects  article-categories/subj-group", "front/article-meta/article-categories/subj-group"),
    ("front", "journal ISSN  journal-meta/issn", "front/journal-meta/issn"),
    ("front", "publisher  journal-meta/publisher", "front/journal-meta/publisher"),
    ("front", "article-title (printed lines)", "front/article-meta/title-group/article-title[@id]"),
    ("front", "subtitle", "front/article-meta/title-group/subtitle"),
    ("front", "trans-title-group, printed", "front/article-meta/title-group/trans-title-group[@specific-use='printed']"),
    ("front", "trans-subtitle, printed", "front/article-meta/title-group/trans-title-group[@specific-use='printed']/trans-subtitle"),
    ("front", "trans-title-group, catalogue", "front/article-meta/title-group/trans-title-group[not(@specific-use='printed')]"),
    ("front", "alt-title catalogue-translation", "front/article-meta/title-group/alt-title[@alt-title-type='catalogue-translation']"),
    ("front", "contrib (author)", "front/article-meta/contrib-group/contrib"),
    ("front", "contrib/name (surname, given-names)", "front/article-meta/contrib-group/contrib//name"),
    ("front", "contrib-id (authority)", "front/article-meta/contrib-group/contrib/contrib-id"),
    ("front", "contrib/role", "front/article-meta/contrib-group/contrib/role"),
    ("front", "contrib/email", "front/article-meta/contrib-group/contrib/email"),
    ("front", "aff", "front/article-meta/contrib-group/contrib/aff"),
    ("front", "aff/institution[@content-type=dept]", "front/article-meta//aff/institution[@content-type='dept']"),
    ("front", "aff/institution[@content-type=orgname]", "front/article-meta//aff/institution[@content-type='orgname']"),
    ("front", "aff/addr-line[@content-type=city]", "front/article-meta//aff/addr-line"),
    ("front", "aff/country", "front/article-meta//aff/country"),
    ("front", "aff/email", "front/article-meta//aff/email"),
    ("front", "pub-date", "front/article-meta/pub-date"),
    ("front", "pub-date with day (printed)", "front/article-meta/pub-date[day]"),
    ("front", "volume / issue", "front/article-meta/volume"),
    ("front", "fpage / lpage", "front/article-meta/fpage"),
    ("front", "history/date", "front/article-meta/history/date"),
    ("front", "permissions (copyright, licence)", "front/article-meta/permissions"),
    ("front", "self-uri", "front/article-meta/self-uri"),
    ("front", "abstract (printed)", "front/article-meta/abstract[@abstract-type='printed']"),
    ("front", "trans-abstract (printed)", "front/article-meta/trans-abstract[@abstract-type='printed']"),
    ("front", "abstract (catalogue)", "front/article-meta/*[self::abstract or self::trans-abstract][@specific-use='catalogue']"),
    ("front", "kwd-group printed", "front/article-meta/kwd-group[@kwd-group-type='author-printed']"),
    ("front", "kwd (printed)", "front/article-meta/kwd-group[@kwd-group-type='author-printed']/kwd"),
    ("front", "kwd-group catalogue", "front/article-meta/kwd-group[@specific-use='catalogue']"),
    ("front", "funding-group", "front/article-meta/funding-group"),
    ("front", "counts/page-count", "front/article-meta/counts/page-count"),
    ("front", "printed front-matter block (custom-meta)", "front/article-meta/custom-meta-group/custom-meta[meta-name='front-matter-block']"),
    ("body", "sec", "body//sec"),
    ("body", "p (body)", "body//p"),
    ("body", "p[@content-type=abstract] left in body", "body//p[@content-type='abstract']"),
    ("body", "p[@content-type=keywords] left in body", "body//p[@content-type='keywords']"),
    ("body", "list / list-item", "body//list-item"),
    ("body", "disp-quote", "//disp-quote"),
    ("body", "named-content[@content-type=quran]", "//named-content[@content-type='quran']"),
    ("body", "verse-group / verse-line", "body//verse-line"),
    ("body", "table-wrap", "//table-wrap"),
    ("body", "fig", "//fig"),
    ("body", "fig/alt-text", "//fig/alt-text"),
    ("body", "fig with alt-text in two languages", "//fig[count(alt-text) > 1]"),
    ("body", "fig/p text-in-figure", "//fig/p[@content-type='text-in-figure']"),
    ("body", "disp-formula", "//disp-formula"),
    ("body", "inline-formula", "//inline-formula"),
    ("body", "boxed-text", "//boxed-text"),
    ("body", "xref[@ref-type=fn] (note calls)", "//xref[@ref-type='fn']"),
    ("body", "named-content sic (misprint flags)", "//named-content[@content-type='sic']"),
    ("body", "def-list / glossary", "//def-list | //glossary"),
    ("back", "fn-group footnotes / fn", "back/fn-group[not(@content-type='endnotes')]/fn"),
    ("back", "fn-group[@content-type=endnotes] / fn", "back/fn-group[@content-type='endnotes']/fn"),
    ("back", "fn-group endnotes title", "back/fn-group[@content-type='endnotes']/title"),
    ("back", "ref-list / ref (mixed-citation)", "back/ref-list/ref"),
    ("back", "element-citation (parsed reference)", "//element-citation"),
    ("back", "ack", "back/ack"),
    ("back", "app-group / app", "back/app-group/app"),
    ("back", "notes reader-fixes / p", "back/notes[@notes-type='reader-fixes']/p"),
    ("back", "notes suspected-misprints / p", "back/notes[@notes-type='suspected-misprints']/p"),
    ("back", "bio / sig-block", "//bio | //sig-block"),
]


def count(folder: Path) -> dict:
    res = {name: [0, 0] for _, name, _ in SLOTS}
    files = sorted(folder.glob("*.jats.xml"))
    for f in files:
        r = etree.parse(str(f), etree.XMLParser(load_dtd=False, no_network=True)).getroot()
        for _, name, xp in SLOTS:
            n = len(r.xpath(xp))
            if n:
                res[name][0] += 1
                res[name][1] += n
    return dict(articles=len(files), slots=res)


def cmd_count(folders):
    cs = [count(Path(f)) for f in folders]
    head = "| part | slot | " + " | ".join(f"{Path(f).relative_to(HERE) if Path(f).resolve().is_relative_to(HERE) else f} "
                                           f"({c['articles']}): articles / count" for f, c in zip(folders, cs)) + " |"
    print(head)
    print("|---|---|" + "---|" * len(cs))
    for part, name, _ in SLOTS:
        print(f"| {part} | {name} | " + " | ".join(f"{c['slots'][name][0]} / {c['slots'][name][1]}" for c in cs) + " |")


def cmd_build(run, out: Path, stems=None):
    from inkscript.enrich.schemas import validate_jats, validate_alto
    tot, per, bad = Counter(), {}, []
    raw = M43.OUT / run / "rules"
    for a in M43.ST.sample():
        if stems and a["stem"] not in stems:
            continue
        if not list(raw.glob(f"{a['stem']}_c*.json")):
            continue
        r = M43.build43(a, raw, out, True, run=run)
        j, al = validate_jats(out / f"{a['stem']}.jats.xml"), validate_alto(out / f"{a['stem']}.alto.xml")
        if j or al:
            bad.append(dict(stem=a["stem"], jats=j[:3], alto=al[:3]))
        d = {k: v for k, v in r.items() if k.startswith("jats_") or "alt_text" in k or "trans_title" in k}
        per[a["stem"]] = d
        tot.update(d)
    (out / "slots.json").write_text(json.dumps(dict(total=tot, per=per, invalid=bad, articles=len(per)),
                                               ensure_ascii=False, indent=1))
    print(f"{len(per)} articles, {len(per) - len(bad)} JATS DTD + ALTO XSD valid; invalid: {bad}")
    print(dict(tot))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "count"])
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--stems", nargs="*")
    a = ap.parse_args()
    if a.cmd == "build":
        cmd_build(a.run, Path(a.out).resolve(), a.stems)
    else:
        cmd_count([Path(d).resolve() for d in a.dirs])


if __name__ == "__main__":
    main()
