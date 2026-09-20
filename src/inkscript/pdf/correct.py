"""Write a corrected reading back into a finished PDF without rebuilding it.

A correction names a word the way the review list does — page and Azure box
in scan pixels — and gives the text it should carry. The glyph whose declared
box overlaps that box most gets a new ToUnicode entry, stored the way its
line is stored (the inverse of Chrome's reading, right-to-left or
left-to-right by the line's majority), and the change is logged beside the
PDF in `<stem>.corrections.json`. The ink is never touched.
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


def apply_corrections(pdf: Path, corrections: list[dict], shapes_json: Path | None = None, min_fit: float = 0.5) -> list[dict]:
    """corrections: [{page (1-based), box [x0,y0,x1,y1] in scan px, text}].
    Returns what was done per correction; the PDF is saved in place."""
    pdf = Path(pdf); doc = fitz.open(pdf); done = []
    cache: dict[int, list[dict]] = {}
    for c in corrections:
        pno = int(c["page"]) - 1
        glyphs = cache.setdefault(pno, page_glyphs(doc, pno))
        best = max(glyphs, key=lambda g: (_fit(g["box_px"], c["box"]), _iou(g["box_px"], c["box"])), default=None)
        score = _fit(best["box_px"], c["box"]) if best else 0.0
        if not best or score < min_fit:
            done.append(dict(**c, applied=False, reason=f"no glyph overlaps the box (best IoU {score:.2f})")); continue
        line = [g for g in glyphs if g["font"] == best["font"]]
        # A word is often several glyphs now (pieces, letters). Every glyph of the line lying inside the word's box
        # belongs to it; the corrected text is dealt out over them in reading order, one letter each and the rest
        # on the last, so the word still copies out whole and each glyph keeps a letter to select.
        area = lambda b: max(1.0, (b[2] - b[0]) * (b[3] - b[1]))
        inside = [g for g in line if area(g["box_px"]) <= area(c["box"]) and _fit(g["box_px"], c["box"]) >= 0.8]
        if best not in inside: inside = [best]
        rtl = bool(RTL.search(c["text"])); inside.sort(key=lambda g: -(g["box_px"][0] + g["box_px"][2]) if rtl else (g["box_px"][0] + g["box_px"][2]))
        was = "".join(chrome_reads(g["text"]) for g in inside)
        units = letters_of(c["text"]) if rtl and "".join(letters_of(c["text"])) == c["text"] else list(c["text"])
        if len(inside) > 1 and len(units) < len(inside):
            done.append(dict(**c, applied=False, reason=f"the word is {len(inside)} glyphs and the correction has {len(units)} letters")); continue
        chunks = [c["text"]] if len(inside) == 1 else units[:len(inside) - 1] + ["".join(units[len(inside) - 1:])]
        for g, chunk in zip(inside, chunks):
            stored = stored_form(line, chunk); set_glyph_text(doc, g, stored); g["text"] = stored
        done.append(dict(**c, applied=True, was=was, font=best["font"], code=best["code"], glyphs=len(inside), iou=round(score, 3)))
    doc.save(pdf, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP); doc.close()
    if shapes_json and Path(shapes_json).exists():
        s = json.loads(Path(shapes_json).read_text(encoding="utf-8"))
        for d in done:
            if not d["applied"]:
                continue
            for p in s["placements"]:
                if p["page"] == d["page"] and _fit(p["box"], d["box"]) >= min_fit:
                    p["text"] = d["text"]; p["corrected"] = True; break
        Path(shapes_json).write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    log = pdf.with_suffix(".corrections.json")
    prev = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    log.write_text(json.dumps(prev + done, ensure_ascii=False, indent=1), encoding="utf-8")
    return done
