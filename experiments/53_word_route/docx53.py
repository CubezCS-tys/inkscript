"""Experiment 53: read a publisher's Word file (.docx, converted from .doc by LibreOffice) into blocks (no model).

    doc = read_docx(path)   -> dict(blocks=[...], footnotes={id: [para]}, header=[...], page_start=int|None,
                                    page_size=(w, h) twips, body_size=half-points)

A block is one of
    {"kind": "p",     "runs": [run], "text": str, "jc", "size", "bold", "hfont", "num": (numId, ilvl) | None,
                      "label": str (the list number Word draws), "outline": int | None, "style": str,
                      "textbox": bool, "images": [rel ids]}
    {"kind": "table", "rows": [[cell]], "header_rows": int}     cell = {"paras": [para], "colspan", "rowspan"}
A run is {"t": text, "b", "i", "sup", "sub"} or {"fn": footnote id, "mark": custom mark | None} or
{"img": rel id}.  Text boxes (mc:Fallback copies dropped) become blocks of their own, before their anchor paragraph.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"w": W, "mc": MC, "m": M, "r": R, "a": A}


def q(t, ns=W):
    return f"{{{ns}}}{t}"


def on(el) -> bool:
    """A w:b / w:i style toggle: present and not switched off."""
    return el is not None and el.get(q("val"), "true") not in ("0", "false", "off")


def part(z, name):
    try:
        return etree.fromstring(z.read(name))
    except KeyError:
        return None


# ------------------------------------------------------------------------------------------------ numbering

ABJAD = "أبجدهوزحطيكلمنسعفصقرشتثخذضظغ"
ALPHA = "أبتثجحخدذرزسشصضطظعغفقكلمنهوي"


def roman(n: int) -> str:
    out = ""
    for v, s in ((1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
                 (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= v:
            out += s
            n -= v
    return out


def fmt_num(n: int, f: str) -> str:
    if f in ("bullet", "none"):
        return ""
    if f == "arabicAbjad":
        return ABJAD[(n - 1) % len(ABJAD)]
    if f == "arabicAlpha":
        return ALPHA[(n - 1) % len(ALPHA)]
    if f == "hindiNumbers":
        return str(n).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    if f == "lowerLetter":
        return chr(96 + (n - 1) % 26 + 1)
    if f == "upperLetter":
        return chr(64 + (n - 1) % 26 + 1)
    if f == "lowerRoman":
        return roman(n)
    if f == "upperRoman":
        return roman(n).upper()
    return str(n)


class Numbering:
    """The label Word draws before a numbered paragraph (numbering.xml: num -> abstractNum -> lvl)."""

    def __init__(self, x):
        self.abs, self.num, self.count = {}, {}, {}
        if x is None:
            return
        for an in x.iter(q("abstractNum")):
            lv = {}
            for l in an.findall("w:lvl", NS):
                il = int(l.get(q("ilvl")))
                g = lambda t, d: (l.find(f"w:{t}", NS).get(q("val")) if l.find(f"w:{t}", NS) is not None else d)
                lv[il] = dict(start=int(g("start", "1")), fmt=g("numFmt", "decimal"), text=g("lvlText", "%1."))
            self.abs[an.get(q("abstractNumId"))] = lv
        for n in x.iter(q("num")):
            a = n.find("w:abstractNumId", NS)
            ov = {}
            for o in n.findall("w:lvlOverride", NS):
                s = o.find("w:startOverride", NS)
                if s is not None:
                    ov[int(o.get(q("ilvl")))] = int(s.get(q("val")))
            self.num[n.get(q("numId"))] = (a.get(q("val")) if a is not None else None, ov)

    def label(self, num_id: str, ilvl: int) -> tuple[str, str]:
        """(label, numFmt) for the next paragraph of this list at this level."""
        an, ov = self.num.get(num_id, (None, {}))
        lv = self.abs.get(an, {})
        if not lv or num_id == "0":
            return "", "none"
        c = self.count.setdefault(num_id, {})
        L = lv.get(ilvl, dict(start=1, fmt="decimal", text="%1."))
        c[ilvl] = c.get(ilvl, ov.get(ilvl, L["start"]) - 1) + 1
        for k in list(c):
            if k > ilvl:
                del c[k]
        if L["fmt"] == "bullet":
            return "•", "bullet"

        def sub(m):
            k = int(m.group(1)) - 1
            L2 = lv.get(k, L)
            return fmt_num(c.get(k, L2["start"]), L2["fmt"])
        return re.sub(r"%(\d)", sub, L["text"]).strip(), L["fmt"]


# ------------------------------------------------------------------------------------------------ styles

class Styles:
    def __init__(self, x):
        self.name, self.outline, self.bold, self.based, self.size = {}, {}, {}, {}, {}
        self.default_size = None
        if x is None:
            return
        d = x.find("w:docDefaults/w:rPrDefault/w:rPr/w:szCs", NS)
        if d is not None:
            self.default_size = int(d.get(q("val")))
        for s in x.iter(q("style")):
            sid = s.get(q("styleId"))
            n = s.find("w:name", NS)
            self.name[sid] = n.get(q("val")) if n is not None else sid
            ol = s.find("w:pPr/w:outlineLvl", NS)
            if ol is not None and int(ol.get(q("val"))) < 9:
                self.outline[sid] = int(ol.get(q("val")))
            b = s.find("w:rPr/w:bCs", NS)
            if b is None:
                b = s.find("w:rPr/w:b", NS)
            if b is not None:
                self.bold[sid] = on(b)
            sz = s.find("w:rPr/w:szCs", NS)
            if sz is not None:
                self.size[sid] = int(sz.get(q("val")))
            bo = s.find("w:basedOn", NS)
            if bo is not None:
                self.based[sid] = bo.get(q("val"))

    def get(self, d, sid):
        seen = 0
        while sid and seen < 10:
            if sid in d:
                return d[sid]
            sid = self.based.get(sid)
            seen += 1
        return None


# ------------------------------------------------------------------------------------------------ paragraphs

SKIP = {q("txbxContent"), q("Fallback", MC), q("instrText"), q("delText")}


def walk_runs(p, st: Styles, sid, out_boxes):
    """The paragraph's runs in order (text boxes collected into out_boxes, not into the runs)."""
    runs = []
    style_b = bool(st.get(st.bold, sid))

    def rprops(r):
        rp = r.find("w:rPr", NS)
        if rp is None:
            return style_b, False, None, None, None
        b = rp.find("w:bCs", NS)
        if b is None:
            b = rp.find("w:b", NS)
        bold = on(b) if b is not None else style_b
        it = rp.find("w:iCs", NS)
        if it is None:
            it = rp.find("w:i", NS)
        va = rp.find("w:vertAlign", NS)
        va = va.get(q("val")) if va is not None else None
        f = rp.find("w:rFonts", NS)
        font = f.get(q("cs")) if f is not None else None
        sz = rp.find("w:szCs", NS)
        sz = int(sz.get(q("val"))) if sz is not None else None
        return bold, on(it), va, font, sz

    def visit(el):
        for c in el:
            if not isinstance(c.tag, str):
                continue
            if c.tag == q("txbxContent"):
                out_boxes.append(c)
                continue
            if c.tag in SKIP:
                continue
            if c.tag == q("r"):
                bold, it, va, font, sz = rprops(c)
                custom = None
                for k in c:
                    if k.tag == q("t"):
                        runs.append(dict(t=k.text or "", b=bold, i=it, sup=va == "superscript", sub=va == "subscript",
                                         font=font, size=sz))
                    elif k.tag in (q("tab"),):
                        runs.append(dict(t="\t", b=bold, i=False, sup=False, sub=False, font=font, size=sz))
                    elif k.tag in (q("br"), q("cr")):
                        runs.append(dict(t="\n" if k.get(q("type")) not in ("page", "column") else " ", b=bold,
                                         i=False, sup=False, sub=False, font=font, size=sz, brk=k.get(q("type"))))
                    elif k.tag in (q("footnoteReference"), q("endnoteReference")):
                        custom = k.get(q("customMarkFollows")) in ("1", "true")
                        runs.append(dict(fn=("en" if k.tag == q("endnoteReference") else "fn") + k.get(q("id")),
                                         custom=custom, mark=None))
                    elif k.tag in (q("drawing"), q("pict"), q("object")):
                        boxes = list(k.iter(q("txbxContent")))
                        if boxes:
                            for bx in boxes:
                                if not any(a.tag == q("Fallback", MC) for a in bx.iterancestors()):
                                    out_boxes.append(bx)
                        else:
                            blip = next(k.iter(q("blip", A)), None)
                            rid = blip.get(q("embed", R)) if blip is not None else None
                            if rid is None:
                                im = next((e for e in k.iter() if isinstance(e.tag, str) and e.get(q("id", R))), None)
                                rid = im.get(q("id", R)) if im is not None else None
                            runs.append(dict(img=rid))
                    elif k.tag == q("AlternateContent", MC):
                        visit(k)
                    elif k.tag == q("Choice", MC):
                        visit(k)
                    elif k.tag == q("sym"):
                        try:
                            cp = int(k.get(q("char")), 16)
                            ch = chr(cp - 0xF000 if cp >= 0xF000 else cp)
                        except (TypeError, ValueError):
                            ch = ""
                        runs.append(dict(t=ch, b=bold, i=False, sup=va == "superscript", sub=False, font=font,
                                         size=sz, sym=True))
                # a custom footnote mark: the text of this run after the reference is the mark
                if custom:
                    fnr = [x for x in runs if "fn" in x][-1]
                    tail = [x for x in runs[runs.index(fnr) + 1:] if "t" in x]
                    if tail:
                        fnr["mark"] = "".join(x["t"] for x in tail)
                        for x in tail:
                            runs.remove(x)
            elif c.tag in (q("oMath", M), q("oMathPara", M)):
                runs.append(dict(t="".join(t.text or "" for t in c.iter(q("t", M))), b=False, i=False, sup=False,
                                 sub=False, font=None, size=None, math=True))
            else:
                visit(c)
    visit(p)
    return runs


