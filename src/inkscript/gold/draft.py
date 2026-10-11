"""A draft gold page from Azure's reading: the starting point the owner corrects (experiment 34).

    doc = document.load(azure_json)                 # once per document (px at 300 dpi)
    info = structure.analyse(doc)                   # paragraph kinds (title, footnote, heading, furniture...)
    g, jpg = draft_page(doc, info, scan_pdf, page, meta)

Lines come in Azure's reading order (the order of their first word in Azure's content, which the build keeps:
99.95% of lines in order at scale); regions are Azure's paragraphs with the build's kinds; each region gets a
column (by the x-centre of its box, clustered over the page's text regions). Text = Azure's line, Persian code
points folded to Arabic as the build folds them; Azure's words with boxes and confidence are kept for the editor.
"""
from __future__ import annotations

import statistics

import numpy as np

from .format import SCHEMA, page_id

KIND_OF_ROLE = {"title": ("title", "title"), "rubric": ("heading", "heading"), "author": ("title", "title"),
                "sectionHeading": ("heading", "heading"), "footnote": ("footnote", "footnote"),
                "pageHeader": ("furniture", "furniture"), "pageFooter": ("furniture", "furniture"),
                "pageNumber": ("furniture", "furniture")}


def render(scan_pdf, page: int, dpi: int = 300) -> tuple[bytes, int, int]:
    """The page as a grey JPEG at dpi (what Azure saw, upright), with its pixel size."""
    import cv2
    import fitz
    d = fitz.open(scan_pdf)
    pg = d[page - 1]
    pix = pg.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    d.close()
    return buf.tobytes(), pix.width, pix.height


def _columns(boxes: list[list[float]], width: float) -> list[int]:
    """Column number (1 = rightmost, as an Arabic page is read) per box: boxes narrower than 60% of the text width
    are grouped by x-centre (gaps over 8% of the page width split columns); wide boxes span, column 0."""
    if not boxes:
        return []
    x0 = min(b[0] for b in boxes)
    x1 = max(b[2] for b in boxes)
    tw = max(1.0, x1 - x0)
    narrow = [(i, (b[0] + b[2]) / 2) for i, b in enumerate(boxes) if (b[2] - b[0]) < 0.6 * tw]
    col = [0] * len(boxes)
    if len(narrow) < 2:
        return [1] * len(boxes)
    narrow.sort(key=lambda t: -t[1])
    c, last = 1, narrow[0][1]
    for i, xc in narrow:
        if last - xc > 0.08 * width:
            c += 1
        col[i] = c
        last = xc
    sizes = {k: sum(1 for i, _ in narrow if col[i] == k) for k in range(1, c + 1)}
    tall = sum(boxes[i][3] - boxes[i][1] for i, _ in narrow)
    th = max(1.0, max(b[3] for b in boxes) - min(b[1] for b in boxes))
    if c == 1 or sum(1 for v in sizes.values() if v >= 2) < 2 or tall < 0.3 * th:
        return [1] * len(boxes)                 # one column (short footnote pieces are not columns)
    return col


