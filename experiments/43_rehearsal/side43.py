"""Experiment 43: scan beside our Layout view, one JPEG a page (for looking at a change next to the print).

    python3 side43.py --views out/v2_55/views --stem 0493-000-029-001 --pages 1 4 --out out/v2_55/shots/after
writes OUT/side_<stem4>_pNNN.jpg (scan left, ours right). Layout screenshots by shots43.py in experiment 40's
Playwright venv. No model calls.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
PW = HERE.parent / "40_gemini4_vlm" / "out" / "venv" / "bin" / "python"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", required=True)
    ap.add_argument("--stem", required=True)
    ap.add_argument("--pages", nargs="+", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--height", type=int, default=1400)
    a = ap.parse_args()
    views, out = Path(a.views).resolve(), Path(a.out).resolve()
    ours = out / "ours"
    ours.mkdir(parents=True, exist_ok=True)
    html = views / "mirror" / f"{a.stem}.html"
    subprocess.run([str(PW), str(HERE / "shots43.py"), str(ours / a.stem), str(html)] + [str(p) for p in a.pages],
                   check=True, capture_output=True)
    for p in a.pages:
        sc = Image.open(views / "scans" / a.stem / f"p{p:03d}.jpg").convert("RGB")
        us = Image.open(ours / f"{a.stem}_p{p:03d}.png").convert("RGB")
        h = a.height
        sc = sc.resize((round(sc.width * h / sc.height), h))
        us = us.resize((round(us.width * h / us.height), h))
        o = Image.new("RGB", (sc.width + us.width + 20, h), "white")
        o.paste(sc, (0, 0))
        o.paste(us, (sc.width + 20, 0))
        f = out / f"side_{a.stem[:4]}_p{p:03d}.jpg"
        o.save(f, quality=85)
        print(f)


if __name__ == "__main__":
    main()
