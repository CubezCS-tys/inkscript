"""Build docs/storyboard/index.html — the interactive storyboard — from real outputs.

    python docs/storyboard/build.py --native-dir OUT/native_set --azure-pdf DATA/azure/<stem>/<stem>.pdf \
        --review OUT/s3_sample/review/0450-000-022-001.review.json --review-pdf DATA/azure/0450.../0450....pdf

Everything visual on the page comes from files the pipeline wrote: the demo's
traced title (docs/demo), a page-1 region of the fixture document with its
glyph outlines read back out of the PDF's Type 3 fonts, what pdfium (Chrome's
engine) copies from Azure's PDF and from ours, the document alphabet sheet,
and one contradiction from the review list with its ink crops.
"""
import argparse, base64, json, re
from pathlib import Path

HERE = Path(__file__).parent
STEM = "0582-004-009-012"


def glyph_explorer(native_dir: Path, stem: str, top_share: float = 0.50, scale: float = 2.2) -> dict:
    """A region of page 1 as an image, with every glyph's outline, text and shape ids read from the PDF."""
    import fitz, sys
    sys.path.insert(0, str(HERE.parent.parent / "src"))
    from inkscript.pdf.inspect import page_glyphs
    doc = fitz.open(native_dir / f"{stem}.pdf"); pg = doc[0]; H = pg.rect.height
    top = [g for g in page_glyphs(doc, 0) if g["box"][1] > H * top_share]
    ymin = min(p[1] for g in top for path in g["paths"] for p in path) - 6; ymax = max(p[1] for g in top for path in g["paths"] for p in path) + 6
    xmin = min(p[0] for g in top for path in g["paths"] for p in path) - 14; xmax = max(p[0] for g in top for path in g["paths"] for p in path) + 14
    pix = pg.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=fitz.Rect(xmin, H - ymax, xmax, H - ymin), colorspace=fitz.csGRAY)
    px = lambda x, y: [round((x - xmin) * scale, 1), round((ymax - y) * scale, 1)]
    return dict(w=pix.width, h=pix.height, jpg=base64.b64encode(pix.tobytes("jpg", jpg_quality=72)).decode(), page=1, doc=stem,
                glyphs=[dict(t=g["text"], ids=g["ids"], box=[*px(g["box"][0], g["box"][3]), *px(g["box"][2], g["box"][1])],
                             paths=[[px(x, y) for x, y in path] for path in g["paths"]]) for g in top])


def what_chrome_copies(azure_pdf: Path, ours_pdf: Path, page: int = 2, lines: int = 6) -> dict:
    import pypdfium2 as pdfium
    out = {}
    for label, path in (("azure", azure_pdf), ("ours", ours_pdf)):
        p = pdfium.PdfDocument(str(path)); t = p[page - 1].get_textpage().get_text_range().replace("\r\n", "\n"); p.close()
        out[label] = [l.strip() for l in t.split("\n") if l.strip()][:lines]
    return out


def contradiction(review_json: Path, review_pdf: Path) -> dict | None:
    """One substitution from a review list, with the ink of each occurrence."""
    import fitz
    r = json.loads(review_json.read_text(encoding="utf-8"))
    subs = [c for c in r["conflicts"] if c["kind"] == "substitution" and all(len(k) >= 3 for k in c["readings"])]
    if not subs:
        return None
    c = subs[0]; doc = fitz.open(review_pdf); crops = []
    for sp in c["suspects"][:4]:
        pg = doc[sp["page"] - 1]; x0, y0, x1, y1 = [v * 72 / 300 for v in sp["box"]]
        pix = pg.get_pixmap(matrix=fitz.Matrix(3, 3), clip=fitz.Rect(x0 - 6, y0 - 6, x1 + 6, y1 + 6), colorspace=fitz.csGRAY)
        crops.append(dict(page=sp["page"], text=sp["text"], w=pix.width, h=pix.height, jpg=base64.b64encode(pix.tobytes("jpg", jpg_quality=75)).decode()))
    return dict(doc=review_pdf.stem, sig=c["sig"], readings=c["readings"], crops=crops, kinds=r["kinds"], words=r["words"], numbers=len(r["numbers"]), conflicts=len(r["conflicts"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native-dir", required=True); ap.add_argument("--azure-pdf", required=True)
    ap.add_argument("--review", required=True); ap.add_argument("--review-pdf", required=True)
    ap.add_argument("--out", default=str(HERE / "index.html"))
    a = ap.parse_args()
    native = Path(a.native_dir).expanduser()
    demo = (HERE.parent / "demo" / "ink_to_text.html").read_text(encoding="utf-8")
    line = next(l for l in demo.splitlines() if l.startswith("const DATA="))
    demo_data = line[len("const DATA="):]; demo_data = demo_data[: demo_data.index("};") + 1]   # the demo keeps its code on the same line
    data = dict(
        explorer=glyph_explorer(native, STEM),
        copies=what_chrome_copies(Path(a.azure_pdf).expanduser(), native / f"{STEM}.pdf"),
        alphabet_png=base64.b64encode((native / f"{STEM}.alphabet.png").read_bytes()).decode(),
        contradiction=contradiction(Path(a.review).expanduser(), Path(a.review_pdf).expanduser()),
    )
    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    html = tpl.replace("/*DEMO_DATA*/", demo_data).replace("/*STORY_DATA*/", json.dumps(data, ensure_ascii=False))
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"wrote {a.out} ({len(html) // 1024} KB): {len(data['explorer']['glyphs'])} explorer glyphs, contradiction {data['contradiction'] and data['contradiction']['readings']}")


if __name__ == "__main__":
    main()
