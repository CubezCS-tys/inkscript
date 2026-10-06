"""Every page, line and word with its box: one ALTO file per document (ALTO 4.4, Library of Congress; the
libraries' standard for OCR text with coordinates).

    write(doc, quotes, marks, stem, path, jats_name)

Layout:
  Description   MeasurementUnit pixel = pixels of the 300-dpi scan (the frame of shapes.json and of
                `inkscript correct`); the source image; one OCRProcessing step for Azure (model, API version)
                and one Processing step each for Gemini's page 1 (when used), inkscript and the Tanzil check.
  Tags          StructureTags for paragraph roles (body, title, author, sectionHeading, footnote, pageHeader,
                pageFooter, pageNumber), OtherTags for the trust marks (trust.verified/agreed/flagged) and their
                reasons (why.conf, why.speck…), and one OtherTag per Quran quotation (TYPE quran-quotation,
                LABEL sura and verse, URI https://tanzil.net/#S:A).
  Layout        Page (ID page<n>, PHYSICAL_IMG_NR, PRINTED_IMG_NR when the page number was found, PAGECLASS
                born-digital for pages whose text in the PDF is the publisher's) > PrintSpace > TextBlock (one per
                Azure paragraph and page, ID p<page>b<n>, TAGREFS its role, xlink:href <stem>.jats.xml#<id>, the
                place of its words in the JATS file; IDNEXT chains a paragraph that continues on the next page)
                > TextLine (Azure's lines, BASEDIRECTION rtl for Arabic lines) > String.
  String        ID p<page>w<nnnn> (reading order on the page), CONTENT = the text the faithful PDF carries for
                the word, HPOS/VPOS/WIDTH/HEIGHT its box, WC Azure's confidence, TAGREFS its trust mark, reasons
                and quotation, a Shape/Polygon with Azure's four corners, and an ALTERNATIVE with the other
                reader's text where two readers differ (page 1: Azure's reading under Gemini's) or with the
                verse's word where a Quran quotation differs. Words are in logical (reading) order within each
                line; SP between them.

The word's glyphs in our PDF: the same id is written into the build's <stem>.shapes.json placements ("word"),
each of which holds the glyph's page, box (same pixel frame) and shape ids; `inkscript correct` and
inkscript.pdf.inspect.page_glyphs find a glyph in the PDF by that page and box.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lxml import etree

from .document import ARABIC, LATIN
from .jats import block_ids, front_matter
from .jats import printed_pages
from .quran import TANZIL_CREDIT
from .trust import MARKS, REASONS

NS = "http://www.loc.gov/standards/alto/ns-v4#"
XLINK = "http://www.w3.org/1999/xlink"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA = "https://www.loc.gov/standards/alto/v4/alto-4-4.xsd"
ROLES = ["body", "title", "rubric", "author", "sectionHeading", "footnote", "pageHeader", "pageFooter", "pageNumber"]


def A(parent, tag, text=None, **attrs):
    a = {}
    for k, v in attrs.items():
        if v is None:
            continue
        a[f"{{{XLINK}}}{k[6:]}" if k.startswith("xlink_") else k] = str(v)
    e = etree.SubElement(parent, f"{{{NS}}}{tag}", a)
    if text is not None:
        e.text = text
    return e


def _f(v: float) -> str:
    return f"{v:.0f}"


def _box(el_attrs: dict, box):
    x0, y0, x1, y1 = box
    el_attrs.update(HPOS=_f(x0), VPOS=_f(y0), WIDTH=_f(max(1, x1 - x0)), HEIGHT=_f(max(1, y1 - y0)))
    return el_attrs


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def write(doc: dict, quotes: list[dict], marks: dict, stem: str, path: Path, jats_name: str | None = None,
          born_digital=(), version: str = "", jats_ids=None) -> dict:
    words, paras, kinds = doc["words"], doc["paras"], doc["roles"]
    root = etree.Element(f"{{{NS}}}alto", nsmap={None: NS, "xlink": XLINK, "xsi": XSI},
                         attrib={"SCHEMAVERSION": "4.4", f"{{{XSI}}}schemaLocation": f"{NS} {SCHEMA}"})
    desc = A(root, "Description")
    A(desc, "MeasurementUnit", "pixel")
    sii = A(desc, "sourceImageInformation")
    A(sii, "fileName", f"{stem}.pdf")
    A(sii, "documentIdentifier", stem, documentIdentifierLocation="Mandumah")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    def step(tag, pid, what, creator, name, ver, settings=None):
        el = A(desc, tag, ID=pid)
        st = A(el, "ocrProcessingStep") if tag == "OCRProcessing" else el
        A(st, "processingCategory", "contentGeneration" if pid in ("azure", "gemini") else "other")
        if pid == "inkscript":
            A(st, "processingDateTime", now)
        A(st, "processingStepDescription", what)
        if settings:
            A(st, "processingStepSettings", settings)
        sw = A(st, "processingSoftware")
        A(sw, "softwareCreator", creator)
        A(sw, "softwareName", name)
        if ver:
            A(sw, "softwareVersion", ver)
    step("OCRProcessing", "azure", "Text recognition: words, boxes, lines, paragraphs, word confidence (WC).",
         "Microsoft", "Azure Document Intelligence", f"{doc.get('model') or ''} API {doc.get('api') or ''}".strip())
    if doc["gemini_pages"]:
        step("Processing", "gemini", "Page 1 read again; that reading is the text of the faithful PDF on page 1, "
             "fitted into Azure's word boxes. Where it differs from Azure's, Azure's is the ALTERNATIVE.",
             "Google", "Gemini", "")
    step("Processing", "inkscript", "Faithful PDF (each word drawn with its own ink), paragraph roles by position "
         "(experiment 20), trust marks (experiment 22's default rule), this file.", "inkscript", "inkscript",
         version, "trust: conf<0.8 + speck + ornament + Latin on Arabic page + Persian letter + Quran difference")
    step("Processing", "tanzil", f"Quran quotations matched against the canonical text: {TANZIL_CREDIT}.",
         "Tanzil Project", "Tanzil Quran Text (Simple Clean / Simple)", "1.1")

    tags = A(root, "Tags")
    for r in ROLES:
        A(tags, "StructureTag", ID=f"role.{r}", TYPE="paragraph-role", LABEL=r,
          DESCRIPTION=None if r == "body" else "found by position rules (experiment 20), not checked")
    for m, d in MARKS.items():
        A(tags, "OtherTag", ID=f"trust.{m}", TYPE="trust", LABEL=m, DESCRIPTION=d)
    for r, (label, d) in REASONS.items():
        A(tags, "OtherTag", ID=f"why.{r}", TYPE="trust-reason", LABEL=label, DESCRIPTION=d)
    qword = {}
    for n, qt in enumerate(quotes, 1):
        status = "equals the verse" if qt["differs"] == 0 else f"{qt['differs']} word(s) differ from the verse"
        A(tags, "OtherTag", ID=f"quran{n}", TYPE="quran-quotation", LABEL=f"{qt['sura_name']} {qt['ref']}",
          DESCRIPTION=status, URI=f"https://tanzil.net/#{qt['sura']}:{qt['aya']}")
        for k in qt["doc_words"]:
            qword[k] = n
    verse_word = {}
    for qt in quotes:
        for o in qt["ops"]:
            if o["kind"] in ("dots", "letters", "other") and len(o["doc"]) == 1:
                verse_word[o["doc"][0]] = " ".join(x["v"] for x in o["q"])

    fm = front_matter(doc)
    role_of = {}
    for i in range(len(paras)):
        role_of[i] = kinds[i] or "body"
    if fm:
        role_of[fm["title"]] = "title"
        for i in fm.get("rubric", []):
            role_of[i] = "rubric"
        for i in fm.get("authors", []):
            role_of[i] = "author"

    bids = block_ids(doc)
    blocks_by_page = {}
    for p in paras:
        chain = bids[p["idx"]]
        for j, (pg, bid) in enumerate(chain):
            nxt = chain[j + 1][1] if j + 1 < len(chain) else None
            blocks_by_page.setdefault(pg, []).append((p, bid, nxt, chain[0][1]))
    printed = printed_pages(doc)
    layout = A(root, "Layout")
    n_strings = 0
    for pn, pg in sorted(doc["pages"].items()):
        page = A(layout, "Page", ID=f"page{pn}", PHYSICAL_IMG_NR=str(pn), PRINTED_IMG_NR=printed.get(pn),
                 PAGECLASS="born-digital" if pn in born_digital else None,
                 WIDTH=_f(pg["w"]), HEIGHT=_f(pg["h"]))
        pw = [w for w in words if w["page"] == pn]
        ps_attrs = _box({}, _union([w["box"] for w in pw])) if pw else dict(HPOS="0", VPOS="0", WIDTH=_f(pg["w"]), HEIGHT=_f(pg["h"]))
        ps = A(page, "PrintSpace", **ps_attrs)
        for p, bid, nxt, first in blocks_by_page.get(pn, []):
            ks = [k for k in p["words"] if words[k]["page"] == pn]
            txt = " ".join(words[k]["text"] for k in ks)
            rtl = len(ARABIC.findall(txt)) >= len(LATIN.findall(txt))
            tb = A(ps, "TextBlock", **_box(dict(ID=bid, TAGREFS=f"role.{role_of[p['idx']]}", IDNEXT=nxt,
                                                LANG="ar" if rtl else None, BASEDIRECTION="rtl" if rtl else "ltr"),
                                           _union([words[k]["box"] for k in ks])),
                   **({"xlink_href": f"{jats_name}#{first}", "xlink_type": "simple"}
                      if jats_name and (jats_ids is None or first in jats_ids) else {}))
            # lines: Azure's, in the order their first word is read
            lines = {}
            for k in ks:
                lines.setdefault(words[k]["line"], []).append(k)
            for li, (lk, lks) in enumerate(lines.items(), 1):
                ltxt = " ".join(words[k]["text"] for k in lks)
                lrtl = len(ARABIC.findall(ltxt)) >= len(LATIN.findall(ltxt))
                tl = A(tb, "TextLine", **_box(dict(ID=f"{bid}l{li}", BASEDIRECTION="rtl" if lrtl else "ltr"),
                                              _union([words[k]["box"] for k in lks])))
                for j, k in enumerate(lks):
                    w = words[k]
                    if j:
                        A(tl, "SP")
                    m = marks.get(k)
                    tr = []
                    if m:
                        tr.append(f"trust.{m.mark}")
                        tr += [f"why.{r}" for r in m.why]
                    if k in qword:
                        tr.append(f"quran{qword[k]}")
                    st = A(tl, "String", **_box(dict(ID=w["id"], CONTENT=w["out"] or w["text"] or "?",
                                                     WC=f"{w['conf']:.3f}" if w["conf"] is not None else None,
                                                     TAGREFS=" ".join(tr) or None,
                                                     LANG=None if not LATIN.search(w["text"]) or not lrtl else "und"),
                                                w["box"]))
                    poly = w["poly"]
                    sh = A(st, "Shape")
                    A(sh, "Polygon", POINTS=" ".join(f"{poly[i]:.0f},{poly[i + 1]:.0f}" for i in range(0, len(poly), 2)))
                    if m and m.other and m.other != w["out"]:
                        A(st, "ALTERNATIVE", m.other, PURPOSE="azure-reading")
                    if k in verse_word:
                        A(st, "ALTERNATIVE", verse_word[k], PURPOSE="quran-verse")
                    n_strings += 1
    etree.indent(root, space=" ")
    path = Path(path)
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + etree.tostring(root, encoding="unicode") + "\n",
                    encoding="utf-8")
    return dict(pages=len(doc["pages"]), blocks=sum(len(v) for v in blocks_by_page.values()), strings=n_strings)
