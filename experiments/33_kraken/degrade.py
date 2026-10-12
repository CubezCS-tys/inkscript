"""Scan-like copy of a clean rendered line: slight skew, lost resolution, blur, ink spread or thinning, paper tint,
uneven light, noise, specks, JPEG. Deterministic for a given seed."""
import io, random
import numpy as np
from PIL import Image, ImageFilter


def degrade(im: Image.Image, seed: int, skew: bool = True) -> Image.Image:
    r = random.Random(seed); g = im.convert("L")
    w, h = g.size
    if r.random() < 0.8 and skew:                                      # skew (off for whole pages: gold boxes stay put)
        g = g.rotate(r.uniform(-0.9, 0.9), resample=Image.BICUBIC, expand=False, fillcolor=255)
    if r.random() < 0.7:                                               # print/scan resolution 150-240 dpi
        f = r.uniform(0.5, 0.8)
        g = g.resize((max(8, int(w * f)), max(8, int(h * f))), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    p = r.random()
    if p < 0.3:
        g = g.filter(ImageFilter.MinFilter(3))                         # ink spread (heavier strokes)
    elif p < 0.45:
        g = g.filter(ImageFilter.MaxFilter(3))                         # thin, broken strokes
    g = g.filter(ImageFilter.GaussianBlur(r.uniform(0.3, 1.2)))
    a = np.asarray(g, dtype=np.float32) / 255.0                        # 1 = paper, 0 = ink
    paper = r.uniform(185, 245); ink = r.uniform(10, 80)
    grad = np.linspace(0, 1, w, dtype=np.float32)[None, :] * r.uniform(-25, 25)   # uneven light across the line
    out = ink + (paper - ink) * a + grad
    out += np.random.default_rng(seed).normal(0, r.uniform(3, 14), out.shape)
    if r.random() < 0.4:                                               # specks
        rng = np.random.default_rng(seed + 1); n = int(w * h * r.uniform(2e-5, 2e-4))
        ys, xs = rng.integers(0, h, n), rng.integers(0, w, n); out[ys, xs] = ink
    g = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
    buf = io.BytesIO(); g.save(buf, "JPEG", quality=r.randint(35, 85)); buf.seek(0)
    return Image.open(buf).convert("L")
