"""Experiment 78, step 3: render synthetic printed Arabic lines and cut them EXACTLY as experiment 77 cuts real lines.

    python render78.py sheet  --n 100 --out sheet.png                      a contact sheet (for looking)
    python render78.py shards --n N --workers W --out DIR [--split train]  tar shards <key>.jpg/<key>.txt + manifest

Needs only Pillow (with raqm: HarfBuzz shaping + FriBiDi), numpy, opencv; runs on the rented GPU host's own CPUs.
Inputs (relative to --root, default this folder's out/): fonts/ (OFL fonts) and fonts/traced/ (typefaces traced from
our own old scans by experiment 11), text/text78.jsonl.gz, bg/paper-*.jpg and bg/through-*.jpg.

One line:
  1. text + font (weighted; the font must cover every character, else another font is tried), size and weight;
  2. the line with a line of other text above and below at a random leading (real crops show their neighbours'
     descenders and dots), shaped by raqm (direction rtl, language ar);
  3. damage on the ink: spread or erosion, broken strokes, fading, blur;
     paper: a real blank patch from our scans or plain paper; show-through: a mirrored real text patch, faint;
     slight skew left in the box, curl (baseline wave), noise, bilevel thresholding, low resolution, scanner JPEG;
  4. an Azure-like polygon (calibrated on experiment 77's crops: baseline 62% down the box, an alef 48% of its
     height), then common78.cut_line (= experiment 77's cut: pad 0.22 / 0.35, height 48, JPEG q80).
The label is the text (clean_label); superscript note calls are drawn as ¹²³ but labelled as plain digits, as the
owner's truth writes them.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import io
import json
import math
import os
import random
import re
import tarfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, features

from common78 import H, clean_label, cut_line, encode

assert features.check("raqm"), "Pillow without raqm cannot shape Arabic"

HERE = Path(__file__).resolve().parent
NJ = "اأإآدذرزوؤةىء"      # letters that do not join to the next one
SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")

# family -> (weight in the mix, variable-weight range or None)
FONTS = {
    "amiri_Amiri-Regular.ttf": (10, None), "amiri_Amiri-Bold.ttf": (4, None),
    "scheherazadenew_ScheherazadeNew-Regular.ttf": (7, None), "scheherazadenew_ScheherazadeNew-Bold.ttf": (3, None),
    "notonaskharabic_NotoNaskhArabic[wght].ttf": (10, (400, 700)),
    "lateef_Lateef-Regular.ttf": (4, None), "lateef_Lateef-Bold.ttf": (2, None),
    "markazitext_MarkaziText[wght].ttf": (5, (400, 700)), "harmattan_Harmattan-Regular.ttf": (3, None),
    "mirza_Mirza-Regular.ttf": (4, None),
    "notosansarabic_NotoSansArabic[wdth_wght].ttf": (5, (400, 800)), "ibmplexsansarabic_IBMPlexSansArabic-Regular.ttf": (4, None),
    "vazirmatn_Vazirmatn[wght].ttf": (3, (400, 800)), "cairo_Cairo[slnt_wght].ttf": (2, None),
    "tajawal_Tajawal-Regular.ttf": (2, None), "almarai_Almarai-Regular.ttf": (2, None),
    "readexpro_ReadexPro[HEXP_wght].ttf": (1, None), "elmessiri_ElMessiri[wght].ttf": (1, None),
    "notokufiarabic_NotoKufiArabic[wght].ttf": (1, None), "reemkufi_ReemKufi[wght].ttf": (0.5, None),
    "kufam_Kufam[wght].ttf": (0.5, None), "arefruqaa_ArefRuqaa-Regular.ttf": (0.7, None),
    "alkalami_Alkalami-Regular.ttf": (0.3, None),
}
# Latin-only lines (English/French abstracts and references: ~30% of experiment 77's lines) also use these
LATIN_FONTS = {"tinos_Tinos-Regular.ttf": 6, "tinos_Tinos-Bold.ttf": 2, "tinos_Tinos-Italic.ttf": 1.5,
               "notolatin_NotoSerif-Regular.ttf": 2, "notolatin_NotoSerif-Bold.ttf": 1, "notolatin_NotoSerif-Italic.ttf": 0.5,
               "notolatin_NotoSans-Regular.ttf": 2, "notolatin_NotoSans-Bold.ttf": 1,
               "sourceserif4_SourceSerif4[opsz_wght].ttf": 2, "crimsonpro_CrimsonPro[wght].ttf": 1,
               "courierprime_CourierPrime-Regular.ttf": 0.7}
LATIN_EXTRA = 0.12          # extra share of lines drawn from the Latin-only texts
ARL = re.compile("[\u0620-\u064A\u0671-\u06D3]")
VERSION = os.environ.get("SYN78_VERSION", "v1")   # v2 (after the synthetic-only reader read kashida as س):
KASHIDA = 0.3 if VERSION == "v2" else 0.0          #   stretched joins in 30% of Arabic lines,
OLD_TEXT = 0.4 if VERSION == "v2" else 0.0         #   40% of lines from experiment 80's old print (text80),
#                                                      paper from bg80 too, and the traced fonts of experiment 80
TRACED_SHARE = 0.2 if VERSION == "v2" else 0.12        # share of lines in the typefaces traced from our own scans (when present)
PAD_FRAC_TOP = 0.71         # baseline position down the polygon (calibrated so the darkest row lands at 28 of 48, as in experiment 77's crops)
ALEF_FRAC = 0.51            # an alef's height as a share of the polygon height (crops: ink top ~12, darkest row 28)
XSTRETCH = (1.0, 1.28)      # horizontal stretch: real crops have ~11.6 px a character at height 48, the fonts ~10.1


def cmap_of(path: str) -> set[int]:
    from fontTools.ttLib import TTFont
    f = TTFont(path, lazy=True)
    return set(f.getBestCmap() or {})


class Fonts:
    def __init__(self, root: Path):
        self.items = []          # (path, weight, wrange, cmap, traced)
        self.iso_bad = {}
        for name, (w, wr) in FONTS.items():
            p = root / "fonts" / name
            if p.exists():
                self.items.append((str(p), w, wr, cmap_of(str(p)), False))
        self.latin = []
        for name, w in LATIN_FONTS.items():
            p = root / "fonts" / name
            if p.exists():
                self.latin.append((str(p), w, None, cmap_of(str(p)), False))
        tr = sorted(glob.glob(str(root / "fonts/traced/*.ttf")))
        ex = json.loads((root / "fonts/traced/exclude.json").read_text(encoding="utf-8")) if tr else {}
        for p in tr:
            name = os.path.basename(p)[:-4]
            if name not in ex:                                         # not looked at yet: never used
                continue
            e = ex.get(name, {})
            if e == "DROP":
                continue
            cm = cmap_of(p) - {ord(c) for c in e.get("chars", "")}   # characters whose traced glyph is wrong
            iso = e.get("iso", "")                                     # letters whose ISOLATED form is wrong
            self.iso_bad[p] = re.compile(rf"(?:(?<![\u0621-\u064A])|(?<=[{NJ}]))[{iso}](?![\u0621-\u064A])") if iso else None
            self.items.append((p, 0, None, cm, True))
        self.plain = [x for x in self.items if not x[4]]
        self.traced = [x for x in self.items if x[4]]
        self._cache = {}

    def covers(self, item, text: str) -> bool:
        cm = item[3]
        if item[4] and self.iso_bad.get(item[0]) is not None and self.iso_bad[item[0]].search(text):
            return False
        return all((ord(c) in cm) or c == " " for c in text)

    def font(self, item, size: int, wght: int | None):
        k = (item[0], size, wght)
        f = self._cache.get(k)
        if f is None:
            f = ImageFont.truetype(item[0], size, layout_engine=ImageFont.Layout.RAQM)
            if wght is not None:
                try:
                    axes = f.get_variation_axes()
                    f.set_variation_by_axes([wght if a.get("name") in (b"Weight", "Weight") else a.get("default", a["minimum"])
                                             for a in axes])
                except Exception:  # noqa: BLE001
                    pass
            if len(self._cache) > 400:
                self._cache.clear()
            self._cache[k] = f
        return f

    def pick(self, rng: random.Random, text: str):
        if self.traced and rng.random() < TRACED_SHARE:
            pool = self.traced
            ok = [x for x in pool if self.covers(x, text)]
            if ok:
                return rng.choice(ok)
            return None
        ok = [x for x in self.plain if self.covers(x, text)]
        if not ok:
            return None
        return rng.choices(ok, weights=[x[1] for x in ok])[0]


class Texts(list):
    latin: list
    old: list


def load_texts(root: Path) -> list[str]:
    with gzip.open(root / "text/text78.jsonl.gz", "rt", encoding="utf-8") as f:
        t = Texts(json.loads(l)["t"] for l in f)
    t.old = []
    if OLD_TEXT and (root / "text/text80.jsonl.gz").exists():
        with gzip.open(root / "text/text80.jsonl.gz", "rt", encoding="utf-8") as f:
            t.old = [json.loads(l)["t"] for l in f]
    return t


def draw_text_choice(texts, rng: random.Random) -> str:
    if texts.old and rng.random() < OLD_TEXT:
        return texts.old[rng.randrange(len(texts.old))]
    if texts.latin and rng.random() < LATIN_EXTRA:
        return texts.latin[rng.randrange(len(texts.latin))]
    return texts[rng.randrange(len(texts))]


def load_imgs(pattern: str, limit: int = 4000) -> list[np.ndarray]:
    fs = sorted(glob.glob(pattern))[:limit]
    return [cv2.imread(f, cv2.IMREAD_GRAYSCALE) for f in fs]


# ------------------------------------------------------------------------------------------------ drawing

def kashida(text: str, rng: random.Random) -> str:
    """Tatweel between two joined letters in a few words (justified print stretches them); clean_label drops it."""
    out = []
    for w in text.split(" "):
        if len(w) > 2 and rng.random() < 0.35:
            pos = [i for i in range(len(w) - 1) if "\u0628" <= w[i] <= "\u064A" and w[i] not in NJ
                   and "\u0621" <= w[i + 1] <= "\u064A"]
            if pos:
                i = rng.choice(pos)
                w = w[:i + 1] + "\u0640" * rng.choice((1, 2, 3, 3, 4, 5, 6, 8)) + w[i + 1:]
        out.append(w)
    return " ".join(out)


def direction(text: str) -> str:
    """A line with an Arabic letter is laid out right to left; a line without one left to right (as printed, and as
    experiment 77's to_visual reads it)."""
    return "rtl" if ARL.search(text) else "ltr"


def draw_text(canvas: Image.Image, xr: float, yb: float, text: str, font) -> None:
    d = direction(text)
    ImageDraw.Draw(canvas).text((xr, yb), text, font=font, fill=255, anchor="rs", direction=d,
                                language="ar" if d == "rtl" else "en")


def smooth_noise(shape, scale: float, rng: np.random.Generator) -> np.ndarray:
    h, w = shape
    sh, sw = max(2, int(h / scale)), max(2, int(w / scale))
    n = rng.random((sh, sw)).astype(np.float32)
    return cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)


