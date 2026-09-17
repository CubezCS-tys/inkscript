"""Azure's searchable PDF with page 1's text layer rewritten from Gemini's
read, in a standard Arabic font (the pre-geometry approach; see pdf/native.py
for the ink-glyph layer that supersedes it for selection quality)."""
from __future__ import annotations
import re, unicodedata
from pathlib import Path

from ..text import ARABIC, RTL, MARKS, norm
from .azure import load_azure
from .align import page1_text

FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"

def for_word(s: str) -> str:
    """make_searchable_pdf.for_text_layer, but script-aware.

    That one reverses every line, which is right for Mistral's all-Arabic blocks
    and wrong here: front pages print English titles, and a reversed Latin word
    extracts backwards. Arabic runs are reversed (PyMuPDF lays them out visually);
    anything else — Latin, and Urdu's digits (see RTL) — is left as written.

    The leading space is what separates words. Azure's word boxes touch, so with
    no space the extractor sees no gap and returns `العربى،قد` as one token — and
    a phrase search for `العربى قد` fails. Measured over 26 front pages: word
    recall 89% -> 99.5%, phrase search 78% -> 98%. A zero-width space scored the
    same but leaked into the extracted text, which breaks exact matching.
    """
    toks = s.split(" ")
    if not any(RTL.search(t) for t in toks):
        return " " + s
    return " " + " ".join(t[::-1] if RTL.search(t) else t for t in reversed(toks))


def draw_words(page, boxes: list[tuple[tuple, str]], sx: float, sy: float,
               font: str) -> tuple[int, int]:
    """Invisible text, one Azure word box at a time, largest size that fits.

    Returns (boxes drawn, of which squeezed). A box too small for its text even
    at 2pt — several Gemini words piled into one narrow Azure box — is written
    with insert_text instead: one line, scaled to the box width, spilling past
    it if it must. insert_textbox writes NOTHING when text does not fit, so the
    earlier "unsized fallback" through it silently dropped those words.
    """
    import fitz
    face = fitz.Font(fontfile=font)
    placed = squeezed = 0
    for (x0, y0, x1, y1), text in boxes:
        rect = fitz.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
        if not text or rect.is_empty or rect.width < 1 or rect.height < 1:
            continue
        text = for_word(text)
        size = max(2.0, min(rect.height * 0.9, 72.0))
        while size >= 2.0:
            if page.insert_textbox(rect, text, fontname="notoar", fontfile=font,
                                   fontsize=size, render_mode=3) >= 0:
                break
            size -= max(0.5, size * 0.12)
        else:
            size = max(1.0, min(rect.height * 0.8, rect.width / max(1e-3, face.text_length(text, 1))))
            page.insert_text((rect.x0, rect.y1 - rect.height * 0.2), text, fontname="notoar",
                             fontfile=font, fontsize=size, render_mode=3)
            squeezed += 1
        placed += 1
    return placed, squeezed


def build(stem: str, azure_json: Path, azure_pdf: Path, gtext: str | None,
          out_pdf: Path, min_exact: float, font: str) -> tuple[dict, list[str] | None]:
    import fitz
    words, _, dims = load_azure(azure_json)
    p1 = [w for w in words if w["page"] == 1]
    texts, st = page1_text(p1, gtext, min_exact)
    st = {"doc": stem, **st}

    doc = fitz.open(azure_pdf)
    if texts is not None:
        boxes = [(w["box"], t) for w, t in zip(p1, texts)]
        page = doc[0]
        page.add_redact_annot(page.rect)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                              graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                              text=fitz.PDF_REDACT_TEXT_REMOVE)
        W, H = dims[1]                                  # inches, from Azure
        st["boxes_drawn"], st["boxes_squeezed"] = draw_words(
            page, boxes, page.rect.width / W, page.rect.height / H, font)
        st["p1_title_line"] = " ".join(gtext.strip().split("\n", 1)[0].split())[:120]

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out_pdf, garbage=3, deflate=True)
    doc.close()
    return st, texts


def verify(out_pdf: Path, azure_pdf: Path, placed: list[str] | None) -> dict:
    """Three checks: page 1 gives back the words placed on it, pages 2+ are
    unchanged, and the page-1 scan is pixel-identical to Azure's.

    Checked against what was placed rather than Gemini's full text: on a
    gemini-title page most of the layer is deliberately Azure's."""
    import fitz
    o, a = fitz.open(out_pdf), fitz.open(azure_pdf)

    def toks(s):
        # Edge punctuation off: Gemini writes `العربى ،` where Azure's box holds
        # `العربى،`, and that is the same word found, not a miss.
        s = unicodedata.normalize("NFKC", s)
        return [w for w in (re.sub(r"^[^\w]+|[^\w]+$", "", t) for t in re.split(r"\s+", s)) if w]

    v = {}
    if placed:
        want = [t for t in toks(" ".join(placed)) if ARABIC.search(t) or t.isalpha()]
        got = toks(o[0].get_text())
        gs, flat = set(got), f" {' '.join(got)} "
        v["p1_recall"] = round(sum(t in gs for t in want) / max(1, len(want)), 3)
        # phrase search is what a reader actually does: consecutive word pairs
        pairs = [f" {x} {y} " for x, y in zip(want, want[1:])]
        v["p1_phrase"] = round(sum(pr in flat for pr in pairs) / max(1, len(pairs)), 3)
    v["rest_identical"] = all(o[i].get_text() == a[i].get_text()
                              for i in range(1, a.page_count))
    po, pa = o[0].get_pixmap(dpi=72), a[0].get_pixmap(dpi=72)
    v["scan_identical"] = po.samples == pa.samples
    o.close(); a.close()
    return v
