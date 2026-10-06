"""Write a corrected reading back into a finished PDF without rebuilding it.

A correction names a word the way the review list does — page and Azure box
in scan pixels — and gives the text it should carry. The glyph whose declared
box overlaps that box most gets a new ToUnicode entry, stored the way its
line is stored (the inverse of Chrome's reading, right-to-left or
left-to-right by the line's majority), and the change is logged beside the
PDF in `<stem>.corrections.json`. The ink is never touched.

Since experiment 27 (2026-10-06): a correction already carried is not written again (idempotent), and nothing
is saved when nothing changed; a correction that names its ALTO word (`id`) marks every placement of that word in
shapes.json; a correction may hold several words (a merge: `إلا ما شاء` for the one box Azure read as
`إلاماشاء`): the text is dealt out letter by letter, each space riding on the letter before it, so no glyph is
given a bare space. `verify_ink` renders the pages before and after and compares the pixels.
"""
from __future__ import annotations
import json
from pathlib import Path
import fitz
from ..text import visual, chrome_reads, latin_majority, RTL
from .inspect import page_glyphs, set_glyph_text
from ..geometry.letters import letters_of


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / (((a[2] - a[0]) * (a[3] - a[1])) + ((b[2] - b[0]) * (b[3] - b[1])) - inter or 1.0)


def _fit(glyph_box, box) -> float:
    """How much of the smaller box lies inside the other: a dash's declared
    box is a few pixels inside its Azure box (IoU 0.08, fit 1.0)."""
    ix = max(0.0, min(glyph_box[2], box[2]) - max(glyph_box[0], box[0])); iy = max(0.0, min(glyph_box[3], box[3]) - max(glyph_box[1], box[1]))
    small = min((glyph_box[2] - glyph_box[0]) * (glyph_box[3] - glyph_box[1]), (box[2] - box[0]) * (box[3] - box[1])) or 1.0
    return ix * iy / small


def stored_form(glyphs_of_line: list[dict], text: str) -> str:
    """How `text` must be stored inside this line: the line's other glyphs
    tell whether it is an Arabic line and whether Latin segments outnumber
    Arabic ones (pdfium then reads it left to right)."""
    logical = chrome_reads(" ".join(g["text"] for g in glyphs_of_line))
    rtl = bool(RTL.search(logical)) or bool(RTL.search(text))
    return visual(text, rtl, rtl and latin_majority(logical))


def units_of(text: str) -> list[str]:
    """One unit per letter for dealing a correction over glyphs: lam-alef one unit, marks and kashida on the letter
    before, punctuation before the first letter on the first, anything else (spaces, punctuation) on the letter
    before it. Joined, the units give the text back."""
    out, lead = [], ""
    i = 0
    while i < len(text):
        if text[i:i + 2] in ("لا", "لأ", "لإ", "لآ"):
            out.append(lead + text[i:i + 2]); lead = ""; i += 2; continue
        ch = text[i]
        if letters_of(ch):                       # an Arabic letter
            out.append(lead + ch); lead = ""
        elif ch.isalnum():                       # Latin letters and digits: one unit each
            out.append(lead + ch); lead = ""
        elif out:
            out[-1] += ch
        else:
            lead += ch
        i += 1
    if lead:
        out = out[:-1] + [out[-1] + lead] if out else [lead]
    return out