def para(p, st: Styles, numbering: Numbering, out_boxes, in_table=False):
    pp = p.find("w:pPr", NS)
    sid = None
    jc = None
    num = None
    outline = None
    bidi = False
    if pp is not None:
        s = pp.find("w:pStyle", NS)
        sid = s.get(q("val")) if s is not None else None
        j = pp.find("w:jc", NS)
        jc = j.get(q("val")) if j is not None else None
        n = pp.find("w:numPr", NS)
        if n is not None:
            ni, il = n.find("w:numId", NS), n.find("w:ilvl", NS)
            if ni is not None:
                num = (ni.get(q("val")), int(il.get(q("val"))) if il is not None else 0)
        o = pp.find("w:outlineLvl", NS)
        if o is not None and int(o.get(q("val"))) < 9:
            outline = int(o.get(q("val")))
        bidi = on(pp.find("w:bidi", NS)) if pp.find("w:bidi", NS) is not None else False
    if outline is None:
        outline = st.get(st.outline, sid)
    runs = walk_runs(p, st, sid, out_boxes)
    text = "".join(r.get("t", "") for r in runs)
    label, lfmt = ("", None)
    if num and text.strip():
        label, lfmt = numbering.label(*num)
    tr = [r for r in runs if r.get("t", "").strip()]
    chars = sum(len(r["t"].strip()) for r in tr) or 1
    bold_share = sum(len(r["t"].strip()) for r in tr if r["b"]) / chars
    fonts = [r.get("font") or "" for r in tr]
    hfont = sum(len(r["t"].strip()) for r in tr if re.search(r"bold|heading|black|thuluth", r.get("font") or "", re.I)) / chars
    sizes = [r.get("size") for r in tr if r.get("size")]
    size = max(set(sizes), key=sizes.count) if sizes else st.get(st.size, sid) or st.default_size
    return dict(kind="p", runs=runs, text=text, jc=jc, bidi=bidi, num=num, label=label, lfmt=lfmt, outline=outline,
                style=st.name.get(sid, sid or "Normal"), bold=bold_share, hfont=hfont, size=size,
                images=[r["img"] for r in runs if "img" in r], in_table=in_table, fonts=fonts)


