"""Experiment 84, step B2b: synthetic DISPLAY-FACE lines (running headers, mastheads, titles), often white on a dark
band, cut exactly as experiment 77 cuts real lines (experiment 78's render78 / common78 helpers, imported unchanged).

    python render84.py sheet  --n 60 --out sheet.png                       a contact sheet (for looking)
    python render84.py shards --n N --workers W --out DIR [--split train-syn84]

Inputs (--root, default this folder's out/): fonts/ (display faces; licences in fonts/LICENCES84.json),
text/display84.jsonl.gz (text84.py: training-pool journal names, headers, titles), and --root78 (experiment 78's out/:
its body fonts for the plain parts, text78 for neighbouring lines, real paper patches).

One line:
  1. text from display84; a display face that covers it (weighted); in 40% of header lines the journal's name is
     set in the display face and the rest (issue, date, page) in a plain bold sans or naskh, as printed headers do;
  2. an alef 14-40 px high at scan resolution; sometimes a vertical rule by a page number; neighbours in 20%;
  3. polarity: 38% white (or light) text on a dark band covering the whole line, 14% a band behind part of the line
     only (text inside it light, outside it dark), 10% a mid-grey or coloured band with dark or light text, 38%
     ordinary dark on paper; the band has grain, gradients, soft edges;
  4. scanner damage (blur, noise, low resolution, bilevel, JPEG), an Azure-like polygon around the line's ink, then
     common78.cut_line (= experiment 77's cut: pad 0.22 / 0.35, height 48, JPEG q80).
The label is clean_label(text).

QUOTE lines (lead, 2026-11-05: transcribe AS PRINTED): a share QUOTE of the lines are ordinary body lines (experiment
78's text, fonts, paper and damage: render78.render_one, unchanged) in which a span of 1-5 words is set in guillemets
«...» (60%) or printed double parentheses ((...)) (40%), labelled exactly as rendered.  Azure writes printed «» as (( ))
almost everywhere, so the real labels cannot teach «»; these lines can.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import os
import random
import re
import sys
import tarfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
for p in (HERE.parent / "78_synthetic_lines", HERE / "x/e78"):
    if p.exists():
        sys.path.insert(0, str(p))
import render78 as R  # noqa: E402
from common78 import H, clean_label, cut_line, encode  # noqa: E402

# display faces: file -> (weight, variable-weight range or None, no_latin: True when its Latin digits are boxes)
DISPLAY = {
    "arefruqaa_ArefRuqaa-Regular.ttf": (5, None, False), "arefruqaa_ArefRuqaa-Bold.ttf": (5, None, False),
    "alkalami_Alkalami-Regular.ttf": (2, None, False), "amiriquran_AmiriQuran-Regular.ttf": (2, None, False),
    "badeendisplay_BadeenDisplay-Regular.ttf": (1.5, None, False), "blaka_Blaka-Regular.ttf": (2, None, False),
    "changa_Changa[wght].ttf": (2, (500, 800), False), "elmessiri_ElMessiri[wght].ttf": (3, (400, 700), False),
    "gulzar_Gulzar-Regular.ttf": (3, None, False), "jomhuria_Jomhuria-Regular.ttf": (2, None, False),
    "katibeh_Katibeh-Regular.ttf": (3, None, False), "lalezar_Lalezar-Regular.ttf": (3, None, False),
    "lemonada_Lemonada[wght].ttf": (1.5, (400, 700), False), "mada_Mada[wght].ttf": (1.5, (500, 900), False),
    "marhey_Marhey[wght].ttf": (2, (300, 700), False), "mirza_Mirza-Bold.ttf": (2, None, False),
    "notonastaliqurdu_NotoNastaliqUrdu[wght].ttf": (2, (400, 700), False), "qahiri_Qahiri-Regular.ttf": (2, None, False),
    "rakkas_Rakkas-Regular.ttf": (3, None, False), "reemkufi_ReemKufi[wght].ttf": (3, (400, 700), False),
    "reemkufifun_ReemKufiFun[wght].ttf": (1.5, (400, 700), False), "vibes_Vibes-Regular.ttf": (1, None, False),
    "zain_Zain-Black.ttf": (1.5, None, False), "zain_Zain-Bold.ttf": (1.5, None, False),
    # Arabeyes (GPL-2 with the font exception) and KACST (GPL-2): Debian's fonts-arabeyes / fonts-kacst
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Tholoth.ttf": (3, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Mashq.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Mashq-Bold.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Nagham.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Granada.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Ostorah.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Ouhod-Bold.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Rasheeq-Bold.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Shado.ttf": (0.7, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Cortoba.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Hor.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_AlHor.ttf": (1, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Japan.ttf": (0.7, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Kayrawan.ttf": (0.7, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Metal.ttf": (0.7, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_Hani.ttf": (0.7, None, False),
    "deb/x_fonts-arabeyes/usr/share/fonts/truetype/fonts-arabeyes/ae_AlBattar.ttf": (0.7, None, False),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstTitle.ttf": (1.5, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstDecorative.ttf": (1.5, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstPoster.ttf": (1, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstArt.ttf": (1, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstFarsi.ttf": (1, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstPen.ttf": (0.7, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstLetter.ttf": (0.7, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstScreen.ttf": (0.7, None, True),
    "deb/x_fonts-kacst/usr/share/fonts/truetype/kacst/KacstDigital.ttf": (0.5, None, True),
}
# plain faces for the rest of a mixed header (experiment 78's fonts)
PLAIN = {"notosansarabic_NotoSansArabic[wdth_wght].ttf": (4, (500, 800)), "cairo_Cairo[slnt_wght].ttf": (3, None),
         "tajawal_Tajawal-Regular.ttf": (2, None), "almarai_Almarai-Regular.ttf": (2, None),
         "notonaskharabic_NotoNaskhArabic[wght].ttf": (3, (500, 700)), "amiri_Amiri-Bold.ttf": (2, None),
         "ibmplexsansarabic_IBMPlexSansArabic-Regular.ttf": (2, None), "vazirmatn_Vazirmatn[wght].ttf": (2, (500, 800)),
         "notokufiarabic_NotoKufiArabic[wght].ttf": (2, (500, 800))}
LATIN_OR_DIGIT = re.compile("[0-9A-Za-z]")
QUOTE = 0.4
ARW = re.compile("[\u0621-\u064A]")
SEP = re.compile(r"\s+(?:[-–/|،]\s+|\s)")


class Faces:
    def __init__(self, root: Path, root78: Path):
        self.disp, self.plain, self._cache = [], [], {}
        for name, (w, wr, nolat) in DISPLAY.items():
            p = root / "fonts" / name
            if p.exists():
                self.disp.append((str(p), w, wr, R.cmap_of(str(p)), nolat))
        for name, (w, wr) in PLAIN.items():
            p = root78 / "fonts" / name
            if p.exists():
                self.plain.append((str(p), w, wr, R.cmap_of(str(p)), False))

    @staticmethod
    def covers(item, text):
        if item[4] and LATIN_OR_DIGIT.search(text):
            return False
        return all(ord(c) in item[3] or c == " " for c in text)

    def pick(self, rng, pool, text):
        ok = [x for x in pool if self.covers(x, text)]
        return rng.choices(ok, weights=[x[1] for x in ok])[0] if ok else None

    def font(self, item, size, rng):
        wght = rng.randint(*item[2]) if item[2] else None
        k = (item[0], size, wght)
        f = self._cache.get(k)
        if f is None:
            f = ImageFont.truetype(item[0], size, layout_engine=ImageFont.Layout.RAQM)
            if wght is not None:
                try:
                    f.set_variation_by_axes([wght if a.get("name") in (b"Weight", "Weight") else a.get("default", a["minimum"])
                                             for a in f.get_variation_axes()])
                except Exception:  # noqa: BLE001
                    pass
            if len(self._cache) > 300:
                self._cache.clear()
            self._cache[k] = f
        return f


def alef100(item, faces):
    f0 = faces.font(item, 100, random.Random(0))
    try:
        ab = f0.getbbox("ا", anchor="ls")
        return max(20.0, -ab[1])
    except Exception:  # noqa: BLE001
        return 65.0


def bbox(font, s):
    return font.getbbox(s, anchor="rs", direction="rtl", language="ar")


def render_one(text: str, faces: Faces, body: list[str], papers, rng: random.Random):
    """-> (crop, label, info) or None."""
    nrng = np.random.default_rng(rng.randrange(1 << 30))
    # ---- segments: (string, item); right to left in reading order
    segs = None
    m = SEP.search(text)
    if m and rng.random() < 0.4 and m.start() > 3:
        a, b = text[:m.start()], text[m.start():]
        ia, ib = faces.pick(rng, faces.disp, a), faces.pick(rng, faces.plain, b.strip())
        if ia and ib:
            segs = [(a, ia), (b, ib)]
    if segs is None:
        it = faces.pick(rng, faces.disp, text)
        if it is None:
            return None
        segs = [(text, it)]
    alef_px = rng.uniform(14, 40)
    fonts = []
    for s, it in segs:
        sz = max(8, int(round(100 * alef_px / alef100(it, faces) * (1.0 if it in faces.disp else rng.uniform(0.6, 0.95)))))
        fonts.append(faces.font(it, sz, rng))
    widths, tops, bots = [], [], []
    for (s, _), f in zip(segs, fonts):
        try:
            l, t, r, b = bbox(f, s)
        except Exception:  # noqa: BLE001
            return None
        if r - l <= 2:
            return None
        widths.append(r - l)
        tops.append(t)
        bots.append(b)
    gap = alef_px * 0.15
    tw = sum(widths) + gap * (len(segs) - 1)
    ink_top, ink_bot = min(tops), max(bots)
    ph = (ink_bot - ink_top) * rng.uniform(0.85, 1.05)
    padx = int(ph * 1.2) + 20
    lead = ph * rng.uniform(1.1, 1.6)
    Wc, Hc = int(tw + 2 * padx), int(3 * lead + ph * 2)
    if Wc > 6000 or tw < 4:
        return None
    ink = Image.new("L", (Wc, Hc), 0)
    d = ImageDraw.Draw(ink)
    yb = Hc / 2 - (ink_top + ink_bot) / 2
    x = Wc - padx
    seg_x = []
    for (s, _), f, w in zip(segs, fonts, widths):
        d.text((x, yb), s, font=f, fill=255, anchor="rs", direction="rtl", language="ar")
        seg_x.append((x - w, x))
        x -= w + gap
    if rng.random() < 0.1:                                  # a vertical rule at one end (beside a page number)
        xr = rng.choice([seg_x[-1][0] - alef_px * 0.6, seg_x[0][1] + alef_px * 0.6])
        d.line([(xr, yb + ink_top), (xr, yb + ink_bot)], fill=255, width=max(1, int(alef_px / 10)))
    if body and rng.random() < 0.2:                         # neighbours (body text) above / below
        nf = faces.font(rng.choice(faces.plain), max(8, int(alef_px * 1.3)), rng)
        for side in (-1, 1):
            if rng.random() < 0.6:
                d.text((Wc - padx, yb + side * lead), body[rng.randrange(len(body))], font=nf, fill=255, anchor="rs",
                       direction="rtl", language="ar")
    a = np.asarray(ink, np.float32) / 255.0
    k = max(1, int(round(alef_px / 16)))
    r_ = rng.random()
    if r_ < 0.25:
        a = cv2.dilate(a, np.ones((k, k), np.uint8))
    elif r_ < 0.35 and alef_px > 18:
        a = cv2.erode(a, np.ones((k, k), np.uint8))
    if rng.random() < 0.15:
        m_ = R.smooth_noise(a.shape, rng.uniform(1.5, 4.0), nrng)
        a = a * (m_ > rng.uniform(0.05, 0.2))
    if rng.random() < 0.35:
        a = cv2.GaussianBlur(a, (0, 0), rng.uniform(0.3, 1.0))
    a = np.clip(a * rng.uniform(1.2, 2.0), 0, 1)
    # ---- background and polarity
    paper = R.paper_patch(a.shape, papers, rng, nrng)
    band = np.zeros(a.shape, np.float32)
    y0 = int(max(0, yb + ink_top - ph * rng.uniform(0.1, 0.8)))
    y1 = int(min(Hc, yb + ink_bot + ph * rng.uniform(0.1, 0.8)))
    if rng.random() < 0.3:
        y0, y1 = 0, Hc
    p = rng.random()
    mode = "plain"
    if p < 0.38:
        mode = "dark band"
        x0, x1 = 0, Wc
        if rng.random() < 0.25:                             # the band ends a little inside the line's ends
            x0 = int(seg_x[-1][0] + rng.uniform(-0.2, 0.15) * tw)
            x1 = int(seg_x[0][1] - rng.uniform(-0.2, 0.15) * tw)
    elif p < 0.52:
        mode = "partial band"
        if len(segs) > 1 and rng.random() < 0.6:
            sx0, sx1 = seg_x[0] if rng.random() < 0.8 else seg_x[1]
            x0, x1 = int(sx0 - alef_px * rng.uniform(0.2, 1.0)), int(sx1 + alef_px * rng.uniform(0.2, 1.0))
        else:
            c0 = rng.uniform(0, 0.7) * tw
            x1 = int(Wc - padx - c0 + alef_px * 0.5)
            x0 = int(x1 - rng.uniform(0.3, 0.8) * tw)
    elif p < 0.62:
        mode = "grey band"
        x0, x1 = 0, Wc
    if mode != "plain":
        band[y0:y1, max(0, x0):max(0, min(Wc, x1))] = 1.0
        if rng.random() < 0.6:
            band = cv2.GaussianBlur(band, (0, 0), rng.uniform(0.5, 2.5))
        lvl = rng.uniform(0, 90) if mode != "grey band" else rng.uniform(95, 175)
        bandimg = lvl + R.smooth_noise(a.shape, rng.uniform(10, 200), nrng) * rng.uniform(0, 45)
        if rng.random() < 0.5:                              # grain / halftone-like texture
            bandimg = bandimg + nrng.normal(0, rng.uniform(4, 20), a.shape).astype(np.float32)
        if rng.random() < 0.3:                              # a gradient across the band
            bandimg = bandimg + np.linspace(0, rng.uniform(-40, 40), Wc, dtype=np.float32)[None, :]
        light = rng.uniform(190, 255)
        if mode == "grey band" and (lvl > 115 or rng.random() < 0.5):
            light = rng.uniform(0, 40)                      # dark text on a mid-grey band (light text only on a darker grey)
        bg = paper * (1 - band) + bandimg * band
        inkv = rng.uniform(0, 30)
        tv = band * light + (1 - band) * inkv
    else:
        bg, tv = paper, rng.uniform(0, 30)
    img = bg * (1 - a) + tv * a
    # ---- scanner
    if rng.random() < 0.4:
        img = img + nrng.normal(0, rng.uniform(2, 12), img.shape).astype(np.float32)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if mode == "plain" and rng.random() < 0.12:            # bilevel scan (not on a band: it would wipe the text)
        img = np.where(img < rng.uniform(100, 170), 0, 255).astype(np.uint8)
    if rng.random() < 0.35:
        f = rng.uniform(0.45, 0.9)
        small = cv2.resize(img, (max(2, int(Wc * f)), max(2, int(Hc * f))), interpolation=cv2.INTER_AREA)
        img = cv2.resize(small, (Wc, Hc), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.5:
        ok, bb = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(30, 90)])
        img = cv2.imdecode(bb, cv2.IMREAD_GRAYSCALE)
    # ---- Azure-like polygon around the line's ink, then experiment 77's cut
    top = yb + ink_top + (ink_bot - ink_top - ph) / 2 + rng.gauss(0, 0.03 * ph)
    x0p = seg_x[-1][0] - rng.uniform(0, 0.15) * ph
    x1p = seg_x[0][1] + rng.uniform(0, 0.15) * ph
    ang = math.radians(rng.gauss(0, 0.3))
    cy, cx, hw = top + ph / 2, (x0p + x1p) / 2, (x1p - x0p) / 2
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for dx, dy in ((-hw, -ph / 2), (hw, -ph / 2), (hw, ph / 2), (-hw, ph / 2)):
        pts += [cx + dx * ca - dy * sa, cy + dx * sa + dy * ca]
    crop, info = cut_line(img, pts, 1.0, 1.0)
    if crop is None:
        return None
    return crop, clean_label(text), dict(font=os.path.basename(segs[0][1][0]), mixed=len(segs) > 1, mode=mode,
                                         alef=round(alef_px, 1), W=info["W"])


def quote_text(rng: random.Random, body: list[str]) -> str | None:
    """A body line with a span of 1-5 words in «» or (( )), spaced as print varies."""
    for _ in range(20):
        t = body[rng.randrange(len(body))]
        w = t.split(" ")
        if len(w) >= 3 and ARW.search(t):
            break
    else:
        return None
    k = rng.randint(1, min(5, len(w) - 1))
    i = rng.randint(0, len(w) - k)
    span = " ".join(w[i:i + k]).strip("«»()[]،.:؛")
    if not span:
        return None
    if rng.random() < 0.6:
        q = rng.choice([f"«{span}»", f"«{span}»", f"« {span} »"])
    else:
        q = rng.choice([f"(({span}))", f"(({span}))", f"(( {span} ))"])
    return " ".join(w[:i] + [q] + w[i + k:])


def render_any(texts, faces, body, papers, rng, f78):
    if rng.random() < QUOTE:
        t = quote_text(rng, body)
        if t is None:
            return None
        r = R.render_one(t, f78, body, papers, [], rng)
        if r is None:
            return None
        crop, lab, info = r
        info.update(mode="quote")
        return crop, lab, info
    return render_one(texts[rng.randrange(len(texts))], faces, body, papers, rng)


def setup(root: Path, root78: Path):
    faces = Faces(root, root78)
    with gzip.open(root / "text/display84.jsonl.gz", "rt", encoding="utf-8") as f:
        texts = [json.loads(l)["t"] for l in f]
    body = []
    with gzip.open(root78 / "text/text78.jsonl.gz", "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            if i % 15 == 0:
                body.append(json.loads(l)["t"])
    papers = R.load_imgs(str(root78 / "bg/paper-*.jpg")) + R.load_imgs(str(root78 / "bg80/paper-*.jpg"))
    return faces, texts, body, papers, R.Fonts(root78)


def sheet(a):
    faces, texts, body, papers, f78 = setup(Path(a.root), Path(a.root78))
    rng = random.Random(a.seed)
    rows = []
    while len(rows) < a.n:
        r = render_any(texts, faces, body, papers, rng, f78)
        if r:
            rows.append(r)
    W = 1400
    out = np.full(((H + 4) * len(rows), W), 255, np.uint8)
    for k, (c, _, _) in enumerate(rows):
        c = c[:, :W]
        out[(H + 4) * k:(H + 4) * k + H, W - c.shape[1]:] = c
    cv2.imwrite(a.out, out)
    with open(a.out + ".labels.txt", "w", encoding="utf-8") as f:
        for c, lab, info in rows:
            f.write(json.dumps(dict(label=lab, **info), ensure_ascii=False) + "\n")


def _worker(args):
    wid, n, root, root78, out, split, seed = args
    cv2.setNumThreads(1)
    faces, texts, body, papers, f78 = setup(Path(root), Path(root78))
    rng = random.Random(seed * 1000 + wid)
    shard, k, tar = 0, 0, None
    mf = open(os.path.join(out, f"manifest-{split}-{wid}.jsonl"), "w", encoding="utf-8")
    t0, done, fails = time.time(), 0, 0
    while done < n:
        try:
            r = render_any(texts, faces, body, papers, rng, f78)
        except Exception:  # noqa: BLE001
            r = None
        if r is None:
            fails += 1
            continue
        crop, lab, info = r
        if not lab.strip():
            continue
        if tar is None or k >= 5000:
            if tar:
                tar.close()
            tar = tarfile.open(os.path.join(out, f"{split}-{wid}-{shard:03d}.tar"), "w")
            shard += 1
            k = 0
        key = f"d84{wid:02d}_{done:07d}"
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
    jobs = [(w, per, a.root, a.root78, a.out, a.split, a.seed) for w in range(a.workers)]
    with Pool(a.workers) as p:
        res = p.map(_worker, jobs)
    print(json.dumps(res))
    with open(os.path.join(a.out, f"render-{a.split}.json"), "w") as f:
        json.dump(res, f)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--out")
    p.add_argument("--root", default=str(HERE / "out"))
    p.add_argument("--root78", default=str(HERE.parent / "78_synthetic_lines/out"))
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--split", default="train-syn84")
    p.add_argument("--seed", type=int, default=84)
    a = p.parse_args()
    {"sheet": sheet, "shards": shards}[a.cmd](a)
