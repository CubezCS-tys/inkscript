"""Azure Document Intelligence output: words with boxes, paragraphs, lines."""
from __future__ import annotations
import json
from pathlib import Path

def bbox(poly: list[float]) -> tuple[float, float, float, float]:
    """Axis-aligned box of Azure's 4-corner polygon. The scans are skewed, so the
    polygon is not axis-aligned and its corners must not be read pairwise."""
    xs, ys = poly[0::2], poly[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def load_azure(path: Path) -> tuple[list[dict], list[dict], dict]:
    """Flatten Azure into a document-order word list plus paragraph spans.

    Words carry their page and box; paragraphs carry their character span, which
    is what assigns words to paragraphs exactly rather than by overlap tests.
    """
    j = json.loads(path.read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    words, dims = [], {}
    for pg in ar.get("pages", []):
        n = pg.get("pageNumber", len(dims) + 1)
        dims[n] = (pg.get("width") or 1, pg.get("height") or 1)
        for w in pg.get("words", []):
            if not w.get("polygon"):
                continue
            sp = w.get("span") or {}
            words.append({"text": w.get("content", ""), "page": n,
                          "box": bbox(w["polygon"]),
                          "off": sp.get("offset", -1), "len": sp.get("length", 0),
                          "conf": w.get("confidence")})
    paras = []
    for p in ar.get("paragraphs", []):
        br = (p.get("boundingRegions") or [None])[0]
        sp = (p.get("spans") or [{}])[0]
        if not br or not br.get("polygon"):
            continue
        paras.append({"page": br.get("pageNumber", 1), "box": bbox(br["polygon"]),
                      "off": sp.get("offset", -1), "len": sp.get("length", 0),
                      "azure_text": p.get("content", "")})
    return words, paras, dims


def load_lines(path: Path) -> dict[int, list[dict]]:
    """Azure's line objects per page number (spans tie them to words)."""
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    return {p["pageNumber"]: p.get("lines", []) for p in ar.get("pages", [])}