def table(tbl, st, numbering, boxes):
    rows = []
    header_rows = 0
    vm_open = {}                 # column index -> the cell a vMerge continues
    for tr in tbl.findall("w:tr", NS):
        if tr.find("w:trPr/w:tblHeader", NS) is not None and on(tr.find("w:trPr/w:tblHeader", NS)):
            header_rows += 1
        row = []
        col = 0
        for tc in tr.findall("w:tc", NS):
            pr = tc.find("w:tcPr", NS)
            span = 1
            vm = None
            if pr is not None:
                g = pr.find("w:gridSpan", NS)
                span = int(g.get(q("val"))) if g is not None else 1
                v = pr.find("w:vMerge", NS)
                if v is not None:
                    vm = v.get(q("val"), "continue")
            paras = []
            for el in tc:
                if el.tag == q("p"):
                    paras.append(para(el, st, numbering, boxes, in_table=True))
                elif el.tag == q("tbl"):      # nested table: its text as paragraphs
                    for p in el.iter(q("p")):
                        paras.append(para(p, st, numbering, boxes, in_table=True))
            if vm == "continue" and col in vm_open:
                vm_open[col]["rowspan"] += 1
            else:
                cell = dict(paras=paras, colspan=span, rowspan=1)
                row.append(cell)
                if vm == "restart":
                    vm_open[col] = cell
                else:
                    vm_open.pop(col, None)
            col += span
        rows.append(row)
    return dict(kind="table", rows=rows, header_rows=header_rows)


