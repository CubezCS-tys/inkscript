"""Experiment 38, step 4: the page's master files, JATS 1.4 + ALTO 4.4, in the format `inkscript edition` reads
-> out/pages/<pid>/master/<pid>.jats.xml, .alto.xml, .pdf (the scan as a one-page PDF), crops/.

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python master.py [PID ...] [--force] [--raw]

One page is one master (the editions are then built per page, so the old edition's page can be set beside it).
The front matter is the document's own from experiment 29's master (catalogue title, authors, journal, date;
abstracts and keywords left out: they are not on this page); a title block on the page replaces the title with
its printed words and is tied to them.

Block ids follow the editions' scheme (D20): p1b<n> text, p1t<n> a table with its cells p1t<n>c<rr><cc>, p1eq<n> a
formula, p1f<n> a picture. ALTO: text blocks with their role (role.sectionHeading, role.footnote, role.caption,
role.listItem, role.pageHeader...), tables as ComposedBlock, formulas and pictures as Illustration; the words inside
a picture (role.pictureText) and a formula (role.formulaInk) kept as their own blocks, so every Azure word is in the
ALTO exactly once. Words: Azure's, with their confidence (WC); a corrected word carries trust.corrected and Azure's
reading in <ALTERNATIVE PURPOSE="azure">; text kept from dots.mocr (a table cell Azure has no words for, a block
Azure skipped) carries source.dots and no WC. --raw writes the uncorrected master (corrections not applied).
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

from common import MASTERS, OUT, gold, pages, union

ALTO_ROLE = {"title": "title", "heading": "sectionHeading", "p": "body", "li": "listItem", "fn": "footnote",
             "caption": "caption", "header": "pageHeader", "footer": "pageFooter", "pagenum": "pageNumber"}
MML_NS = "http://www.w3.org/1998/Math/MathML"
DPI = 300


def e(s) -> str:
    return escape(s or "", {'"': "&quot;"})


# ------------------------------------------------------------------------------------------------ corrections

def apply_corrections(L: dict, C: dict | None) -> dict:
    """Word id -> list of new words (text, box, original) for every applied edit."""
    if not C:
        return {}
    words = {w["id"]: w for b in L["blocks"] for w in b["words"]}
    for b in L["blocks"]:
        for r in b.get("rows") or []:
            for c in r["cells"]:
                for w in c.get("words") or []:
                    words[w["id"]] = w
    rep = {}
    for ed in C["edits"]:
        if ed.get("status") != "applied":
            continue
        ids = ed["word_ids"]
        ws = [words[i] for i in ids if i in words]
        if not ws:
            continue
        after = (ed["after"] or "").split()
        bb = union(w["box"] for w in ws)
        orig = " ".join(w["text"] for w in ws)
        latin = bool(re.search(r"[A-Za-z]", ed["after"] or "")) and not re.search(r"[؀-ۿ]", ed["after"] or "")
        n = sum(len(a) for a in after) or 1
        new, x = [], (bb[0] if latin else bb[2])
        for a in after:
            wd = (bb[2] - bb[0]) * len(a) / n
            box = [x, bb[1], x + wd, bb[3]] if latin else [x - wd, bb[1], x, bb[3]]
            x = x + wd if latin else x - wd
            new.append(dict(text=a, box=box, orig=orig, conf=min(w.get("conf") or 1 for w in ws)))
        rep[ids[0]] = new
        for i in ids[1:]:
            rep[i] = []
    return rep


def corrected_words(ws: list[dict], rep: dict) -> list[dict]:
    out = []
    for w in ws:
        if w["id"] in rep:
            for k, n in enumerate(rep[w["id"]]):
                out.append(dict(w, id=f"{w['id']}c{k}", text=n["text"], box=n["box"], corrected=n["orig"]))
        else:
            out.append(w)
    return out


# ------------------------------------------------------------------------------------------------ ALTO

class Alto:
    def __init__(self, pid, W, H):
        self.pid, self.W, self.H = pid, W, H
        self.parts, self.nw = [], 0

    def strings(self, ws, dots=False) -> str:
        out = []
        for k, w in enumerate(ws):
            self.nw += 1
            x0, y0, x1, y1 = w["box"]
            tags = ["source.dots"] if dots else (["trust.corrected"] if w.get("corrected") else ["trust.agreed"])
            wc = "" if dots or w.get("conf") is None else f' WC="{w["conf"]:.3f}"'
            lang = ' LANG="en"' if re.search(r"[A-Za-z]", w["text"]) and not re.search(r"[؀-ۿ]", w["text"]) else ""
            alt = f'<ALTERNATIVE PURPOSE="azure">{e(w["corrected"])}</ALTERNATIVE>' if w.get("corrected") else ""
            out.append(f'<String ID="p1w{self.nw:04d}" CONTENT="{e(w["text"])}"{wc}{lang} TAGREFS="{" ".join(tags)}" '
                       f'HPOS="{x0:.0f}" VPOS="{y0:.0f}" WIDTH="{max(1, x1 - x0):.0f}" HEIGHT="{max(1, y1 - y0):.0f}"'
                       + (f">{alt}</String>" if alt else "/>"))
            if k < len(ws) - 1:
                out.append("<SP/>")
        return "".join(out)

    def textblock(self, bid, role, lines, href=None, dots=False, latin=False):
        """lines: list of word lists."""
        lines = [ln for ln in lines if ln]
        if not lines:
            return
        bb = union(w["box"] for ln in lines for w in ln)
        h = f' xlink:href="{self.pid}.jats.xml#{href}" xlink:type="simple"' if href else ""
        lang = 'LANG="en" BASEDIRECTION="ltr"' if latin else 'LANG="ar" BASEDIRECTION="rtl"'
        s = [f'<TextBlock ID="{bid}" TAGREFS="role.{role}" {lang} HPOS="{bb[0]:.0f}" VPOS="{bb[1]:.0f}" '
             f'WIDTH="{bb[2] - bb[0]:.0f}" HEIGHT="{bb[3] - bb[1]:.0f}"{h}>']
        for k, ln in enumerate(lines, 1):
            lb = union(w["box"] for w in ln)
            s.append(f'<TextLine ID="{bid}l{k}" HPOS="{lb[0]:.0f}" VPOS="{lb[1]:.0f}" WIDTH="{lb[2] - lb[0]:.0f}" '
                     f'HEIGHT="{lb[3] - lb[1]:.0f}">{self.strings(ln, dots)}</TextLine>')
        s.append("</TextBlock>")
        self.parts.append("".join(s))

    def raw(self, s):
        self.parts.append(s)

    def xml(self, printed: str | None) -> str:
        tags = "".join(f'<StructureTag ID="role.{r}" TYPE="paragraph-role" LABEL="{r}"/>' for r in
                       ("title", "sectionHeading", "body", "listItem", "footnote", "caption", "pageHeader",
                        "pageFooter", "pageNumber", "pictureText", "formulaInk", "tableCell"))
        tags += ('<OtherTag ID="trust.agreed" TYPE="trust" LABEL="agreed" DESCRIPTION="Azure\'s word, unchanged."/>'
                 '<OtherTag ID="trust.corrected" TYPE="trust" LABEL="corrected" DESCRIPTION="Corrected on the ink by '
                 'a model under strict rules (experiment 38); Azure\'s reading in ALTERNATIVE PURPOSE=azure."/>'
                 '<OtherTag ID="source.dots" TYPE="source" LABEL="dots" DESCRIPTION="Text from dots.mocr\'s reading '
                 '(no Azure word there); its box is the cell or block, split evenly."/>')
        pr = f' PRINTED_IMG_NR="{e(printed)}"' if printed else ""
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#" '
                'xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'SCHEMAVERSION="4.4" xsi:schemaLocation="http://www.loc.gov/standards/alto/ns-v4# '
                'https://www.loc.gov/standards/alto/v4/alto-4-4.xsd">'
                f'<Description><MeasurementUnit>pixel</MeasurementUnit><sourceImageInformation><fileName>{e(self.pid)}.pdf'
                '</fileName></sourceImageInformation><OCRProcessing ID="exp38"><ocrProcessingStep><processingCategory>'
                'contentGeneration</processingCategory><processingStepDescription>Words: Azure Document Intelligence '
                '(read). Layout, reading order, table grids, formulas: dots.mocr. Corrections: Gemini under strict '
                'rules (experiment 38). 300 dpi pixels.</processingStepDescription><processingSoftware><softwareCreator>'
                'inkscript</softwareCreator><softwareName>experiments/38_parser</softwareName><softwareVersion>exp38'
                '</softwareVersion></processingSoftware></ocrProcessingStep></OCRProcessing></Description>'
                f'<Tags>{tags}</Tags><Layout><Page ID="page1" PHYSICAL_IMG_NR="1"{pr} WIDTH="{self.W}" HEIGHT="{self.H}">'
                f'<PrintSpace HPOS="0" VPOS="0" WIDTH="{self.W}" HEIGHT="{self.H}">' + "".join(self.parts) +
                "</PrintSpace></Page></Layout></alto>\n")


def split_dots(text: str, box, line_h: float | None = None) -> list[list[dict]]:
    """dots-only text as one line of words sharing its box evenly (right to left); with line_h, the line is that
    high, centred in the box (a table cell's box is the whole cell, which would set the text far too big)."""
    ws = text.split()
    if not ws:
        return []
    x0, y0, x1, y1 = box
    if line_h and y1 - y0 > 1.3 * line_h:
        cy = (y0 + y1) / 2
        y0, y1 = cy - line_h / 2, cy + line_h / 2
    n = sum(len(w) for w in ws)
    out, x = [], x1
    for w in ws:
        wd = (x1 - x0) * len(w) / n
        out.append(dict(id="", text=w, box=[x - wd, y0, x, y1], conf=None))
        x -= wd
    return [out]


# ------------------------------------------------------------------------------------------------ JATS

def front_xml(stem: str, title_block: dict | None, title_text: str) -> str:
    src = MASTERS / f"{stem}.jats.xml"
    if not src.exists():
        t = f'<article-title id="{title_block["id"]}">{e(title_text)}</article-title>' if title_block else \
            "<article-title/>"
        return (f"<front><journal-meta><journal-title-group><journal-title/></journal-title-group></journal-meta>"
                f"<article-meta><title-group>{t}</title-group></article-meta></front>")
    root = etree.parse(str(src), etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)).getroot()
    fr = copy.deepcopy(root.find("front"))
    am = fr.find("article-meta")
    for tag in ("abstract", "trans-abstract", "kwd-group", "custom-meta-group"):
        for x in am.findall(tag):
            am.remove(x)
    for x in fr.iter():
        if isinstance(x.tag, str) and "id" in x.attrib and re.match(r"^p\d+", x.get("id") or ""):
            del x.attrib["id"]
    if title_block is not None:
        at = am.find("title-group/article-title")
        if at is not None:
            for c in list(at):
                at.remove(c)
            at.text = title_text
            at.set("id", title_block["id"])
    x = etree.tostring(fr, encoding="unicode")
    return re.sub(r' xmlns:(xlink|mml|xsi|ali)="[^"]*"', "", x)     # declared on <article>


