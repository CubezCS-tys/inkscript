"""A page you can look at: the same page from both layers, side by side.

    python viewer.py <azure_dir> <ours_dir> [--pages 2] [--dpi 100]

For each document it shows one page and lets you flip between the two text layers:

* **the boxes** — every character's selection box drawn on the page. Azure's are a uniform grid (it never
  knew where the letters are); ours follow the ink.
* **the copy** — what a reader actually gets when they select the page and press copy, from each PDF, with
  the lines that came back in the wrong order marked.

One self-contained HTML file; no server, no data outside it.
"""
from __future__ import annotations
import argparse, base64, io, json, re, sys, unicodedata
from pathlib import Path
import numpy as np, cv2, pypdfium2 as pdfium

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from inkscript.text import ARABIC_LETTER

N = lambda s: unicodedata.normalize("NFKC", s)


def edge(t):
    while t and unicodedata.category(t[0])[0] in "PSZ": t = t[1:]
    while t and unicodedata.category(t[-1])[0] in "PSZ": t = t[:-1]
    return t


def key(line):
    return tuple(x for x in (edge(w) for w in N(line).split()) if x and ARABIC_LETTER.search(x))


def render(pdf: Path, page: int, dpi: int):
    d = pdfium.PdfDocument(str(pdf)); pg = d[page - 1]
    W, H = pg.get_size()
    img = pg.render(scale=dpi / 72, grayscale=False).to_numpy().copy()
    tp = pg.get_textpage(); t = tp.get_text_range()
    boxes = [tp.get_charbox(i) for i in range(len(t))]
    tp.close(); pg.close(); d.close()
    return img, t, boxes, H


def draw(img, boxes, H, dpi, colour):
    out = img.copy()
    s = dpi / 72
    for b in boxes:
        x0, y0, x1, y1 = int(b[0] * s), int((H - b[3]) * s), int(b[2] * s), int((H - b[1]) * s)
        if x1 > x0 and y1 > y0:
            cv2.rectangle(out, (x0, y0), (x1, y1), colour, 1)
    return out


def jpg(a, q=72, width=900):
    if a.shape[1] > width:
        s = width / a.shape[1]
        a = cv2.resize(a, (width, int(a.shape[0] * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(a, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, q])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def copied(text, runs):
    """What a reader gets, line by line, with the reference lines that did not survive marked."""
    lines = [l for l in N(text).replace("\r\n", "\n").split("\n")]
    keys = [key(l) for l in lines]
    bad = 0; want = []
    for r in runs:
        k = key(r)
        if len(k) < 3:
            continue
        n = len(k)
        ok = any(l[i:i + n] == k for l in keys if len(l) >= n for i in range(len(l) - n + 1))
        want.append((r, ok)); bad += not ok
    return lines, want, bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("azure"); ap.add_argument("ours")
    ap.add_argument("--dpi", type=int, default=100)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    az, ours = Path(a.azure), Path(a.ours)
    reps = {r["doc"]: r for r in json.load(open(ours / "native_pdf_report.json"))}
    docs = []
    for stem in sorted(reps):
        r = reps[stem]
        pages = [p for p in r["pages"] if p.get("glyphs")]
        if not pages:
            continue
        pi = pages[len(pages) // 2]                      # a page from the middle: body text, not a cover
        pn = pi["page"]
        try:
            # our boxes are drawn on the SAME scan Azure's are, so only the boxes differ; the vector edition
            # (the ink as the text, no image) is a third view of its own
            oi, ot, ob, oH = render(ours / f"{stem}.pdf", pn, a.dpi)
            vi, _, _, _ = render(ours / f"{stem}_vector.pdf", pn, a.dpi)
            ai, at, ab, aH = render(az / stem / f"{stem}.pdf", pn, a.dpi)
        except Exception as e:
            print(f"  skipped {stem}: {e}"); continue
        al, aw, abad = copied(at, pi["runs"])
        ol, ow, obad = copied(ot, pi["runs"])
        docs.append(dict(stem=stem, page=pn,
                         a_plain=jpg(ai), a_box=jpg(draw(ai, ab, aH, a.dpi, (220, 40, 40))),
                         o_plain=jpg(oi), o_box=jpg(draw(oi, ob, oH, a.dpi, (30, 90, 220))), o_vec=jpg(vi),
                         a_lines=al[:60], o_lines=ol[:60],
                         a_bad=abad, o_bad=obad, n_ref=len(aw),
                         a_chars=len(ab), o_chars=len(ob)))
        print(f"  {stem} p{pn}: azure {abad} lines wrong, ours {obad}")
    out = Path(a.out) if a.out else Path(__file__).parent / "out" / "compare.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    tpl = (Path(__file__).parent / "viewer.html").read_text(encoding="utf-8")
    out.write_text(tpl.replace("__DATA__", json.dumps(docs, ensure_ascii=False)), encoding="utf-8")
    mb = out.stat().st_size / 1e6
    print(f"\n{len(docs)} documents -> {out.resolve()}  ({mb:.1f} MB, open it directly)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
