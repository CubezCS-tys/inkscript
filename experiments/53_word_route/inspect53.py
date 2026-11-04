"""Experiment 53: what the Word files hold (no model calls).

For each out/docx/<stem>.docx (converted from the publisher's .doc by LibreOffice): paragraph count, styles used,
outline levels, numbered paragraphs, bold-only paragraphs, footnotes / endnotes and their calls, tables, images,
text boxes, fields, bidi share, complex-script fonts, header text.  -> out/inspect.json, a summary on stdout.

    .venv/bin/python experiments/53_word_route/inspect53.py
"""
from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}


def q(t):
    return f"{{{W}}}{t}"


def part(z, name):
    try:
        return etree.fromstring(z.read(name))
    except KeyError:
        return None


def ptext(p):
    return "".join(t.text or "" for t in p.iter(q("t")))


def inspect(path: Path) -> dict:
    z = zipfile.ZipFile(path)
    doc = part(z, "word/document.xml")
    styles = part(z, "word/styles.xml")
    sname = {}
    s_outline = {}
    if styles is not None:
        for s in styles.iter(q("style")):
            sid = s.get(q("styleId"))
            n = s.find("w:name", NS)
            sname[sid] = n.get(q("val")) if n is not None else sid
            ol = s.find("w:pPr/w:outlineLvl", NS)
            if ol is not None:
                s_outline[sid] = int(ol.get(q("val")))
    body = doc.find("w:body", NS)
    st = Counter()
    used = Counter()
    fonts = Counter()
    paras = [p for p in body.iter(q("p"))]
    top = [p for p in body if p.tag == q("p")]
    st["paragraphs"] = len(paras)
    st["paragraphs_nonempty"] = sum(1 for p in paras if ptext(p).strip())
    st["top_paragraphs_nonempty"] = sum(1 for p in top if ptext(p).strip())
    for p in paras:
        if not ptext(p).strip():
            continue
        ps = p.find("w:pPr/w:pStyle", NS)
        sid = ps.get(q("val")) if ps is not None else "Normal"
        used[sname.get(sid, sid)] += 1
        if p.find("w:pPr/w:outlineLvl", NS) is not None or sid in s_outline:
            st["outline_paragraphs"] += 1
        if p.find("w:pPr/w:numPr", NS) is not None:
            st["numbered_paragraphs"] += 1
        if p.find("w:pPr/w:bidi", NS) is not None:
            st["bidi_paragraphs"] += 1
        runs = [r for r in p.iter(q("r")) if "".join(t.text or "" for t in r.iter(q("t"))).strip()]
        if runs and all(r.find("w:rPr/w:b", NS) is not None or r.find("w:rPr/w:bCs", NS) is not None for r in runs):
            st["bold_only_paragraphs"] += 1
        for r in runs:
            f = r.find("w:rPr/w:rFonts", NS)
            if f is not None and f.get(q("cs")):
                fonts[f.get(q("cs"))] += len("".join(t.text or "" for t in r.iter(q("t"))))
    st["footnote_calls"] = len(list(body.iter(q("footnoteReference"))))
    st["endnote_calls"] = len(list(body.iter(q("endnoteReference"))))
    for nm, tag in (("word/footnotes.xml", "footnote"), ("word/endnotes.xml", "endnote")):
        x = part(z, nm)
        if x is not None:
            st[tag + "s"] = sum(1 for f in x.iter(q(tag)) if f.get(q("type")) in (None, "normal"))
    st["tables"] = sum(1 for t in body.iter(q("tbl")) if t.getparent().tag != q("tc"))
    st["tables_nested"] = sum(1 for t in body.iter(q("tbl")) if t.getparent().tag == q("tc"))
    st["table_paragraphs"] = sum(1 for p in paras if any(a.tag == q("tc") for a in p.iterancestors()))
    st["drawings"] = len(list(body.iter(q("drawing")))) + len(list(body.iter(q("pict"))))
    st["textboxes"] = len(list(body.iter(q("txbxContent"))))
    st["textbox_paragraphs"] = sum(1 for p in paras if any(a.tag == q("txbxContent") for a in p.iterancestors()))
    st["math"] = len(list(body.iter("{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath")))
    st["objects"] = len(list(body.iter(q("object"))))
    st["fields"] = len(list(body.iter(q("fldChar")))) // 2 + len(list(body.iter(q("fldSimple"))))
    st["sections"] = len(list(body.iter(q("sectPr"))))
    st["chars"] = sum(len(ptext(p)) for p in paras)
    hdr = []
    for n in z.namelist():
        if n.startswith("word/header") and n.endswith(".xml"):
            x = part(z, n)
            hdr.append(" ".join(ptext(p) for p in x.iter(q("p")) if ptext(p).strip()))
    return dict(stem=path.stem, stats=dict(st), styles=dict(used.most_common()), fonts=dict(fonts.most_common(6)),
                headers=hdr)


def main():
    res = []
    for f in sorted((OUT / "docx").glob("*.docx")):
        try:
            res.append(inspect(f))
        except Exception as e:  # noqa: BLE001
            res.append(dict(stem=f.stem, error=repr(e)))
    (OUT / "inspect.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = Counter()
    has = Counter()
    sty = Counter()
    fon = Counter()
    for r in res:
        if "error" in r:
            print("ERROR", r["stem"], r["error"])
            continue
        for k, v in r["stats"].items():
            tot[k] += v
            has[k] += 1 if v else 0
        for k, v in r["styles"].items():
            sty[k] += v
        for k, v in r["fonts"].items():
            fon[k] += v
    print(f"{len(res)} files")
    for k in sorted(tot):
        print(f"  {k:<26} total {tot[k]:>8}   files with any {has[k]:>4}")
    print("styles:", sty.most_common(25))
    print("cs fonts (chars):", fon.most_common(12))


if __name__ == "__main__":
    sys.exit(main())