def paper_patch(shape, papers, rng: random.Random, nrng) -> np.ndarray:
    h, w = shape
    r = rng.random()
    if r < 0.38 or not papers:
        base = np.full(shape, rng.uniform(235, 255) if rng.random() < 0.7 else 255.0, np.float32)
        if rng.random() < 0.5:
            base -= smooth_noise(shape, rng.uniform(20, 120), nrng) * rng.uniform(0, 18)
        return base
    p = papers[rng.randrange(len(papers))]
    if rng.random() < 0.5:
        p = p[:, ::-1]
    reps_y, reps_x = math.ceil(h / p.shape[0]), math.ceil(w / p.shape[1])
    t = np.tile(p, (reps_y, reps_x))
    y, x = rng.randint(0, t.shape[0] - h), rng.randint(0, t.shape[1] - w)
    return t[y:y + h, x:x + w].astype(np.float32)


def render_one(text: str, fonts: Fonts, texts: list[str], papers, throughs, rng: random.Random):
    """-> (crop uint8 HxW, label, info) or None."""
    if fonts.traced and rng.random() < TRACED_SHARE:
        item = rng.choice(fonts.traced)      # a traced typeface sets only text it covers (Arabic letters, no digits)
        for _ in range(80):
            if fonts.covers(item, text):
                break
            text = texts[rng.randrange(len(texts))]
        else:
            return None
    else:
        pool = fonts.plain if (ARL.search(text) or rng.random() < 0.3) else fonts.latin
        ok = [x for x in pool if fonts.covers(x, text)]
        if not ok:
            return None
        item = rng.choices(ok, weights=[x[1] for x in ok])[0]
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    alef_px = rng.uniform(11, 26)                    # an alef's height at "scan" resolution (250 dpi: ~11-26 px)
    # size from the font's own alef
    f0 = fonts.font(item, 100, None)
    try:
        ab = f0.getbbox("ا" if 0x627 in item[3] else "l", anchor="ls")   # Latin-only fonts: the l ascender
        a100 = max(20.0, -ab[1])
    except Exception:  # noqa: BLE001
        a100 = 65.0
    size = max(8, int(round(100 * alef_px / a100)))
    wght = rng.randint(*item[2]) if item[2] else None
    font = fonts.font(item, size, wght)
    shown = text
    if KASHIDA and ARL.search(text) and 0x640 in item[3] and rng.random() < KASHIDA:
        shown = kashida(text, rng)                   # stretched joins, as justified old print; the label has none
    if rng.random() < 0.3:                           # superscript note calls: a Latin digit glued to a word
        shown = __import__("re").sub(r"(?<=[ء-ي\.،])([0-9])(?=\s|$)", lambda m: m.group(1).translate(SUP), text)
        if not fonts.covers(item, shown):
            shown = text
    try:
        dd = direction(shown)
        l, t, r, b = font.getbbox(shown, anchor="rs", direction=dd, language="ar" if dd == "rtl" else "en")
    except Exception:  # noqa: BLE001
        return None
    tw = r - l
    if tw <= 2:
        return None
    ph = alef_px / ALEF_FRAC * rng.uniform(0.93, 1.07)  # polygon height
    lead = ph * rng.uniform(1.0, 1.7)                   # baseline to baseline
    padx = int(ph * 1.5) + 20
    Wc = int(tw + 2 * padx)
    Hc = int(3 * lead + ph * 2)
    if Wc > 6000:
        return None
    ink = Image.new("L", (Wc, Hc), 0)
    xr = Wc - padx
    yb = Hc / 2 + ph * (PAD_FRAC_TOP - 0.5)
    draw_text(ink, xr, yb, shown, font)
    for side in (-1, 1):                             # neighbours above and below
        if rng.random() < 0.85:
            nt = texts[rng.randrange(len(texts))]
            if fonts.covers(item, nt):
                draw_text(ink, xr + rng.uniform(-ph, ph) * (rng.random() < 0.3), yb + side * lead, nt, font)
    a = np.asarray(ink, np.float32) / 255.0
    # ---- ink damage
    k = max(1, int(round(alef_px / 14)))
    r_ = rng.random()
    if r_ < 0.4:
        a = cv2.dilate(a, np.ones((k + rng.randint(0, 1), k), np.uint8))                     # ink spread
    elif r_ < 0.5:
        a = cv2.erode(a, np.ones((k, k), np.uint8)) if alef_px > 14 else a * 0.85           # thin, eroded strokes
    if rng.random() < 0.3:                                                                    # broken strokes
        m = smooth_noise(a.shape, rng.uniform(1.5, 4.0), nrng)
        a = a * (m > rng.uniform(0.08, 0.3))
    if rng.random() < 0.2:                                                                    # faded / uneven ink
        a = a * (rng.uniform(0.55, 1.0) + rng.uniform(0, 0.4) * smooth_noise(a.shape, rng.uniform(30, 200), nrng))
    a = np.clip(a, 0, 1)
    if rng.random() < 0.35:
        a = cv2.GaussianBlur(a, (0, 0), rng.uniform(0.3, 0.9))
    a = np.clip(a * rng.uniform(1.2, 2.0), 0, 1)                                              # solid ink cores
    # ---- paper, ink, show-through
    paper = paper_patch(a.shape, papers, rng, nrng)
    inkv = rng.uniform(0, 25) if rng.random() < 0.85 else rng.uniform(25, 100)
    img = paper * (1 - a) + inkv * a
    if throughs and rng.random() < 0.3:
        th = throughs[rng.randrange(len(throughs))].astype(np.float32)
        sc = ph * 1.44 / th.shape[0] * rng.uniform(1.5, 3.0)
        th = cv2.resize(th, (max(2, int(th.shape[1] * sc)), max(2, int(th.shape[0] * sc))))
        th = np.tile(th, (math.ceil(Hc / th.shape[0]), math.ceil(Wc / th.shape[1])))[:Hc, :Wc]
        th = cv2.GaussianBlur(th, (0, 0), rng.uniform(1.0, 2.5))
        img = img * (1 - rng.uniform(0.06, 0.3) * (1 - th / 255.0))
    # ---- geometry: curl and a residual skew
    if rng.random() < 0.3:
        amp, per = rng.uniform(0.5, 0.06 * ph + 0.5), rng.uniform(300, 2000)
        ph0 = rng.uniform(0, 6.3)
        xs = np.arange(Wc, dtype=np.float32)
        mx = np.tile(xs, (Hc, 1))
        my = np.tile(np.arange(Hc, dtype=np.float32)[:, None], (1, Wc)) + amp * np.sin(xs / per * 6.28 + ph0)[None, :]
        img = cv2.remap(img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    ang = math.radians(rng.gauss(0, 0.35))
    # ---- scanner: noise, bilevel, low resolution, JPEG
    if rng.random() < 0.4:
        img = img + nrng.normal(0, rng.uniform(2, 14), img.shape).astype(np.float32)
    if rng.random() < 0.08:                                                                   # specks
        sp = nrng.random(img.shape) < rng.uniform(0.0003, 0.002)
        img[sp] = rng.uniform(0, 80)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if rng.random() < 0.25:                                                                   # bilevel scan
        thr = rng.uniform(110, 190)
        img = np.where(img < thr, 0, 255).astype(np.uint8)
        if rng.random() < 0.5:
            img = cv2.GaussianBlur(img, (0, 0), 0.5)
    if rng.random() < 0.35:                                                                   # low resolution
        f = rng.uniform(0.45, 0.9)
        small = cv2.resize(img, (max(2, int(Wc * f)), max(2, int(Hc * f))), interpolation=cv2.INTER_AREA)
        img = cv2.resize(small, (Wc, Hc), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.5:
        ok, bb = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(25, 90)])
        img = cv2.imdecode(bb, cv2.IMREAD_GRAYSCALE)
    # ---- the Azure-like polygon around the middle line, then experiment 77's cut
    sx_ = rng.uniform(*XSTRETCH)
    img = cv2.resize(img, (int(Wc * sx_), Hc), interpolation=cv2.INTER_LINEAR)
    top = yb - PAD_FRAC_TOP * ph + rng.gauss(0, 0.03 * ph)
    x0 = (xr - tw - rng.uniform(0, 0.15) * ph) * sx_
    x1 = (xr + rng.uniform(0, 0.15) * ph) * sx_
    cy = top + ph / 2
    cx = (x0 + x1) / 2
    hw = (x1 - x0) / 2
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((-hw, -ph / 2), (hw, -ph / 2), (hw, ph / 2), (-hw, ph / 2)):
        pts += [cx + dx * ca - dy * sa, cy + dx * sa + dy * ca]
    crop, info = cut_line(img, pts, 1.0, 1.0)
    if crop is None:
        return None
    return crop, clean_label(text), dict(font=os.path.basename(item[0]), traced=item[4], alef=round(alef_px, 1),
                                         W=info["W"])


