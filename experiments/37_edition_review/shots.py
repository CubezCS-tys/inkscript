"""Experiment 37: render what a reader sees, for review by eye. For each document of experiment 35:
  out/shots/<id>/pNN.jpg   the scan page (left) beside the same page of the layout-faithful PDF (right)
  out/shots/<id>/onecol-NN.jpg   each page of the one-column PDF
    python3 experiments/37_edition_review/shots.py [--workers 4]
"""
import argparse, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ED = ROOT / "experiments/35_edition/out/editions"
OUT = Path(__file__).with_name("out") / "shots"
H = 1400   # height of each half of a side-by-side, in pixels


def render(pdf: Path, tmp: Path, dpi: int) -> list[Path]:
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", str(pdf), str(tmp / "p")], check=True)
    return sorted(tmp.glob("p-*.png"), key=lambda p: int(p.stem.split("-")[1]))


def fit(im: Image.Image) -> Image.Image:
    return im.convert("RGB").resize((max(1, round(im.width * H / im.height)), H), Image.LANCZOS)


def one(doc: str) -> str:
    d, out = ED / doc, OUT / doc
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); (t / "l").mkdir(); (t / "o").mkdir()
        lay = render(d / f"{doc}.layout.pdf", t / "l", 110)
        for i, lp in enumerate(lay, 1):
            scan = d / "scan" / f"p{i}.jpg"
            a = fit(Image.open(scan)) if scan.exists() else Image.new("RGB", (900, H), "white")
            b = fit(Image.open(lp))
            c = Image.new("RGB", (a.width + b.width + 24, H), (120, 120, 120))
            c.paste(a, (0, 0)); c.paste(b, (a.width + 24, 0))
            c.save(out / f"p{i:02d}.jpg", quality=80)
        for i, op in enumerate(render(d / f"{doc}.onecol.pdf", t / "o", 90), 1):
            fit(Image.open(op)).save(out / f"onecol-{i:02d}.jpg", quality=80)
    return f"{doc} {len(lay)}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--workers", type=int, default=4); a = ap.parse_args()
    docs = sorted(p.name for p in ED.iterdir() if (p / f"{p.name}.layout.pdf").exists())
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(one, docs):
            print(r, flush=True)
