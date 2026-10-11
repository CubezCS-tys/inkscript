"""What is on each candidate page, seen by Gemini (experiment 34): a cheap look to confirm the kinds the features
guess (tables, equations, vowelled text, handwriting, decorative type, columns...).

    PYTHONPATH=src python classify.py out/candidates.json  -> out/page_kinds.json  {"<stem>_p<NNN>": {...}}

gemini-3.8-flash, four pages a request, each page a 100 dpi grey render at medium resolution; cached and logged
(gem.py). The answer is a set of yes/no facts per page, not a reading.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gem

MODEL = "gemini-3.8-flash"
OUT = gem.OUT
PROMPT = """You see {n} scanned pages from Arabic journals (Image 1..{n}). For each page answer with facts about what is
printed on it. Be literal; do not guess beyond what you can see.

- body_text: ordinary running paragraphs make up much of the page
- footnotes: there are footnotes (notes under a rule or in smaller type at the bottom)
- table: there is a table (rows and columns of cells, ruled or aligned; not just a list)
- equation: there is a mathematical formula or equation (symbols such as = + Σ fractions, not just numbers in text)
- vowelled: much of the Arabic text is printed with short vowel marks (harakat), as in Quran, poetry or old texts
- quran_or_verse: Quran verses, hadith or poetry set apart (brackets ﴿ ﴾, centred verse, couplets)
- mixed_latin: words or lines in Latin script (English/French, transliteration, references) mixed with the Arabic
- headings: section headings or a title in larger or bold type
- handwriting: handwritten text (not printed)
- decorative: calligraphic or decorative display lettering, stamps, ornaments with lettering
- columns: the running text is set in 2 or more columns (number of columns; 1 if a single column)
- figure: a chart, map, photo or drawing
- page_type: one of title_page, body, references, table_page, index_or_contents, cover_or_ad, blank_or_image, other
- quality: good, fair or poor (blur, bleed-through, broken letters, skew)
- note: a few words on anything unusual (max 12 words)
"""
SCHEMA = {"type": "object", "properties": {"pages": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "body_text": {"type": "boolean"}, "footnotes": {"type": "boolean"},
    "table": {"type": "boolean"}, "equation": {"type": "boolean"}, "vowelled": {"type": "boolean"},
    "quran_or_verse": {"type": "boolean"}, "mixed_latin": {"type": "boolean"}, "headings": {"type": "boolean"},
    "handwriting": {"type": "boolean"}, "decorative": {"type": "boolean"}, "columns": {"type": "integer"},
    "figure": {"type": "boolean"},
    "page_type": {"type": "string", "enum": ["title_page", "body", "references", "table_page", "index_or_contents",
                                             "cover_or_ad", "blank_or_image", "other"]},
    "quality": {"type": "string", "enum": ["good", "fair", "poor"]}, "note": {"type": "string"}},
    "required": ["n", "body_text", "footnotes", "table", "equation", "vowelled", "quran_or_verse", "mixed_latin",
                 "headings", "handwriting", "decorative", "columns", "figure", "page_type", "quality", "note"]}}},
    "required": ["pages"]}


def thumb(scan: str, page: int) -> bytes:
    import cv2
    import fitz
    import numpy as np
    d = fitz.open(scan)
    pix = d[page - 1].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
    d.close()
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


def main() -> int:
    cands = json.loads(Path(sys.argv[1]).read_text())          # [[stem, page], ...]
    pool = json.loads((OUT / "pool.json").read_text())
    f = OUT / "page_kinds.json"
    res = json.loads(f.read_text()) if f.exists() else {}
    todo = [(s, p) for s, p in cands if f"{s}_p{p:03d}" not in res]
    chunks = [todo[i:i + 4] for i in range(0, len(todo), 4)]
    est = 0.008                                                # per request, rounded up from the first ones
    print(f"{len(todo)} pages, {len(chunks)} requests, estimate ${len(chunks) * est:.2f}; spent so far ${gem.spent():.3f}",
          flush=True)

    def one(ch):
        imgs = [thumb(pool[s]["scan"], p) for s, p in ch]
        a = gem.call(MODEL, PROMPT.format(n=len(ch)), imgs, SCHEMA, "classify", est, resolution="medium")
        return ch, a

    with ThreadPoolExecutor(2) as ex:
        for k, (ch, a) in enumerate(ex.map(one, chunks), 1):
            if a:
                by = {x["n"]: x for x in a.get("pages", [])}
                for n, (s, p) in enumerate(ch, 1):
                    if n in by:
                        res[f"{s}_p{p:03d}"] = by[n]
            if k % 10 == 0:
                f.write_text(json.dumps(res, ensure_ascii=False, indent=0))
                print(k, f"${gem.spent():.3f}", flush=True)
    f.write_text(json.dumps(res, ensure_ascii=False, indent=0))
    print(len(res), "pages classified; spent", f"${gem.spent():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