# ------------------------------------------------------------------------------------------------ commands

def setup(root: Path):
    fonts = Fonts(root)
    texts = load_texts(root)
    texts.latin = [t for t in texts if not ARL.search(t) and re.search("[A-Za-z]{2}", t)]
    papers = load_imgs(str(root / "bg/paper-*.jpg"))
    throughs = load_imgs(str(root / "bg/through-*.jpg"))
    if VERSION == "v2":
        papers += load_imgs(str(root / "bg80/paper-*.jpg"))
        throughs += load_imgs(str(root / "bg80/through-*.jpg"))
    return fonts, texts, papers, throughs


def sheet(a):
    root = Path(a.root)
    fonts, texts, papers, throughs = setup(root)
    rng = random.Random(a.seed)
    rows = []
    while len(rows) < a.n:
        r = render_one(draw_text_choice(texts, rng), fonts, texts, papers, throughs, rng)
        if r:
            rows.append(r)
    W = 1400
    out = np.full((H * len(rows), W), 255, np.uint8)
    for k, (c, _, _) in enumerate(rows):
        c = c[:, :W]
        out[H * k:H * k + H, W - c.shape[1]:] = c
    cv2.imwrite(a.out, out)
    with open(a.out + ".labels.txt", "w", encoding="utf-8") as f:
        for c, lab, info in rows:
            f.write(json.dumps(dict(label=lab, **info), ensure_ascii=False) + "\n")


