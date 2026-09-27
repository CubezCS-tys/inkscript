"""The gold set: hand-mark every word of a page — is the reading right, and if not, what KIND of error is it?

    python mark.py <stem> --page 3 [--built DIR] [--azure DIR] [--out FILE.html]

Writes one self-contained HTML page: every word of that page as its own ink beside the reading the PDF
carries, in reading order, with a class to pick and a field to type what the ink really says. Default is
"correct", so only the wrong ones cost a click — chase every "no".

Why per-word AND per-class: the counts decide what to build next. A page whose errors are nearly all dot
confusions says the look-alike checker (milestone 1) is the right build; a page of dropped and merged words
says the right build is a coverage test instead. `check --html` shows only contradictions and numbers; a gold
set needs every word, judged, including the ones nothing flagged.

Reads `<stem>.shapes.json` (what the PDF carries: page, text, box, rot) and the scan beside the Azure JSON.
Nothing here writes to the built set; it is safe to run while a set is building.
"""
from __future__ import annotations
import argparse, base64, glob, io, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import numpy as np, cv2, fitz
from inkscript.geometry.trace import DPI
from inkscript.ocr.azure import load_azure

CLASSES = [
    ("correct",   "correct",            "1", "the reading matches the ink"),
    ("dots",      "dots",               "2", "ب ت ث ن ي / ج ح خ — right skeleton, wrong dot count or side"),
    ("hamza",     "hamza أ ا إ",        "3", "hamza present or absent against the ink"),
    ("ta",        "ة / ه",              "4", ""),
    ("ya",        "ى / ي",              "5", ""),
    ("lookalike", "other look-alike",   "6", "same shape family, different letter"),
    ("wrong",     "wrong word",         "7", "a different word altogether"),
    ("merged",    "merged",             "8", "one reading covers ink that is two words"),
    ("split",     "split",              "9", "this reading is half of one word"),
    ("invented",  "invented",           "0", "a reading with no ink under it"),
    ("style",     "the book's style",   "s", "the ink differs from standard Arabic, but the BOOK always prints it this way — not an error"),
    ("boxwrong",  "ink isn't this word","b", "the reading is fine — the BOX covers the wrong ink (part of the word, or a neighbour). Azure's fault, not the reader's"),
    ("unsure",    "unsure",             "u", "cannot tell from the ink"),
]


def azure_page(azure: Path, stem: str, pn: int):
    """Azure's own reading of a page, in the pixel frame the build renders — the text that Gemini REPLACES on
    page 1. Same ink, same boxes, the other reader: the only way to score the two against one page."""
    j = json.load(open(azure / stem / f"{stem}.json")); ar = j.get("analyzeResult", j)
    pg = {p["pageNumber"]: p for p in ar["pages"]}[pn]
    ang = pg.get("angle") or 0.0
    rot = 90 if ang > 45 else -90 if ang < -45 else 0
    words, _, dims = load_azure(azure / stem / f"{stem}.json")
    W_in, H_in = dims[pn]
    out = []
    for w in words:
        if w["page"] != pn or not w["text"].strip():
            continue
        x0, y0, x1, y1 = w["box"]
        if rot == 90:    x0, y0, x1, y1 = y0, W_in - x1, y1, W_in - x0      # the same turn the build makes
        elif rot == -90: x0, y0, x1, y1 = H_in - y1, x0, H_in - y0, x1
        out.append(dict(text=w["text"], page=pn, rot=rot, _box=(x0, y0, x1, y1)))
    return out, rot, ((H_in, W_in) if rot else (W_in, H_in))


def find_shapes(built: Path, stem: str) -> Path:
    hits = glob.glob(f"{built}/**/{stem}.shapes.json", recursive=True)
    if not hits:
        sys.exit(f"no {stem}.shapes.json under {built}")
    return Path(hits[0])