def mathml_prefixed(mml: str) -> str:
    if not mml:
        return ""
    try:
        src = etree.fromstring(mml.encode())
    except Exception:
        return ""

    def cp(x):
        n = etree.Element(f"{{{MML_NS}}}{etree.QName(x).localname}", nsmap={"mml": MML_NS})
        for k, v in x.attrib.items():
            if not k.startswith("{"):
                n.set(k, v)
        n.text = x.text
        for c in x:
            if isinstance(c.tag, str):
                cc = cp(c)
                cc.tail = c.tail
                n.append(cc)
        return n
    root = cp(src)
    etree.cleanup_namespaces(root)
    return etree.tostring(root, encoding="unicode")


def build(pid: str, raw: bool = False) -> dict:
    meta = next(m for m in pages() if m["page_id"] == pid)
    pdir = OUT / "pages" / pid
    L = json.loads((pdir / "layout.json").read_text(encoding="utf-8"))
    F = {f["id"]: f for f in json.loads((pdir / "formulas.json").read_text(encoding="utf-8"))} \
        if (pdir / "formulas.json").exists() else {}
    C = None if raw else (json.loads((pdir / "corrections.json").read_text(encoding="utf-8"))
                          if (pdir / "corrections.json").exists() else None)
    rep = apply_corrections(L, C)
    md = pdir / ("master_raw" if raw else "master")
    if md.exists():
        shutil.rmtree(md)
    (md / "crops").mkdir(parents=True)
    for f in (pdir / "crops").glob("*.jpg"):
        shutil.copyfile(f, md / "crops" / f.name)
    W, H = L["width"], L["height"]
    A = Alto(pid, W, H)
    blocks = L["blocks"]
    by_id = {b["id"]: b for b in blocks}
    nb = max([int(b["id"][3:]) for b in blocks if re.match(r"^p1b\d+$", b["id"])] or [0])

    def new_id():
        nonlocal nb
        nb += 1
        return f"p1b{nb}"

    def lines_of(b):
        return [corrected_words(ln, rep) for ln in b.get("lines") or []]

    def text_of(b):
        if b["source"] == "dots":
            return b.get("text") or b["dots_text"]
        return " ".join(w["text"] for ln in lines_of(b) for w in ln)

    body, back_fn, printed = [], [], None
    in_sec = False
    list_open = None
    title_block = None
    first_page = meta["page"] == 1 or any(b["role"] == "title" for b in blocks) and meta["page"] <= 2
    stats = dict(corrected_words=sum(1 for v in rep.values() for _ in v), dots_strings=0)

    def close_list():
        nonlocal list_open
        if list_open is not None:
            body.append("</list>")
            list_open = None

    for b in blocks:
        role = b["role"]
        latin = b.get("latin", False)
        lang = ' xml:lang="en"' if latin else ""
        if role in ("header", "footer", "pagenum"):
            A.textblock(b["id"], ALTO_ROLE[role], lines_of(b), latin=latin)
            if role == "pagenum" and not printed:
                printed = text_of(b).strip(" -–|()[]")
            continue
        if role == "caption" and b.get("caption_of"):
            A.textblock(b["id"], "caption", lines_of(b), href=b["id"], latin=latin)
            continue                       # written inside its figure or table
        if role != "li":
            close_list()
        if role == "title" and first_page and title_block is None:
            title_block = b
            A.textblock(b["id"], "title", lines_of(b), href=b["id"], latin=latin)
            continue
        if role in ("title", "heading"):
            if in_sec:
                body.append("</sec>")
            body.append(f'<sec id="s{b["id"]}"><title id="{b["id"]}">{e(text_of(b))}</title>')
            in_sec = True
            A.textblock(b["id"], "sectionHeading", lines_of(b), href=b["id"], latin=latin)
            continue
        if role in ("p", "li", "fn", "caption"):
            dots = b["source"] == "dots"
            ct = ' content-type="vlm-text"' if dots else ""
            p = f'<p id="{b["id"]}"{lang}{ct}>{e(text_of(b))}</p>'
            if dots:
                stats["dots_strings"] += len(text_of(b).split())
                A.textblock(b["id"], ALTO_ROLE[role], split_dots(text_of(b), b["box"]), href=b["id"], dots=True,
                            latin=latin)
            else:
                A.textblock(b["id"], ALTO_ROLE[role], lines_of(b), href=b["id"], latin=latin)
            if role == "fn":
                back_fn.append(f'<fn id="fn-p1-{len(back_fn) + 1}">{p}</fn>')
            elif role == "li":
                if list_open is None:
                    list_open = b.get("list_type") or "bullet"
                    body.append(f'<list list-type="{list_open}">')
                lab = f"<label>{e(b['label'])}</label>" if b.get("label") else ""
                body.append(f"<list-item>{lab}{p}</list-item>")
            else:
                body.append(p)
            continue
        cap = by_id.get(b.get("caption") or "")
        capx = ""
        if cap is not None:
            capx = f'<caption><p id="{cap["id"]}">{e(text_of(cap))}</p></caption>'
        if role == "figure":
            A.raw(f'<Illustration ID="{b["id"]}" TYPE="figure" HPOS="{b["box"][0]:.0f}" VPOS="{b["box"][1]:.0f}" '
                  f'WIDTH="{b["box"][2] - b["box"][0]:.0f}" HEIGHT="{b["box"][3] - b["box"][1]:.0f}" '
                  f'xlink:href="{pid}.jats.xml#{b["id"]}" xlink:type="simple"/>')
            if b["words"]:
                A.textblock(new_id(), "pictureText", lines_of(b))
            body.append(f'<fig id="{b["id"]}">{capx}<graphic xlink:href="crops/{b["id"]}.jpg"/></fig>')
            continue
        if role == "formula":
            f = F.get(b["id"], {})
            tex = f.get("tex") if f else (b.get("tex_dots") or "")
            mml = mathml_prefixed(f.get("mathml") or "")
            lab = f"<label>{e(f.get('label'))}</label>" if f.get("label") else ""
            A.raw(f'<Illustration ID="{b["id"]}" TYPE="formula" HPOS="{b["box"][0]:.0f}" VPOS="{b["box"][1]:.0f}" '
                  f'WIDTH="{b["box"][2] - b["box"][0]:.0f}" HEIGHT="{b["box"][3] - b["box"][1]:.0f}" '
                  f'xlink:href="{pid}.jats.xml#{b["id"]}" xlink:type="simple"/>')
            if b["words"]:
                A.textblock(new_id(), "formulaInk", lines_of(b))
            tm = f"<tex-math><![CDATA[{tex}]]></tex-math>" if tex else ""
            body.append(f'<disp-formula id="{b["id"]}">{lab}<alternatives>{mml}{tm}'
                        f'<graphic xlink:href="crops/{b["id"]}.jpg" specific-use="scan-crop"/></alternatives>'
                        f'</disp-formula>')
            continue
        if role == "table":
            cells_x = [f'<ComposedBlock ID="{b["id"]}" TYPE="table" HPOS="{b["box"][0]:.0f}" VPOS="{b["box"][1]:.0f}" '
                       f'WIDTH="{b["box"][2] - b["box"][0]:.0f}" HEIGHT="{b["box"][3] - b["box"][1]:.0f}" '
                       f'xlink:href="{pid}.jats.xml#{b["id"]}" xlink:type="simple">']
            A.raw(cells_x[0])
            rows_x = {"head": [], "body": []}
            hs = sorted(w["box"][3] - w["box"][1] for r in b["rows"] for c in r["cells"] for w in c.get("words") or [])
            tlh = hs[len(hs) // 2] if hs else None
            for ri, r in enumerate(b["rows"]):
                cs = []
                for ci, c in enumerate(r["cells"]):
                    cid = f'{b["id"]}c{ri:02d}{ci:02d}'
                    tag = "th" if c.get("th") else "td"
                    sp = (f' colspan="{c["colspan"]}"' if c["colspan"] > 1 else "") + \
                         (f' rowspan="{c["rowspan"]}"' if c["rowspan"] > 1 else "")
                    if c.get("words"):
                        from parse import order_lines
                        lns = [corrected_words(ln, rep) for ln in order_lines(c["words"])]
                        txt = " ".join(w["text"] for ln in lns for w in ln)
                        A.textblock(cid, "tableCell", lns, href=cid)
                        cs.append(f'<{tag} id="{cid}"{sp}>{e(txt)}</{tag}>')
                    elif c.get("text"):
                        stats["dots_strings"] += len(c["text"].split())
                        A.textblock(cid, "tableCell", split_dots(c["text"], c["box"], tlh), href=cid, dots=True)
                        cs.append(f'<{tag} id="{cid}"{sp} content-type="vlm-text">{e(c["text"])}</{tag}>')
                    else:
                        cs.append(f'<{tag} id="{cid}"{sp}/>')
                rows_x["head" if r.get("head") else "body"].append("<tr>" + "".join(cs) + "</tr>")
            A.raw("</ComposedBlock>")
            t = "<table>" + (f"<thead>{''.join(rows_x['head'])}</thead>" if rows_x["head"] else "") + \
                f"<tbody>{''.join(rows_x['body'])}</tbody></table>"
            body.append(f'<table-wrap id="{b["id"]}">{capx}<alternatives><graphic xlink:href="crops/{b["id"]}.jpg" '
                        f'specific-use="scan-crop"/>{t}</alternatives></table-wrap>')
            continue
    close_list()
    if in_sec:
        body.append("</sec>")
    title_text = text_of(title_block) if title_block else ""
    fr = front_xml(L["stem"], title_block, title_text)
    back = f"<back><fn-group>{''.join(back_fn)}</fn-group></back>" if back_fn else ""
    jats = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal '
            'Archiving and Interchange DTD with MathML3 v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">\n'
            '<article xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:mml="http://www.w3.org/1998/Math/MathML" '
            'article-type="research-article" dtd-version="1.4" xml:lang="ar"><processing-meta tagset-family="jats" '
            'base-tagset="archiving" table-model="xhtml" math-representation="mathml tex" mathml-version="3.0"/>'
            + fr + "<body>" + "".join(body) + "</body>" + back + "</article>\n")
    (md / f"{pid}.jats.xml").write_text(jats, encoding="utf-8")
    (md / f"{pid}.alto.xml").write_text(A.xml(printed), encoding="utf-8")
    # the scan as a one-page PDF (300 dpi): colour where the faithful PDF matched, else the grey page
    import pymupdf
    img = pdir / "page_colour.jpg"
    if not img.exists():
        from common import colour_page
        import cv2
        c = colour_page(pid, L["stem"], L["page"])
        if c is not None:
            cv2.imwrite(str(img), c, [cv2.IMWRITE_JPEG_QUALITY, 85])
    src = img if img.exists() else (Path("/home/yassine/inkscript/experiments/34_yardstick/out/gold") / f"{pid}.jpg")
    doc = pymupdf.open()
    pg = doc.new_page(width=W * 72 / DPI, height=H * 72 / DPI)
    pg.insert_image(pg.rect, filename=str(src))
    doc.save(str(md / f"{pid}.pdf"))
    doc.close()
    from inkscript.enrich.schemas import validate_alto, validate_jats
    ja, al = validate_jats(md / f"{pid}.jats.xml"), validate_alto(md / f"{pid}.alto.xml")
    stats.update(jats_errors=ja[:5], alto_errors=al[:5], alto_words=A.nw)
    (md / "master_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    return stats


def main(argv):
    raw = "--raw" in argv
    force = "--force" in argv
    want = [a for a in argv if not a.startswith("--")]
    for meta in pages():
        pid = meta["page_id"]
        if want and pid not in want:
            continue
        md = OUT / "pages" / pid / ("master_raw" if raw else "master")
        if (md / "master_stats.json").exists() and not force:
            continue
        if not (OUT / "pages" / pid / "layout.json").exists():
            continue
        if not raw and not (OUT / "pages" / pid / "corrections.json").exists():
            continue                      # the corrected master waits for its corrections
        s = build(pid, raw)
        print(pid, "words", s["alto_words"], "corrected", s["corrected_words"], "dots", s["dots_strings"],
              "JATS", "ok" if not s["jats_errors"] else s["jats_errors"][:2],
              "ALTO", "ok" if not s["alto_errors"] else s["alto_errors"][:2], flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
