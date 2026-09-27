"""Judge the two cuts in the real PDFs, not in pictures of them.

    python ab.py <ours_dir> <baseline_dir> <stem> [--limit 60]

Two PDFs of the same document: one with letters cut along the pen path, one built with `native.LETTERS = False`
so every word is a single glyph and the viewer slices it evenly — D7's baseline, produced rather than
simulated. Which pane holds which is a coin flip, written only into `mapping.json`.

A word list drives both viewers: clicking a word sends both panes to that page and position, so the same ink
is on screen in both. Drag across it in each, then judge. This exists because a rendered band with a tint over
it is a worse instrument than the thing itself — the objection was the owner's, and it was right.
"""
from __future__ import annotations
import argparse, json, os, random, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from inkscript.text import MARKS
DPI = 300
LIG = ("لا", "لأ", "لإ", "لآ")


def n_letters(t: str) -> int:
    t = MARKS.sub("", t); t = re.sub(r"[^؀-ۿ]", "", t)
    for l in LIG: t = t.replace(l, "L")
    return len(t)


def link(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    os.symlink(src.resolve(), dst)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ours"); ap.add_argument("baseline"); ap.add_argument("stem")
    ap.add_argument("--limit", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    ours, base = Path(a.ours), Path(a.baseline)
    out = Path(a.out) if a.out else Path(__file__).parent / "out" / "ab"
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    flip = rng.random() < 0.5                       # A is ours, or A is the baseline
    link(ours / f"{a.stem}_vector.pdf", out / "A.pdf" if not flip else out / "B.pdf")
    link(base / f"{a.stem}_vector.pdf", out / "B.pdf" if not flip else out / "A.pdf")
    (out / "mapping.json").write_text(json.dumps(
        {"stem": a.stem, "seed": a.seed, "A": "baseline" if flip else "pen path",
         "B": "pen path" if flip else "baseline"}, indent=1), encoding="utf-8")

    shapes = json.load(open(ours / f"{a.stem}.shapes.json"))
    rep = {r["doc"]: r for r in json.load(open(ours / "native_pdf_report.json"))}[a.stem]
    cut_pages = {p["page"] for p in rep["pages"] if p.get("glyphs")}
    words = []
    for p in shapes["placements"]:
        if p.get("rot") or p["page"] not in cut_pages:
            continue
        t = p["text"].strip()
        if n_letters(t) < 4 or MARKS.search(t):
            continue
        x0, y0, x1, y1 = p["box"]
        if x1 - x0 < 40:
            continue
        words.append(dict(text=t, page=p["page"], letters=n_letters(t),
                          # PDF points from the page's top-left, which is what the viewer's zoom fragment wants
                          left=round(x0 * 72 / DPI - 40, 1), top=round(y0 * 72 / DPI - 40, 1)))
    rng.shuffle(words); words = words[:a.limit]
    for i, w in enumerate(words): w["i"] = i

    tpl = (Path(__file__).parent / "ab.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(
        tpl.replace("__DATA__", json.dumps(dict(stem=a.stem, seed=a.seed, words=words), ensure_ascii=False)),
        encoding="utf-8")
    print(f"{len(words)} words -> {(out / 'index.html').resolve()}")
    print(f"  serve:  python3 -m http.server 8735 --bind 127.0.0.1 --directory {out.resolve()}")
    print(f"  open:   http://127.0.0.1:8735/")
    print(f"  (which pane is which is in {out / 'mapping.json'} — do not open it until you have judged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
