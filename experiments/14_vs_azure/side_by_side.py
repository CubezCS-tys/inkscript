"""The two PDFs themselves, side by side in the browser's own viewer — so you can drag, select and copy in
each exactly as you would comparing the files by hand.

    python side_by_side.py <azure_dir> <ours_dir> [--out DIR]

Builds a folder with an index.html and symlinks to both sets of PDFs (nothing is copied). Left pane is the
Azure searchable PDF, right pane ours. Both are the SAME scan with an invisible text layer over it, so they
look identical — the difference only appears when you select. A toggle swaps our side to the vector edition,
which has no scan under it at all.
"""
from __future__ import annotations
import argparse, json, os
from pathlib import Path


def link(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    os.symlink(src.resolve(), dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("azure"); ap.add_argument("ours")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    az, ours = Path(a.azure), Path(a.ours)
    out = Path(a.out) if a.out else Path(__file__).parent / "out" / "side_by_side"
    out.mkdir(parents=True, exist_ok=True)

    reps = {r["doc"]: r for r in json.load(open(ours / "native_pdf_report.json"))}
    docs = []
    for stem in sorted(reps):
        ap_ = az / stem / f"{stem}.pdf"
        op = ours / f"{stem}.pdf"
        vp = ours / f"{stem}_vector.pdf"
        if not (ap_.exists() and op.exists()):
            continue
        link(ap_, out / "azure" / f"{stem}.pdf")
        link(op, out / "ours" / f"{stem}.pdf")
        if vp.exists():
            link(vp, out / "ours" / f"{stem}_vector.pdf")
        pages = [p["page"] for p in reps[stem]["pages"] if p.get("glyphs")]
        docs.append(dict(stem=stem, start=pages[len(pages) // 2] if pages else 1,
                         pages=len(reps[stem]["pages"]), vector=vp.exists()))

    tpl = (Path(__file__).parent / "side_by_side.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(tpl.replace("__DATA__", json.dumps(docs, ensure_ascii=False)), encoding="utf-8")
    print(f"{len(docs)} documents -> {(out / 'index.html').resolve()}")
    print("Chrome will not load a PDF into a frame from file://, so serve the folder:")
    print(f"  python3 -m http.server 8733 --bind 127.0.0.1 --directory {out.resolve()}")
    print("  then open http://127.0.0.1:8733/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