def apply_corrections(pdf: Path, corrections: list[dict], shapes_json: Path | None = None, min_fit: float = 0.5,
                      log: bool = True) -> list[dict]:
    """corrections: [{page (1-based), box [x0,y0,x1,y1] in scan px, text, optional id (the ALTO word)}].
    Returns what was done per correction; the PDF is saved in place (incrementally) when anything changed.
    log: append the results to <stem>.corrections.json (the `inkscript correct` way); `inkscript fix` keeps its own."""
    pdf = Path(pdf); doc = fitz.open(pdf); done = []
    changed = False
    cache: dict[int, list[dict]] = {}
    for c in corrections:
        pno = int(c["page"]) - 1
        glyphs = cache.setdefault(pno, page_glyphs(doc, pno))
        best = max(glyphs, key=lambda g: (_fit(g["box_px"], c["box"]), _iou(g["box_px"], c["box"])), default=None)
        score = _fit(best["box_px"], c["box"]) if best else 0.0
        if not best or score < min_fit:
            done.append(dict(**{k: v for k, v in c.items() if k in ("page", "box", "text", "id")}, applied=False,
                             reason=f"no glyph overlaps the box (best IoU {score:.2f})")); continue
        line = [g for g in glyphs if g["font"] == best["font"]]
        # A word is often several glyphs now (pieces, letters). Every glyph of the line lying inside the word's box
        # belongs to it; the corrected text is dealt out over them in reading order, one letter each and the rest
        # on the last, so the word still copies out whole and each glyph keeps a letter to select.
        area = lambda b: max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
        rtl = bool(RTL.search(c["text"]))
        order = lambda gs: sorted(gs, key=lambda g: -(g["box_px"][0] + g["box_px"][2]) if rtl else (g["box_px"][0] + g["box_px"][2]))
        reads = lambda gs: "".join(chrome_reads(g["text"]) for g in order(gs))
        # A letter's declared box often reaches past Azure's word box (a final ر, an initial ف): a glyph belongs to
        # the word when its middle lies inside the box (experiment 27 found the old rule, 80% inside, leaving such
        # letters out, so the word read رزفير after a correction to زفير).
        x0, y0, x1, y1 = c["box"]
        inside = [g for g in line if x0 - 2 <= (g["box_px"][0] + g["box_px"][2]) / 2 <= x1 + 2
                  and min(g["box_px"][3], y1) > max(g["box_px"][1], y0) and area(g["box_px"]) <= 2.5 * area(c["box"])]
        if best not in inside: inside = [best]
        near = [k for k, g in enumerate(line) if min(g["box_px"][2], x1) > max(g["box_px"][0], x0)]
        runs = [line[a:b + 1] for a in near for b in near if b >= a and b - a < 40]
        done_already = [r for r in [inside] + runs if reads(r) == c["text"]]
        if done_already:
            inside = done_already[0]
        elif c.get("was") and reads(inside).replace(" ", "") != c["was"].replace(" ", ""):
            # the caller says what the word reads now: take the run of the line's glyphs (stream order) that does
            hit = [r for r in runs if reads(r).replace(" ", "") == c["was"].replace(" ", "")]
            if not hit:
                done.append(dict(**{k: v for k, v in c.items() if k in ("page", "box", "text", "id")}, applied=False,
                                 reason=f"the glyphs in the box read {reads(inside)!r}, not {c['was']!r}")); continue
            inside = min(hit, key=len)
        inside = order(inside)
        was = "".join(chrome_reads(g["text"]) for g in inside)
        keep = {k: v for k, v in c.items() if k in ("page", "box", "text", "id")}
        if was == c["text"] or was == c["text"].replace(" ", ""):
            if was == c["text"]:
                done.append(dict(**keep, applied=True, already=True, was=was, font=best["font"], code=best["code"],
                                 glyphs=len(inside), iou=round(score, 3)))
                continue
        units = units_of(c["text"]) if rtl else list(c["text"])
        if len(inside) > 1 and len(units) < len(inside):
            done.append(dict(**keep, applied=False, reason=f"the word is {len(inside)} glyphs and the correction has {len(units)} letters")); continue
        chunks = [c["text"]] if len(inside) == 1 else units[:len(inside) - 1] + ["".join(units[len(inside) - 1:])]
        for g, chunk in zip(inside, chunks):
            stored = stored_form(line, chunk); set_glyph_text(doc, g, stored); g["text"] = stored
        changed = True
        done.append(dict(**keep, applied=True, was=was, font=best["font"], code=best["code"], glyphs=len(inside), iou=round(score, 3)))
    if changed:
        doc.save(pdf, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    doc.close()
    fresh = [d for d in done if d["applied"] and not d.get("already")]
    if fresh and shapes_json and Path(shapes_json).exists():
        s = json.loads(Path(shapes_json).read_text(encoding="utf-8"))
        for d in fresh:
            mine = [p for p in s["placements"] if d.get("id") and p.get("word") == d["id"]]
            if mine:
                for p in mine:
                    p["corrected"] = d["text"]
                continue
            for p in s["placements"]:
                if p["page"] == d["page"] and _fit(p["box"], d["box"]) >= min_fit:
                    p["text"] = d["text"]; p["corrected"] = True; break
        Path(shapes_json).write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    if log:
        from ..enrich.corrections import load as load_log, save as save_log
        path = pdf.with_suffix(".corrections.json")
        data = load_log(path)
        data["corrections"] += [dict(d, source="manual", status="applied" if d["applied"] else "declined",
                                     pdf=pdf.name) for d in done]
        save_log(path, data)
    return done


def verify_ink(before: Path | bytes, after: Path, pages: list[int] | None = None, scale: float = 100 / 72) -> dict:
    """The drawing before and after a correction, rendered by pdfium: pages compared pixel for pixel, and the text
    of every page (pdfium's reading) before and after. `before` may be the original bytes (an incremental save
    keeps them as the file's prefix). pages: 1-based pages to render (default all)."""
    import numpy as np
    import pypdfium2 as pdfium
    a = pdfium.PdfDocument(before if isinstance(before, (bytes, bytearray)) else str(before))
    b = pdfium.PdfDocument(str(after))
    res = dict(pages=len(a), rendered=0, identical=0, text_changed=[])
    try:
        for i in range(len(a)):
            ta, tb = a[i].get_textpage().get_text_range(), b[i].get_textpage().get_text_range()
            if ta != tb:
                res["text_changed"].append(i + 1)
            if pages is not None and i + 1 not in pages:
                continue
            ia = a[i].render(scale=scale).to_numpy()
            ib = b[i].render(scale=scale).to_numpy()
            res["rendered"] += 1
            res["identical"] += bool(ia.shape == ib.shape and np.array_equal(ia, ib))
    finally:
        a.close(); b.close()
    res["ink_identical"] = res["identical"] == res["rendered"]
    return res
