"""Normalisers: an engine's verbatim raw output -> canonical blocks.  Run core-side, so they can be changed and
re-run without inference (the normaliser version is part of every stored prediction).

Label mappings are explicit; a label not in a mapping becomes type "unknown" with `raw_label` kept, so it stays
visible.  Boxes come only from the engine (never invented); text-only engines give blocks without boxes.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..schemas import Block, TableCell

NORMALISER_VERSION = "normalise/1"

# PaddleOCR-VL / PP-DocLayoutV3 labels -> canonical types
PADDLE_LABELS = {
    "text": "paragraph", "content": "paragraph", "paragraph_title": "heading", "doc_title": "title",
    "abstract": "abstract", "header": "header", "footer": "footer", "number": "page_number",
    "footnote": "footnote", "vision_footnote": "footnote", "aside_text": "unknown",
    "table": "table", "formula": "equation", "display_formula": "equation", "inline_formula": "equation",
    "formula_number": "equation", "algorithm": "unknown",
    "image": "figure", "chart": "figure", "header_image": "figure", "footer_image": "figure", "seal": "figure",
    "figure_title": "caption", "figure_caption": "caption", "table_title": "caption", "table_caption": "caption",
    "chart_title": "caption", "caption": "caption",
    "reference": "bibliography", "reference_content": "bibliography", "list": "list",
}


def _paddle_json(raw: dict) -> list[dict]:
    """The JSON documents PaddleOCR wrote, parsed from their verbatim text."""
    out = []
    for name, text in sorted((raw or {}).get("files", {}).items()):
        if name.endswith(".json"):
            d = json.loads(text)
            out.append(d.get("res", d) if isinstance(d, dict) else d)
    return out


def paddle_markdown(raw: dict) -> str:
    return "\n\n".join(t for n, t in sorted((raw or {}).get("files", {}).items()) if n.endswith(".md"))


def html_table_cells(html: str) -> list[TableCell]:
    """Cells of an HTML table in the order written (rows top to bottom, cells in source order), spans kept.
    Columns are the spatial order the engine wrote; no reversal for Arabic."""
    import lxml.html as LH
    try:
        root = LH.fragment_fromstring(html, create_parent="div")
    except Exception:  # noqa: BLE001
        return []
    cells, taken = [], set()
    for r, tr in enumerate(root.iter("tr")):
        c = 0
        for td in tr:
            if td.tag not in ("td", "th"):
                continue
            while (r, c) in taken:
                c += 1
            rs, cs = int(td.get("rowspan", 1) or 1), int(td.get("colspan", 1) or 1)
            for i in range(rs):
                for j in range(cs):
                    taken.add((r + i, c + j))
            cells.append(TableCell(row=r, col=c, row_span=rs, col_span=cs, text=td.text_content(),
                                   header=td.tag == "th"))
            c += cs
    return cells


def normalise_paddle(raw: dict, variant: str) -> list[Block]:
    docs = _paddle_json(raw)
    blocks: list[Block] = []
    for d in docs:
        if variant == "layout_stage":
            boxes = d.get("boxes") or (d.get("layout_det_res") or {}).get("boxes") or []
            for i, b in enumerate(boxes):
                lab = b.get("label")
                blocks.append(Block(block_id=f"b{len(blocks)}", type=PADDLE_LABELS.get(lab, "unknown"),
                                    raw_label=lab, box=[float(x) for x in b["coordinate"]], box_source="engine",
                                    order=b.get("order") if isinstance(b.get("order"), int) else None,
                                    order_source="engine (layout order)" if isinstance(b.get("order"), int) else None,
                                    confidence=b.get("score"), confidence_meaning="layout detector score"))
            # layout orders may repeat or be absent; keep only a valid unique sequence
            if len({b.order for b in blocks if b.order is not None}) != sum(b.order is not None for b in blocks):
                for b in blocks:
                    b.order, b.order_source = None, None
            continue
        for item in d.get("parsing_res_list") or []:
            lab = item.get("block_label")
            content = item.get("block_content") or ""
            bb = item.get("block_bbox")
            typ = PADDLE_LABELS.get(lab, "unknown")
            flags = []
            if item.get("block_order") is not None:
                flags.append(f"block_order={item['block_order']}")
            if variant == "bare_ocr":
                # layout detection is off: the one box is the whole input image, not a detected region
                flags.append(f"engine box {bb} = the whole input (no layout stage); not used as a region")
                bb = None
            blk = Block(block_id=f"b{len(blocks)}", type=typ, raw_label=lab,
                        box=[float(x) for x in bb] if bb else None, box_source="engine" if bb else None,
                        raw_text=content, order=len(blocks), order_source="parsing_res_list position", flags=flags)
            if typ == "table" and "<t" in content:
                blk.cells = html_table_cells(content)
            if typ == "equation":
                blk.latex = content
                blk.equation_display = lab != "inline_formula"
            blocks.append(blk)
    return blocks


_MD_HEAD = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")


def normalise_text(text: str, markdown: bool) -> list[Block]:
    """A text-only engine: one block per non-empty line, in the order written (no boxes).
    In markdown mode '#' lines become headings and HTML tables become table blocks."""
    blocks: list[Block] = []
    lines = (text or "").split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip():
            i += 1
            continue
        if markdown and "<table" in ln.lower():
            j = i
            buf = []
            while j < len(lines):
                buf.append(lines[j])
                if "</table>" in lines[j].lower():
                    break
                j += 1
            html = "\n".join(buf)
            blocks.append(Block(block_id=f"b{len(blocks)}", type="table", raw_label="html_table", raw_text=html,
                                order=len(blocks), order_source="output position", cells=html_table_cells(html)))
            i = j + 1
            continue
        m = _MD_HEAD.match(ln) if markdown else None
        blocks.append(Block(block_id=f"b{len(blocks)}", type="heading" if m else "text",
                            raw_label=("md_h" + str(len(m.group(1)))) if m else "line", raw_text=ln,
                            order=len(blocks), order_source="output position"))
        i += 1
    return blocks


def normalise(engine: str, variant: str, result: dict) -> list[Block]:
    """Canonical blocks for a worker result (dict).  Workers that already return blocks keep theirs."""
    raw: Any = result.get("raw")
    if engine == "paddle_vl":
        return normalise_paddle(raw, variant)
    if engine == "nuqta":
        return normalise_text(result.get("page_text") or (raw or {}).get("text", ""), markdown=variant == "markdown")
    return [Block.model_validate(b) for b in result.get("blocks") or []]