def _worker(args):
    wid, n, root, out, split, seed = args
    import cv2 as _cv2
    _cv2.setNumThreads(1)
    root = Path(root)
    fonts, texts, papers, throughs = setup(root)
    rng = random.Random(seed * 1000 + wid)
    shard, k, tar = 0, 0, None
    mf = open(os.path.join(out, f"manifest-{split}-{wid}.jsonl"), "w", encoding="utf-8")
    t0 = time.time()
    done = fails = 0
    while done < n:
        text = draw_text_choice(texts, rng)
        try:
            r = render_one(text, fonts, texts, papers, throughs, rng)
        except Exception:  # noqa: BLE001
            r = None
        if r is None:
            fails += 1
            continue
        crop, lab, info = r
        if tar is None or k >= 5000:
            if tar:
                tar.close()
            tar = tarfile.open(os.path.join(out, f"{split}-{wid}-{shard:03d}.tar"), "w")
            shard += 1
            k = 0
        key = f"syn{wid:02d}_{done:07d}"
        for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", lab.encode("utf-8"))):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))
        mf.write(json.dumps(dict(key=key, label=lab, **info), ensure_ascii=False) + "\n")
        k += 1
        done += 1
        if done % 5000 == 0:
            print(f"w{wid} {done}/{n} {done / (time.time() - t0):.0f}/s fails {fails}", flush=True)
    if tar:
        tar.close()
    mf.close()
    return dict(wid=wid, done=done, fails=fails, s=round(time.time() - t0))


def shards(a):
    from multiprocessing import Pool
    os.makedirs(a.out, exist_ok=True)
    per = a.n // a.workers
    jobs = [(w, per, a.root, a.out, a.split, a.seed) for w in range(a.workers)]
    with Pool(a.workers) as p:
        res = p.map(_worker, jobs)
    print(json.dumps(res))
    with open(os.path.join(a.out, f"render-{a.split}.json"), "w") as f:
        json.dump(res, f)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--out")
    p.add_argument("--root", default=str(HERE / "out"))
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--split", default="train")
    p.add_argument("--seed", type=int, default=78)
    a = p.parse_args()
    {"sheet": sheet, "shards": shards}[a.cmd](a)
