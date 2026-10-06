"""Where the locally available documents are, and their words in reading order.

Copied from experiment 20 (docs.py); changes: each word keeps `pi`, its index in Azure's page word list (experiment 19
ids are doc:page:pi), and the source folders point at the other experiments' data (read only)."""
from __future__ import annotations
import json
import unicodedata
from pathlib import Path

from inkscript.ocr.azure import bbox
from quran import norm, noalef

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent

SOURCES = [
    ("fixture", REPO / "tests/fixtures/0582-004-009-012/azure"),
    ("tryout", REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/azure"),
    ("books", REPO / "experiments/16_feel/out/books/raw"),
    ("azure_map", REPO / "experiments/19_azure_map/out/docs"),
    ("fetched", REPO / "experiments/20_document_data/out/fetched"),
]

# our built PDFs (shapes.json placements), where they exist
BUILT = [REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/fixture_r2l",
         REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/native_r2l",
         REPO / "experiments/14_vs_azure/out/tryout_2026-10-05/native",
         REPO / "experiments/20_document_data/out/built"]


def list_docs() -> dict[str, dict]:
    """stem -> {json, pdf, source}; the first source that has a stem wins."""
    out = {}
    for name, root in SOURCES:
        if not root.exists():
            continue
        for js in sorted(root.glob("*/*.json")):
            stem = js.stem
            if js.parent.name != stem or stem in out:
                continue
            pdf = js.with_suffix(".pdf")
            out[stem] = {"json": js, "pdf": pdf if pdf.exists() else None, "source": name}
    return out


def shapes_for(stem: str) -> Path | None:
    for d in BUILT:
        p = d / f"{stem}.shapes.json"
        if p.exists():
            return p
    return None


def text_elements(s: str) -> list[int]:
    """Code-point start of each text element (grapheme cluster).

    Azure's offsets count text elements (stringIndexType = textElements): a
    letter and the harakat on it are one element. A cluster here is a base
    character plus the combining marks (Mn/Me/Mc), ZWJ/ZWNJ and variation
    selectors after it; CR LF is one element. Checked by re-reading every word
    of a document at its offset (see load_doc)."""
    starts, i, n = [], 0, len(s)
    while i < n:
        starts.append(i)
        if s[i] == "\r" and i + 1 < n and s[i + 1] == "\n":
            i += 2
            continue
        i += 1
        while i < n and (unicodedata.category(s[i]) in ("Mn", "Me", "Mc")
                         or s[i] in "\u200c\u200d\ufe0e\ufe0f"):
            i += 1
    starts.append(n)
    return starts


def load_doc(js: Path) -> dict:
    """Azure's reading: content, pages, words in content order, paragraphs."""
    j = json.loads(js.read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    content = ar.get("content", "")
    te = text_elements(content) if ar.get("stringIndexType") == "textElements" else None

    def cp(off):              # text-element offset -> code-point offset
        if te is None or off < 0:
            return off
        return te[min(off, len(te) - 1)]

    def span(sp):
        o, ln = sp.get("offset", -1), sp.get("length", 0)
        a = cp(o)
        return a, (cp(o + ln) - a if o >= 0 else 0)
    pages, words = {}, []
    for pg in ar.get("pages", []):
        n = pg.get("pageNumber", len(pages) + 1)
        pages[n] = {"w": pg.get("width") or 1, "h": pg.get("height") or 1,
                    "angle": pg.get("angle") or 0, "unit": pg.get("unit", "inch")}
        for pi, w in enumerate(pg.get("words", [])):
            if not w.get("polygon"):
                continue
            o, ln = span(w.get("span") or {})
            words.append({"text": w.get("content", ""), "page": n,
                          "poly": w["polygon"], "box": bbox(w["polygon"]),
                          "off": o, "len": ln,
                          "conf": w.get("confidence"), "pi": pi})   # pi: index in Azure's page word list (exp. 19 ids)
    words.sort(key=lambda w: w["off"])
    bad = sum(content[w["off"]:w["off"] + w["len"]] != w["text"] for w in words)
    for i, w in enumerate(words):
        w["idx"] = i
        w["n"] = norm(w["text"])
        w["k"] = noalef(w["n"])
    paras = []
    for p in ar.get("paragraphs", []):
        o, ln = span((p.get("spans") or [{}])[0])
        brs = p.get("boundingRegions") or []
        paras.append({"off": o, "len": ln,
                      "role": p.get("role"), "content": p.get("content", ""),
                      "page": brs[0]["pageNumber"] if brs else None,
                      "box": bbox(brs[0]["polygon"]) if brs and brs[0].get("polygon") else None})
    return {"content": content, "pages": pages, "words": words, "paras": paras,
            "offset_mismatch": bad, "model": ar.get("modelId"), "api": ar.get("apiVersion"),
            "gemini_front_page": ar.get("gemini_front_page")}
