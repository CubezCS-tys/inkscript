"""Experiment 87, rung 0 (synthetic): lines rendered from the FONT FILES' own outlines (exp 79's synth79.render,
HarfBuzz-shaped, 96 px, 56-66 px per em), so the true letters and the true face are known; the writer then fits
them with that face's stroke programs (and with AlQalam's, as a stranger).  -> out/data/synth.jsonl,
out/data/crops/synth/.  Texts: exp 78's corpus (no held-out text), lines 20-70 characters."""
import gzip, json, random, sys
from pathlib import Path
import cv2
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "82_path_accuracy"))
import path82  # noqa: F401
import synth79 as S
import fontprog87 as FP
import run87 as R
import writer87 as W

S.H = 96
rng = random.Random(870)
T = []
with gzip.open(HERE.parent / "78_synthetic_lines/out/text/text78.jsonl.gz", "rt", encoding="utf-8") as f:
    for i, l in enumerate(f):
        if i % 199 == 11:
            t = json.loads(l)["t"].strip()
            if 20 <= len(t) <= 70 and R.OK_SYN.match(t):
                T.append(t)
        if len(T) >= 4000:
            break
fonts = FP.MODERN + FP.TRACED
out = HERE / "out/data/crops/synth"
out.mkdir(parents=True, exist_ok=True)
rows = []
k = 0
for t in T:
    font = fonts[k % len(fonts)]
    lib = "font:" + FP.name_of(font)
    if not R.lib_ok(lib, t) or not S.covers(FP.FONTS / font, t):
        continue
    if any(g.get("missing") for g in W.font_shape(t, lib[5:])[0]):
        k += 1
        continue
    px = round(61.0 * rng.uniform(0.92, 1.08), 1)
    grey, _, ink = S.render(t, FP.FONTS / font, px_per_em=px)
    key = f"synth{k:04d}"
    cv2.imwrite(str(out / f"{key}.png"), grey)
    rows.append(dict(key=key, text=t, lib=lib, px=px, W=grey.shape[1], era="synthetic"))
    k += 1
    if k >= 240:
        break
with open(HERE / "out/data/synth.jsonl", "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows))
