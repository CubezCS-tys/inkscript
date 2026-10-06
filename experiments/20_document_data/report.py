"""out/report.html — the Quran check on the ink, and one document's XML.

    python report.py [--xml STEM] [--page N]
"""
from __future__ import annotations
import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from docs import list_docs, load_doc  # noqa: E402
from crops import Pages, crop, data_uri, union  # noqa: E402
from quran import norm  # noqa: E402

E = html.escape
TEI = "{http://www.tei-c.org/ns/1.0}"
XID = "{http://www.w3.org/XML/1998/namespace}id"
ET.register_namespace("", "http://www.tei-c.org/ns/1.0")

VERDICT_ORDER = ["reading error? (dots only)", "reading error? (letters)", "different word",
                 "word not in verse", "word not in reading (omitted or lost)", "quotation choice (و/ف)"]
VERDICT_PLAIN = {
    "reading error? (dots only)": "Same letter shapes, different dots",
    "reading error? (letters)": "One or two letters differ",
    "different word": "A different word",
    "word not in verse": "Extra word in the reading",
    "word not in reading (omitted or lost)": "Verse word missing from the reading",
    "quotation choice (و/ف)": "و / ف added or dropped",
}


def diff_marks(a: str, b: str) -> tuple[str, str]:
    """Normalised a and b with the differing letters wrapped in <mark>."""
    import difflib
    na, nb = norm(a), norm(b)
    sm = difflib.SequenceMatcher(None, na, nb)
    oa, ob = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        sa, sb = E(na[i1:i2]), E(nb[j1:j2])
        if op == "equal":
            oa.append(sa); ob.append(sb)
        else:
            if sa: oa.append(f"<mark>{sa}</mark>")
            if sb: ob.append(f"<mark>{sb}</mark>")
    return "".join(oa), "".join(ob)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml", default="1005-000-001-002")
    ap.add_argument("--page", type=int, default=0)
    ap.add_argument("--cards", type=int, default=40)
    args = ap.parse_args()
    R = json.loads((HERE / "out/quotes.json").read_text(encoding="utf-8"))
    docs = list_docs()

    # ------------------------------------------------ numbers
    Q = [(s, q) for s, d in R.items() for q in d["quotes"]]
    n_docs = len(R)
    n_words = sum(d["words"] for d in R.values())
    n_pages = sum(d["pages"] for d in R.values())
    docs_q = sum(1 for d in R.values() if d["quotes"])
    n_br = sum(d["brackets"] for d in R.values())
    n_brq = sum(d["brackets_with_quote"] for d in R.values())
    n_bq = sum(q["bracketed"] for s, q in Q)
    exact = [x for x in Q if x[1]["differs"] == 0]
    exact_sp = [x for x in exact if any(o["kind"] == "spelling" for o in x[1]["ops"])]
    differ = [x for x in Q if x[1]["differs"] > 0]
    verdicts = Counter(o["verdict"] for s, q in Q for o in q["ops"] if o.get("verdict"))
    words_checked = sum(len(q["doc_words"]) for s, q in Q)
    cit = [q for s, q in Q if q["citation"]]
    cit_s = sum(1 for q in cit if q["citation_agrees"])
    cit_v = sum(1 for q in cit if q.get("citation_verse_agrees"))
    by_source = Counter(R[s]["source"] for s in R)
    vow = {"vowelled": [0, 0], "plain": [0, 0]}
    for s_, q in Q:
        L = len(re.findall("[\u0621-\u064A]", q["reading"]))
        Hh = len(re.findall("[\u064B-\u0652]", q["reading"]))
        k = "vowelled" if L and Hh / L > 0.3 else "plain"
        vow[k][0] += sum(len(o["doc"]) for o in q["ops"])
        vow[k][1] += sum(1 for o in q["ops"] if (o.get("verdict") or "").startswith("reading"))
    stats = dict(docs=n_docs, pages=n_pages, words=n_words, docs_with_quotes=docs_q,
                 brackets=n_br, brackets_with_quote=n_brq, quotes=len(Q), bracketed=n_bq,
                 exact=len(exact), exact_with_spelling=len(exact_sp), differing=len(differ),
                 words_in_quotes=words_checked, verdicts=dict(verdicts), citations=len(cit),
                 citation_sura_agrees=cit_s, citation_verse_agrees=cit_v, sources=dict(by_source), vowelled=vow)
    (HERE / "out/report_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False))

    # ------------------------------------------------ pick examples
    # differing words: per verdict, spread over documents
    picks = defaultdict(list)
    per_doc = Counter()
    for s, q in sorted(Q, key=lambda x: (x[0], x[1]["doc_words"][0])):
        for o in q["ops"]:
            v = o.get("verdict")
            if not v or not o["doc"] or docs[s]["pdf"] is None:
                continue
            picks[v].append((s, q, o))
    quota = {"reading error? (dots only)": 12, "reading error? (letters)": 14, "different word": 4,
             "word not in verse": 4, "word not in reading (omitted or lost)": 0, "quotation choice (و/ف)": 4}
    chosen = []
    for v in VERDICT_ORDER:
        lst, got, seen = picks.get(v, []), [], Counter()
        for cap in (1, 2, 3, 99):
            for x in lst:
                if len(got) >= quota.get(v, 0):
                    break
                if x not in got and seen[x[0]] < cap:
                    got.append(x); seen[x[0]] += 1
        chosen += got
    # exact quotations shown whole: bracketed, on one page, 5–14 words, different docs
    ex_show, seen = [], set()
    for s, q in exact:
        if s in seen or docs[s]["pdf"] is None or not q["bracketed"]:
            continue
        if 5 <= len(q["doc_words"]) <= 14:
            ex_show.append((s, q)); seen.add(s)
        if len(ex_show) >= 4:
            break
    # differing quotations shown whole, with the differences boxed
    dq_show, seen = [], set()
    for s, q in sorted(differ, key=lambda x: -sum(o["kind"] in ("dots", "letters") for o in x[1]["ops"])):
        if s in seen or docs[s]["pdf"] is None or len(q["doc_words"]) > 20:
            continue
        dq_show.append((s, q)); seen.add(s)
        if len(dq_show) >= 4:
            break

    need = defaultdict(list)
    for s, q, o in chosen:
        need[s].append(("card", q, o))
    for s, q in ex_show:
        need[s].append(("exact", q, None))
    for s, q in dq_show:
        need[s].append(("dq", q, None))

    cards, exacts, dqs = {}, {}, {}
    for s, items in need.items():
        doc = load_doc(docs[s]["json"])
        W = doc["words"]
        pages = Pages(docs[s]["pdf"])
        for kind, q, o in items:
            if kind == "card":
                w = W[o["doc"][0]]
                wb = union([W[i]["box"] for i in o["doc"]])
                ink = crop(pages, w["page"], wb, margin_in=0.06)
                ctx_ids = [i for i in range(max(0, o["doc"][0] - 3), min(len(W), o["doc"][-1] + 4))
                           if W[i]["page"] == w["page"] and abs(W[i]["box"][1] - w["box"][1]) < 0.25]
                ctx = crop(pages, w["page"], union([W[i]["box"] for i in ctx_ids]), margin_in=0.06,
                           marks=[(wb, (214, 120, 0))], max_w=700)
                cards[(s, q["doc_words"][0], o["doc"][0])] = (data_uri(ink), data_uri(ctx), w["page"])
            else:
                ids = [i for i in q["doc_words"] if W[i]["page"] == W[q["doc_words"][0]]["page"]]
                pg = W[ids[0]]["page"]
                marks = []
                if kind == "dq":
                    for op in q["ops"]:
                        if op.get("verdict") and op["doc"]:
                            marks.append((union([W[i]["box"] for i in op["doc"]]), (214, 120, 0)))
                img = crop(pages, pg, union([W[i]["box"] for i in ids]), margin_in=0.08,
                           marks=marks, max_w=900)
                (exacts if kind == "exact" else dqs)[(s, q["doc_words"][0])] = (data_uri(img, 66), pg)
        pages.close()

    # ------------------------------------------------ XML view
    xml_html = xml_section(args.xml, args.page, docs)

    # ------------------------------------------------ write
    out = []
    out.append(HEAD)
    out.append(f"""
<header class="top">
 <p class="eyebrow">inkscript · experiment 20 · {E(str(stats['docs']))} documents</p>
 <h1>Checking the Quran quotations</h1>
 <p class="lede">These journals quote the Quran, usually inside the ornate brackets <span class="ar">﴿ ﴾</span>.
 A quotation can be checked word by word against the canonical text, with no AI involved. Each
 quotation then links to its sura and verse, and every word that differs from the verse is a place
 where Azure may have misread the page. Those words are shown below on the ink.</p>
</header>

<section class="tiles">
 <div class="tile"><b>{stats['quotes']:,}</b><span>quotations found in {stats['docs_with_quotes']} of {stats['docs']} documents, each linked to its sura and verse</span></div>
 <div class="tile"><b>{stats['words_in_quotes']:,}</b><span>words of the reading checked against the verse they quote</span></div>
 <div class="tile good"><b>{stats['exact']:,}</b><span>exactly the verse after normalisation ({stats['exact_with_spelling']} of them in Uthmani spelling)</span></div>
 <div class="tile warn"><b>{stats['differing']:,}</b><span>differ in at least one word: {sum(verdicts.values()):,} differing words in all</span></div>
</section>

<section class="prose">
 <h2>What was checked</h2>
 <p>{stats['docs']} documents available on this machine ({', '.join(f'{v} {k}' for k, v in by_source.items())}),
 {stats['pages']:,} pages and {stats['words']:,} words of Azure's reading. They held {stats['brackets']} spans
 inside <span class="ar">﴿ ﴾</span>; {stats['brackets_with_quote']} of them contain a quotation that was found. Most of the others
 are not quotations at all. Azure reads the honorific signs <span class="ar">ﷺ</span> and
 <span class="ar">رضي الله عنه</span> as <span class="ar">﴿</span> or <span class="ar">﴾</span>, so ordinary prose ends up between brackets.
 {stats['quotes'] - stats['bracketed']} quotations were found without the ornate brackets, set in <span class="ar">(( ))</span>, quotation marks or plain text.
 Together the quotations cover {stats['words_in_quotes']:,} words, each now confirmed or questioned by a second source.</p>
 <p>Words are compared after normalisation: vowel marks, Quranic signs and tatweel are removed, the alef forms become
 <span class="ar">ا</span>, <span class="ar">ى</span> becomes <span class="ar">ي</span>, <span class="ar">ة</span> becomes <span class="ar">ه</span>, and hamza seats are dropped. A quotation printed in Uthmani
 script (<span class="ar">ٱلْعَٰلَمِينَ</span>, <span class="ar">ءَاتَيْنَٰكَ</span>) matches on a looser key without long alefs.
 A cross-check: where the author cites the sura after the quotation ({stats['citations']} times), the citation names the
 same sura {stats['citation_sura_agrees']} times and the same verse {stats['citation_verse_agrees']} times. The misses are mostly verses whose
 words repeat elsewhere in the Quran, and wrong citations in the source.</p>
</section>
""")
    out.append('<section><h2>How the differing words fall</h2><div class="bars">')
    mx = max(verdicts.values()) if verdicts else 1
    for v in VERDICT_ORDER:
        n = verdicts.get(v, 0)
        out.append(f'<div class="bar"><span class="bl">{E(VERDICT_PLAIN[v])}</span>'
                   f'<span class="bt"><span class="bf {"err" if "error" in v else "var"}" style="width:{100 * n / mx:.1f}%"></span></span>'
                   f'<span class="bn">{n}</span></div>')
    out.append('</div><p class="note">Orange: probably a misreading by Azure, because the verse is known and the word nearly matches it. '
               'Grey: more often a choice made by the author (a word left out, a و added at the start) or a quotation boundary. '
               'Every one of these is a word to check on the ink. None has been corrected.</p>')
    vv_, pp_ = vow["vowelled"], vow["plain"]
    out.append(f'<p class="prose">Looked at by eye, 24 of these words picked at random from the two orange groups: '
               f'<b>20 are misreadings by Azure</b> (the ink shows the verse\'s word), 3 are the author\'s own wording, '
               f'and 1 is a wrong alignment. The misreadings cluster in fully vowelled and Uthmani-script quotations. Azure '
               f'reads the small dagger alef as a letter or drops it (<span class="ar">لَحَٰفِظُونَ</span> read as <span class="ar">لَفِظُونَ</span>), '
               f'and the dense harakat cost it dots (<span class="ar">الرَّجِيمِ</span> read as <span class="ar">الرَّحِيمِ</span>). '
               f'In vowelled quotations {vv_[1]} of {vv_[0]:,} words ({100 * vv_[1] / max(1, vv_[0]):.1f}%) are flagged this way, '
               f'against {pp_[1]} of {pp_[0]:,} ({100 * pp_[1] / max(1, pp_[0]):.1f}%) in unvowelled ones. On body text, '
               f'Azure\'s letter errors are rare (experiment 17).</p></section>')

    out.append('<section><h2>Matched exactly</h2><div class="quotes">')
    for s, q in ex_show:
        img, pg = exacts[(s, q["doc_words"][0])]
        out.append(f'<figure class="quote"><img src="{img}" alt="ink of the quotation">'
                   f'<figcaption><span class="ref ok">{E(q["sura_name"])} {q["sura"]}:{q["aya"]}'
                   f'{"–" + str(q["aya_end"]) if q["aya_end"] != q["aya"] else ""} ✓</span>'
                   f'<span class="ar verse">{E(q["verse"])}</span><span class="src">{E(s)} · p. {pg}</span></figcaption></figure>')
    out.append('</div></section>')

    out.append('<section><h2>Quotations that differ: whole quotation, differing words boxed</h2><div class="quotes">')
    for s, q in dq_show:
        img, pg = dqs[(s, q["doc_words"][0])]
        rows = []
        for o in q["ops"]:
            if o.get("verdict"):
                rd = " ".join(o2 for o2 in [load_text(R, s, o)])
                rows.append(f'<li><span class="ar">{E(rd) or "—"}</span> → <span class="ar">{E(" ".join(x["v"] for x in o["q"])) or "—"}</span> <i>{E(VERDICT_PLAIN[o["verdict"]])}</i></li>')
        out.append(f'<figure class="quote"><img src="{img}" alt="ink of the quotation">'
                   f'<figcaption><span class="ref bad">{E(q["sura_name"])} {q["sura"]}:{q["aya"]}'
                   f'{"–" + str(q["aya_end"]) if q["aya_end"] != q["aya"] else ""} · {q["differs"]} differ</span>'
                   f'<span class="ar verse">{E(q["verse"])}</span><ul class="diffs">{"".join(rows)}</ul>'
                   f'<span class="src">{E(s)} · p. {pg}</span></figcaption></figure>')
    out.append('</div></section>')

    out.append('<section><h2>Differing words on the ink</h2><p class="note">Each card shows the word as printed, the line around it, '
               'Azure\'s reading and the verse\'s word. Highlighted letters are where the two differ after normalisation.</p>')
    for v in VERDICT_ORDER:
        group = [(s, q, o) for s, q, o in chosen if o["verdict"] == v]
        if not group:
            continue
        out.append(f'<h3>{E(VERDICT_PLAIN[v])} <small>{verdicts.get(v, 0)} words</small></h3><div class="cards">')
        for s, q, o in group:
            ink, ctx, pg = cards[(s, q["doc_words"][0], o["doc"][0])]
            rd = load_text(R, s, o)
            vs = " ".join(x["w"] for x in o["q"])
            a, b = diff_marks(rd, vs) if o["kind"] in ("dots", "letters", "other") else (E(norm(rd)), E(norm(vs)))
            vv = " ".join(x["v"] for x in o["q"])
            out.append(f'''<article class="card"><div class="ink"><img src="{ink}" alt="printed word"></div>
<dl><dt>Azure</dt><dd class="ar">{E(rd) or "—"} <span class="n">{a}</span></dd>
<dt>Verse</dt><dd class="ar">{E(vv) or "—"} <span class="n">{b}</span></dd></dl>
<img class="ctx" src="{ctx}" alt="the line around it">
<p class="src">{E(q["sura_name"])} {o["q"][0]["s"] if o["q"] else q["sura"]}:{o["q"][0]["a"] if o["q"] else q["aya"]} · {E(s)} p. {pg}</p></article>''')
        out.append('</div>')
    out.append('</section>')
    out.append(xml_html)
    out.append(per_doc_table(R))
    out.append(FOOT)
    (HERE / "out/report.html").write_text("".join(out), encoding="utf-8")
    print("wrote", HERE / "out/report.html", sum(len(x) for x in out) // 1024, "KB")


_TEXT_CACHE = {}


def load_text(R, s, o):
    if s not in _TEXT_CACHE:
        _TEXT_CACHE[s] = load_doc(list_docs()[s]["json"])["words"]
    return " ".join(_TEXT_CACHE[s][i]["text"] for i in o["doc"])


def per_doc_table(R):
    rows = []
    for s, d in sorted(R.items(), key=lambda x: -len(x[1]["quotes"])):
        if not d["quotes"] and not d["brackets"]:
            continue
        ex = sum(q["differs"] == 0 for q in d["quotes"])
        rows.append(f'<tr><td>{E(s)}</td><td>{E(d["source"])}</td><td>{d["pages"]}</td><td>{d["words"]:,}</td>'
                    f'<td>{d["brackets"]}</td><td>{len(d["quotes"])}</td><td>{ex}</td><td>{len(d["quotes"]) - ex}</td></tr>')
    rest = sum(1 for d in R.values() if not d["quotes"] and not d["brackets"])
    return (f'<section><details><summary>Every document with a quotation or a bracket ({len(rows)}; '
            f'{rest} more have neither)</summary><div class="tw"><table><thead><tr><th>document</th><th>from</th>'
            f'<th>pages</th><th>words</th><th>﴿ ﴾ spans</th><th>quotations</th><th>exact</th><th>differ</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details></section>')


def xml_section(stem, page, docs):
    p = HERE / "out/tei" / f"{stem}.tei.xml"
    if not p.exists():
        return ""
    root = ET.parse(p).getroot()
    summ = json.loads((HERE / "out/tei/summary.json").read_text()).get(stem, {})
    zones = {z.get(XID): z.get("points") for z in root.iter(TEI + "zone")}
    words = {w.get(XID): w for w in root.iter(TEI + "w")}
    # pick the page with the most Quran-linked words
    ann = list(root.iter(TEI + "annotation"))
    cnt = Counter()
    for a in ann:
        for t in a.get("target", "").split():
            cnt[int(re.match(r"#p(\d+)w", t).group(1))] += 1
    for wid_, w in words.items():       # pages with a flagged word come first
        if w.get("ana") == "#trust.flagged":
            cnt[int(re.match(r"p(\d+)w", wid_).group(1))] += 1000
    pg = page or (cnt.most_common(1)[0][0] if cnt else 1)
    doc = load_doc(docs[stem]["json"])
    pages = Pages(docs[stem]["pdf"])
    Wi, Hi = pages.size_in(pg)
    polys, marks = [], []
    for wid_, w in words.items():
        if not wid_.startswith(f"p{pg}w"):
            continue
        pts = [tuple(int(v) / 300 for v in xy.split(",")) for xy in zones[f"z.{wid_}"].split()]
        bx = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        a = w.get("ana")
        if a == "#trust.agreed":
            polys.append((bx, (40, 160, 95), 0.35))
        elif a == "#trust.flagged":
            polys.append((bx, (240, 140, 0), 0.45))
            marks.append((bx, (214, 100, 0)))
    pix = crop(pages, pg, (0, 0, Wi, Hi), margin_in=0, dpi=110, polys=polys, marks=marks)
    pimg = data_uri(pix, 60)
    pages.close()

    # outline of that page: walk the body in order
    body = root.find(f"{TEI}text/{TEI}body")
    lines = []
    on_page = False

    def words_of(el):
        return [w for w in el.iter(TEI + "w")]

    def label(el):
        tag = el.tag.replace(TEI, "")
        attrs = " ".join(f'{k.split("}")[-1]}="{v}"' for k, v in el.attrib.items()
                         if k.split("}")[-1] in ("type", "place", "resp", "n"))
        return tag, attrs

    def walk(el, depth):
        nonlocal on_page
        for ch in el:
            tag, attrs = label(ch)
            if tag == "pb":
                on_page = ch.get("n") == str(pg)
                if on_page:
                    lines.append(f'<li class="d{depth} pb">&lt;pb n="{pg}"/&gt; page {pg}</li>')
                continue
            if tag == "div":
                if on_page:
                    lines.append(f'<li class="d{depth}"><code>&lt;div {E(attrs)}&gt;</code></li>')
                walk(ch, depth + 1)
                continue
            if not on_page:
                # a block can start on this page from a pb inside it
                continue
            ws = words_of(ch)
            txt = " ".join((w.text or "") for w in ws)
            flag = sum(w.get("ana") == "#trust.flagged" for w in ws)
            agr = sum(w.get("ana") == "#trust.agreed" for w in ws)
            glyph = sum(1 for w in ws if w.get("corresp"))
            meta = f'{len(ws)} words' + (f' · {glyph} linked to glyphs' if glyph else '') + \
                   (f' · <span class="g">{agr} agreed</span>' if agr else '') + \
                   (f' · <span class="o">{flag} flagged</span>' if flag else '')
            short = txt if len(txt) < 140 else txt[:140] + " …"
            lines.append(f'<li class="d{depth}"><code>&lt;{tag}{" " + E(attrs) if attrs else ""}&gt;</code> '
                         f'<span class="meta">{meta}</span><div class="ar t">{E(short)}</div></li>')
    walk(body, 0)

    # a raw excerpt: the first flagged word's paragraph start, and one annotation
    ex_w = next((w for w in root.iter(TEI + "w") if w.get("ana") == "#trust.flagged"
                 and w.get(XID).startswith(f"p{pg}w")), None)
    if ex_w is None:
        ex_w = next(iter(words.values()))
    raw_w = ET.tostring(ex_w, encoding="unicode").replace(' xmlns="http://www.tei-c.org/ns/1.0"', "")
    zid = f"z.{ex_w.get(XID)}"
    raw_z = f'<zone xml:id="{zid}" points="{zones[zid]}"/>'
    a0 = next((a for a in ann if ex_w.get(XID) in a.get("target", "")), ann[0] if ann else None)
    raw_a = ET.tostring(a0, encoding="unicode").replace(' xmlns="http://www.tei-c.org/ns/1.0"', "") if a0 is not None else ""
    raw_a = re.sub(r'target="([^"]{120})[^"]*"', r'target="\1 …"', raw_a)
    hdr = root.find(f"{TEI}teiHeader")
    bib = hdr.find(f".//{TEI}biblStruct")
    raw_b = ET.tostring(bib, encoding="unicode").replace(' xmlns="http://www.tei-c.org/ns/1.0"', "")
    raw_b = re.sub(r"\n\s*\n", "\n", raw_b)
    linked = f'{summ.get("linked_words", 0):,} of {summ.get("words", 0):,} words linked to {summ.get("placements_linked", 0):,} glyphs of the PDF' \
        if summ.get("shapes") else "no glyph links (this document has no built PDF here)"
    roles = ", ".join(f"{k} {v}" for k, v in sorted(summ.get("roles", {}).items(), key=lambda x: -x[1]))
    return f"""
<section id="xml"><h2>One document as data: {E(stem)}</h2>
<p class="prose">A TEI file beside the PDF ({E(stem)}.tei.xml) describes the document: bibliographic header, the body in reading order
with each paragraph's role, every word with its page, its box on the scan and the glyph(s) it is drawn with, the Quran links, and a
trust mark per word. This document: {summ.get('words', 0):,} words, {summ.get('paragraphs', 0)} paragraphs (roles found: {E(roles) or 'none'}),
{linked}, {summ.get('quotes', 0)} Quran quotations, {summ.get('agreed', 0)} words marked agreed and {summ.get('flagged', 0)} flagged.
Page {pg} is shown: <span class="g">green</span> words are confirmed by the verse, <span class="o">orange</span> words differ from it.</p>
<div class="xmlview"><figure class="page"><img src="{pimg}" alt="page {pg} with trust marks"></figure>
<div class="outline"><h3>Page {pg} in the XML, in reading order</h3><ul>{''.join(lines)}</ul></div></div>
<h3>What it looks like inside</h3>
<div class="raw"><p>One word: its zone on the scan, Azure's confidence, the glyph in our PDF, and its trust mark.</p>
<pre dir="ltr">{E(raw_z)}
{E(raw_w)}</pre>
<p>Its Quran link, in the standOff part:</p><pre dir="ltr">{E(raw_a)}</pre>
<p>The bibliographic part (empty fields are where we have nothing yet):</p><pre dir="ltr">{E(raw_b)}</pre></div>
</section>"""


HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Quran Quotation Check</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Amiri:wght@400;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
/* Layout: a single reading column of a lab notebook; examples break out into wrapping card grids. */
:root{
 --bg:#f6f7f4; --surface:#ffffff; --ink:#1e2420; --muted:#5d665f; --line:#d9ddd6;
 --accent:#1d6b57; --ok:#2a8a5c; --warn:#c96d00; --warn-bg:#fdebd2; --mark:#ffd79a;
 --display:"Source Serif 4", Georgia, serif; --body:"Source Serif 4", Georgia, serif;
 --arabic:"Amiri", "Noto Naskh Arabic", "Traditional Arabic", serif; --mono:"IBM Plex Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
 --bg:#141816; --surface:#1c211e; --ink:#e4e8e3; --muted:#a2aba4; --line:#323a35;
 --accent:#6cc4a6; --ok:#5cc28e; --warn:#f0a040; --warn-bg:#3a2a14; --mark:#7a5418; color-scheme:dark}}
:root[data-theme="dark"]{
 --bg:#141816; --surface:#1c211e; --ink:#e4e8e3; --muted:#a2aba4; --line:#323a35;
 --accent:#6cc4a6; --ok:#5cc28e; --warn:#f0a040; --warn-bg:#3a2a14; --mark:#7a5418; color-scheme:dark}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.55 var(--body);padding-block:24px 64px;padding-inline:max(16px,4vw)}
main{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:40px}
h1,h2,h3{font-family:var(--display);text-wrap:balance;line-height:1.2;margin:0 0 .5em}
h1{font-size:2.2rem;font-weight:600} h2{font-size:1.45rem;font-weight:600} h3{font-size:1.1rem;font-weight:600;margin-top:1.2em}
h3 small{font-weight:400;color:var(--muted);font-size:.85rem;margin-inline-start:.4em}
p{margin:.5em 0} .prose,.lede{max-width:68ch}
.lede{font-size:1.1rem}
.eyebrow{font-family:var(--mono);font-size:.78rem;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin:0 0 .6em}
.ar{font-family:var(--arabic);direction:rtl;unicode-bidi:isolate;font-size:1.15em}
.note{color:var(--muted);font-size:.92rem;max-width:72ch}
mark{background:var(--mark);color:inherit;border-radius:2px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:14px 16px;display:flex;flex-direction:column;gap:4px}
.tile b{font-family:var(--display);font-size:2rem;font-variant-numeric:tabular-nums;line-height:1}
.tile span{color:var(--muted);font-size:.9rem}
.tile.good b{color:var(--ok)} .tile.warn b{color:var(--warn)}
.bars{display:flex;flex-direction:column;gap:8px;max-width:760px}
.bar{display:grid;grid-template-columns:minmax(120px,15rem) 1fr 3.5rem;gap:12px;align-items:center;font-size:.95rem}
.bt{height:14px;background:var(--line);border-radius:3px;overflow:hidden}
.bf{display:block;height:100%} .bf.err{background:var(--warn)} .bf.var{background:var(--muted)}
.bn{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:end}
.quotes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,460px),1fr));gap:16px}
figure{margin:0}
.quote{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px;display:flex;flex-direction:column;gap:10px;min-width:0}
.quote img{width:100%;height:auto;border-radius:3px;background:#fff}
figcaption{display:flex;flex-direction:column;gap:6px;min-width:0}
.ref{font-family:var(--mono);font-size:.85rem} .ref.ok{color:var(--ok)} .ref.bad{color:var(--warn)}
.verse{line-height:1.9}
.src{font-family:var(--mono);font-size:.75rem;color:var(--muted)}
.diffs{margin:0;padding-inline-start:1.1em;font-size:.92rem} .diffs i{color:var(--muted);font-style:normal;font-size:.85rem}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr));gap:12px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:10px 12px;display:flex;flex-direction:column;gap:8px;min-width:0}
.card .ink{display:flex;justify-content:center;background:#fff;border-radius:3px;padding:6px}
.card .ink img{max-height:90px;width:auto}
.card .ctx{width:100%;height:auto;border-radius:3px;background:#fff}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;margin:0;align-items:baseline}
dt{font-family:var(--mono);font-size:.72rem;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
dd{margin:0} dd .n{display:block;font-size:.85em;color:var(--muted)}
.xmlview{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;align-items:start}
@media (max-width:820px){.xmlview{grid-template-columns:1fr}}
.page img{width:100%;height:auto;border:1px solid var(--line);border-radius:4px;background:#fff}
.outline{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px 14px;min-width:0;max-height:1100px;overflow:auto}
.outline ul{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px}
.outline li{border-inline-start:2px solid var(--line);padding-inline-start:10px}
.outline li.d1{margin-inline-start:14px} .outline li.d2{margin-inline-start:28px}
.outline li.pb{border-color:var(--accent);font-family:var(--mono);font-size:.8rem;color:var(--accent)}
.outline code{font-family:var(--mono);font-size:.8rem;color:var(--accent)}
.outline .meta{font-size:.8rem;color:var(--muted)} .outline .t{font-size:1rem;line-height:1.7}
.g{color:var(--ok);font-weight:600} .o{color:var(--warn);font-weight:600}
.raw pre{font-family:var(--mono);font-size:.78rem;line-height:1.5;background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px;overflow-x:auto;white-space:pre}
details summary{cursor:pointer;font-family:var(--display);font-size:1.1rem}
.tw{overflow-x:auto;margin-top:10px}
table{border-collapse:collapse;font-size:.88rem;font-variant-numeric:tabular-nums}
th,td{padding:4px 10px;border-bottom:1px solid var(--line);text-align:end;white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:start;font-family:var(--mono)}
a{color:var(--accent)} :focus-visible{outline:2px solid var(--accent);outline-offset:2px}
</style></head><body><main>
"""

FOOT = """<footer class="note"><p>Quran text: Tanzil Project, Simple Clean and Simple editions v1.1, CC BY 3.0, verbatim (tanzil.net).
Ink crops are 300-dpi renders of the scans, cut out by Azure's word boxes. Code and method: experiments/20_document_data/README.md.</p></footer>
</main></body></html>
"""

if __name__ == "__main__":
    main()