def page_image(azure: Path, stem: str, pn: int, rot: int, scan: Path | None = None):
    """The scan page as the build saw it: rendered at DPI and turned upright, so the stored boxes fit it."""
    pdf = (scan / f"{stem}.pdf") if scan else (azure / stem / f"{stem}.pdf")
    if not pdf.exists():
        sys.exit(f"no scan at {pdf}")
    doc = fitz.open(pdf)
    try:
        pix = doc[pn - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        g = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()
    finally:
        doc.close()                      # a script that leaves PDFs open once took the machine's memory
    if rot:
        g = np.ascontiguousarray(np.rot90(g, 1 if rot == 90 else -1))
    return g


def png(a: np.ndarray) -> str:
    ok, buf = cv2.imencode(".png", a, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise RuntimeError("could not encode a crop")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()


def reading_order(words: list[dict]) -> list[dict]:
    """Line by line down the page, right to left inside a line — the order an Arabic reader would take them."""
    rest = sorted(words, key=lambda w: w["box"][1]); lines = []
    while rest:
        seed = rest.pop(0); y0, y1 = seed["box"][1], seed["box"][3]; h = max(1, y1 - y0); line = [seed]
        for w in list(rest):
            b = w["box"]
            if min(y1, b[3]) - max(y0, b[1]) > 0.4 * min(h, max(1, b[3] - b[1])):
                line.append(w); rest.remove(w); y0, y1 = min(y0, b[1]), max(y1, b[3]); h = max(1, y1 - y0)
        lines.append(sorted(line, key=lambda w: -w["box"][2]))
    return [w for L in lines for w in L]


def overview(g: np.ndarray, words: list[dict], width: int = 900) -> str:
    """The whole page with every word's box drawn on it: ink outside a box is a word nothing read (they cannot
    appear as rows below, so this picture is the only place a dropped word shows)."""
    im = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    for w in words:
        x0, y0, x1, y1 = w["box"]
        cv2.rectangle(im, (x0, y0), (x1, y1), (40, 40, 220), 3)          # BGR: red
    s = width / im.shape[1]
    im = cv2.resize(im, (width, max(1, int(im.shape[0] * s))), interpolation=cv2.INTER_AREA)
    return png(im)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stem")
    ap.add_argument("--page", type=int, required=True)
    ap.add_argument("--built", default="experiments/09_pen_path/out/journals227")
    ap.add_argument("--azure", default=str(Path.home() / "Desktop/OCR_gem_json/output/s3_night/azure"))
    ap.add_argument("--scan", default=None, help="where the scans are, if not beside the Azure JSON (the fixture's input/)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pad", type=int, default=8, help="pixels of margin around a word's crop")
    ap.add_argument("--sample", type=int, default=0, help="mark only this many words, a contiguous run in reading order")
    ap.add_argument("--start", type=int, default=0, help="where that run begins (0 = the first word of the page)")
    ap.add_argument("--reader", default="pdf", choices=["pdf", "azure"],
                    help="pdf: the reading the PDF carries (Gemini's on page 1); azure: Azure's own, which Gemini replaced")
    a = ap.parse_args()

    if a.reader == "azure":
        words, rot, (W_in, H_in) = azure_page(Path(a.azure), a.stem, a.page)
        if not words:
            sys.exit(f"{a.stem} has no Azure words on page {a.page}")
        g = page_image(Path(a.azure), a.stem, a.page, rot, Path(a.scan) if a.scan else None)
        sx, sy = g.shape[1] / W_in, g.shape[0] / H_in                 # page units -> the rendered pixels
        for w in words:
            x0, y0, x1, y1 = w.pop("_box")
            w["box"] = [int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)]
    else:
        shapes = find_shapes(Path(a.built), a.stem)
        words = [w for w in json.load(open(shapes))["placements"] if w["page"] == a.page]
        if not words:
            sys.exit(f"{a.stem} has no words on page {a.page}")
        rot = words[0].get("rot", 0)
        g = page_image(Path(a.azure), a.stem, a.page, rot, Path(a.scan) if a.scan else None)
    words = reading_order(words)
    # A contiguous run, not a random scatter: merged and split readings are only visible beside their
    # neighbours, and the eye keeps its place down a column.
    if a.sample:
        words = words[a.start:a.start + a.sample]

    rows = []
    H, W = g.shape
    for i, w in enumerate(words):
        x0, y0, x1, y1 = w["box"]
        x0, y0 = max(0, x0 - a.pad), max(0, y0 - a.pad); x1, y1 = min(W, x1 + a.pad), min(H, y1 + a.pad)
        if x1 <= x0 or y1 <= y0:
            continue
        rows.append(dict(i=i, text=w["text"], box=w["box"], img=png(g[y0:y1, x0:x1])))

    tag = "" if a.reader == "pdf" else "_azure"
    out = Path(a.out) if a.out else Path(__file__).parent / "out" / f"{a.stem}_p{a.page}{tag}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tpl = (Path(__file__).parent / "template.html").read_text(encoding="utf-8")
    html = (tpl.replace("__DATA__", json.dumps(dict(stem=a.stem, page=a.page, sheet=a.reader, dpi=DPI, rot=rot,
                                                    classes=[dict(id=c, label=l, key=k, hint=h) for c, l, k, h in CLASSES],
                                                    words=rows), ensure_ascii=False))
                .replace("__OVERVIEW__", overview(g, words))
                .replace("__TITLE__", f"{a.stem} · page {a.page}" + (" · Azure's own reading" if a.reader == "azure" else "")))
    out.write_text(html, encoding="utf-8")
    print(f"{len(rows)} words -> {out.resolve()}")
    # Chrome gives a file:// page an opaque origin and may refuse it localStorage, which is what keeps a
    # half-finished page of marks; served over http it always saves.
    print(f"  serve it:  python3 -m http.server 8731 --bind 127.0.0.1 --directory {out.parent.resolve()}\n"
          f"  then open: http://127.0.0.1:8731/{out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