def draft_page(doc: dict, info: dict | None, page: int, meta: dict, image: dict, dpi: int = 300) -> dict:
    W = doc["words"]
    s = dpi / 300.0
    sc = lambda b: [round(v * s, 1) for v in b]
    kinds = (info or {}).get("kinds") or [p.get("kind") for p in doc["paras"]]
    pg = doc["pages"][page]
    lines = []
    for li, members in enumerate(doc["lines"].get(page, [])):
        ws = [W[k] for k in members]
        if not ws:
            continue
        ws_sorted = sorted(ws, key=lambda w: w["off"])
        box = [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
               max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)]
        paras = [w["para"] for w in ws if w["para"] is not None]
        para = statistics.mode(paras) if paras else None
        text = " ".join(w["out"] for w in ws_sorted)
        lines.append(dict(_off=ws_sorted[0]["off"], _para=para, box=sc(box), text=text,
                          words=[dict(text=w["out"], box=sc(w["box"]), conf=w["conf"]) for w in ws_sorted],
                          hw=max(w.get("hw", 0.0) for w in ws)))
    lines.sort(key=lambda d: d["_off"])
    # regions: one per paragraph met on this page, in the order first met
    reg_of, regions = {}, []
    for ln in lines:
        p = ln["_para"]
        if p not in reg_of:
            reg_of[p] = f"r{len(regions) + 1:02d}"
            role = kinds[p] if p is not None and p < len(kinds) else None
            rtype, lkind = KIND_OF_ROLE.get(role, ("text", "text"))
            regions.append(dict(id=reg_of[p], type=rtype, box=None, column=1, article=None,
                                order=len(regions) + 1, _kind=lkind, _role=role))
    rby = {r["id"]: r for r in regions}
    for i, ln in enumerate(lines):
        r = rby[reg_of[ln["_para"]]]
        b = ln["box"]
        r["box"] = b[:] if r["box"] is None else [min(r["box"][0], b[0]), min(r["box"][1], b[1]),
                                                  max(r["box"][2], b[2]), max(r["box"][3], b[3])]
        if ln["hw"] >= 0.5 and r["type"] == "text":
            r["type"] = "handwriting"
        ln.update(id=f"l{i + 1:03d}", region=r["id"], kind=r["_kind"], lang=_lang(ln["text"]), status="todo",
                  draft=dict(azure=ln["text"]), disagree=[], flags=[])
        if any((w["conf"] or 0) < 0.6 for w in ln["words"]):     # experiment 27: under 0.6 is always doubtful
            ln["flags"].append("low-conf")
    text_regions = [r for r in regions if r["type"] not in ("furniture",)]
    for r, c in zip(text_regions, _columns([r["box"] for r in text_regions], image["width"])):
        r["column"] = c
    for r in regions:
        r.pop("_kind")
        r.pop("_role")
        if r["type"] == "furniture":
            r["column"] = 0
    for ln in lines:
        for k in ("_off", "_para", "hw"):
            ln.pop(k)
    pid = page_id(meta["stem"], page)
    return dict(schema=SCHEMA, page_id=pid, stem=meta["stem"], page=page, split=meta.get("split", "test"),
                kinds=meta.get("kinds", []), primary=meta.get("primary", ""), decade=meta.get("decade", ""),
                year=meta.get("year", ""), journal=meta.get("journal", ""), field=meta.get("field", ""),
                image=dict(file=f"{pid}.jpg", dpi=dpi, width=image["width"], height=image["height"],
                           angle=pg.get("angle", 0.0)),
                status="todo", seconds=0.0, checked=dict(by="", at=""), regions=regions, lines=lines,
                order=[ln["id"] for ln in lines], tables=[], equations=[], articles=[], notes="")


def _lang(t: str) -> str:
    ar = sum(1 for c in t if "؀" <= c <= "ۿ" or "ﭐ" <= c <= "ﻼ")
    la = sum(1 for c in t if c.isascii() and c.isalpha())
    if la and ar:
        return "mixed" if min(la, ar) > 0.15 * (la + ar) else ("la" if la > ar else "ar")
    return "la" if la else "ar"


def write_pages(azure_json, scan_pdf, pages: list[int], gold_dir, meta: dict, dpi: int = 300,
                analyse: bool = True) -> list[str]:
    """Draft pages of one document into gold_dir (<page_id>.json + .jpg); an existing page file is never
    overwritten (it may hold corrections). meta["pages"][p] adds per-page fields (kinds, primary...).
    Returns the page ids written."""
    from pathlib import Path

    from ..enrich import document, structure
    from .format import save
    gold_dir = Path(gold_dir)
    gold_dir.mkdir(parents=True, exist_ok=True)
    doc = document.load(Path(azure_json))
    info = structure.analyse(doc) if analyse else None
    out = []
    for p in pages:
        pm = dict(meta, **(meta.get("pages", {}).get(p, {})))
        pid = page_id(meta["stem"], p)
        if (gold_dir / f"{pid}.json").exists():
            continue
        jpg, w, h = render(scan_pdf, p, dpi)
        (gold_dir / f"{pid}.jpg").write_bytes(jpg)
        g = draft_page(doc, info, p, pm, dict(width=w, height=h), dpi)
        save(gold_dir / f"{pid}.json", g, history=False)
        out.append(pid)
    return out
