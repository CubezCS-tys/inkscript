"""The same document built with letter cutting switched OFF — the free baseline, as a real PDF.

    python build_baseline.py <stem> <azure_dir> <out_dir> [--scan DIR] [--frontpage DIR]

D7's baseline is what a viewer does with an UNCUT glyph: it slices the word's width evenly, one part per
character. There is no need to simulate that — build the document without the letters pass and every word is
one glyph again, so Chrome does the equal slicing itself. Then the two PDFs can be dragged side by side and
the comparison is between two real text layers instead of two pictures of one.

`native.LETTERS` is set here rather than edited in `src/`, so the package is untouched.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
import inkscript.pdf.native as native


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stem"); ap.add_argument("azure_dir"); ap.add_argument("out_dir")
    ap.add_argument("--scan", default=None)
    ap.add_argument("--frontpage", default=None)
    a = ap.parse_args()

    ad = Path(a.azure_dir).expanduser(); out = Path(a.out_dir).expanduser()
    scan = (Path(a.scan) / f"{a.stem}.pdf") if a.scan else ad / a.stem / f"{a.stem}.pdf"
    gem = (Path(a.frontpage) / f"{a.stem}.gemini.p1.md") if a.frontpage else None

    native.LETTERS = False                      # the whole point: words stay one glyph, the viewer slices them
    r = native.build_document(a.stem, ad, scan, gem, out, True, 0.0)
    out.mkdir(parents=True, exist_ok=True)
    (out / "native_pdf_report.json").write_text(json.dumps([r], ensure_ascii=False, indent=1), encoding="utf-8")
    g = sum(p.get("glyphs", 0) for p in r["pages"])
    print(f"{a.stem}: {len(r['pages'])} pages, {g} glyphs (no letter cutting) -> {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