def read_docx(path: Path) -> dict:
    z = zipfile.ZipFile(path)
    doc = part(z, "word/document.xml")
    st = Styles(part(z, "word/styles.xml"))
    numbering = Numbering(part(z, "word/numbering.xml"))
    rels = {}
    rx = part(z, "word/_rels/document.xml.rels")
    if rx is not None:
        for r in rx:
            rels[r.get("Id")] = r.get("Target")
    body = doc.find("w:body", NS)
    for fb in list(body.iter(q("Fallback", MC))):
        fb.getparent().remove(fb)
    blocks = []

    def add_boxes(boxes):
        for bx in boxes:
            for p in bx.iter(q("p")):
                b = para(p, st, numbering, [])
                b["textbox"] = True
                if b["text"].strip():
                    blocks.append(b)

    for el in body:
        if el.tag == q("p"):
            boxes = []
            b = para(el, st, numbering, boxes)
            add_boxes(boxes)
            b["textbox"] = False
            if b["text"].strip() or b["images"]:
                blocks.append(b)
        elif el.tag == q("tbl"):
            boxes = []
            blocks.append(table(el, st, numbering, boxes))
            add_boxes(boxes)
        elif el.tag == q("sdt"):
            for p in el.iter(q("p")):
                boxes = []
                b = para(p, st, numbering, boxes)
                add_boxes(boxes)
                if b["text"].strip():
                    blocks.append(b)
    fns = {}
    for nm, tag, pre in (("word/footnotes.xml", "footnote", "fn"), ("word/endnotes.xml", "endnote", "en")):
        x = part(z, nm)
        if x is None:
            continue
        for f in x.iter(q(tag)):
            if f.get(q("type")) not in (None, "normal"):
                continue
            ps = [para(p, st, numbering, []) for p in f.iter(q("p"))]
            fns[pre + f.get(q("id"))] = [p for p in ps if p["text"].strip()]
    hdr = []
    for n in sorted(z.namelist()):
        if re.match(r"word/header\d*\.xml$", n):
            x = part(z, n)
            t = " ".join(" ".join("".join(t.text or "" for t in p.iter(q("t"))).split()) for p in x.iter(q("p")))
            if t.strip():
                hdr.append(t.strip())
    sp = body.find("w:sectPr", NS)
    if sp is None:
        sp = next(body.iter(q("sectPr")), None)
    start = None
    size = None
    if sp is not None:
        pn = sp.find("w:pgNumType", NS)
        if pn is not None and pn.get(q("start")):
            start = int(pn.get(q("start")))
        pg = sp.find("w:pgSz", NS)
        if pg is not None:
            size = (int(pg.get(q("w"))), int(pg.get(q("h"))))
    # the body text size: the commonest size by characters
    cnt = {}
    for b in blocks:
        if b["kind"] == "p":
            for r in b["runs"]:
                if r.get("t", "").strip() and r.get("size"):
                    cnt[r["size"]] = cnt.get(r["size"], 0) + len(r["t"])
    body_size = max(cnt, key=cnt.get) if cnt else 28
    media = {k: v for k, v in rels.items() if v and v.startswith("media/")}
    return dict(blocks=blocks, footnotes=fns, header=hdr, page_start=start, page_size=size, body_size=body_size,
                media=media, zip=z)
