"""Experiment 82: the test lines with known letters, and their damage.

Faces:
  modern  - exp 78's OFL faces (as exp 79's mcrcmp: every face of data79.TRAIN_FONTS that is not traced) + Mirza
  traced  - exp 78's typefaces TRACED from our own old scans (out/fonts/traced), respecting exclude.json: a face marked
            DROP is not used; a face's "chars" never appear; its "iso" letters never appear in their isolated form
Damage levels (the line is rendered once and every level is applied to the same rendering, so rebuilders and levels are
compared on the same letters):
  clean  - the rendered ink itself
  mild, heavy, spread - exp 79's data79.damage (spread: dilation 1-3 x, counters close, then mild scan damage)
  fill   - NEW, old heavy print: ink spread 1-2 x, then most small counters FILLED (a hole of a loop letter becomes ink
           with probability 0.8), then mild scan damage: the 1937/1953 pages' filled heads of و ف ق م ه
"""
from __future__ import annotations

import gzip
import json
import random
from pathlib import Path

import cv2
import numpy as np

import path82  # noqa: F401  (sets sys.path for the frozen exp-79 copies and uharfbuzz)
import synth79 as S
from data79 import ARABIC, TRAIN_FONTS, cut, damage

FONTS = S.FONTS
EXCLUDE = json.loads((FONTS / "traced/exclude.json").read_text(encoding="utf-8"))
MODERN = [f for f in TRAIN_FONTS if not f.startswith("traced")] + ["mirza_Mirza-Regular.ttf"]
TRACED = sorted(f"traced/{p.name}" for p in (FONTS / "traced").glob("*.ttf")
                if EXCLUDE.get(p.stem) != "DROP" and p.stem in EXCLUDE)
LOOPS = set("وفقمهةصضطظعغؤ")
NON_LEFT = set("اأإآدذرزوؤةءى") - {"ى"}                              # letters that never join the next one
LEVELS = ["clean", "mild", "heavy", "spread", "fill"]


def isolated_letters(text: str) -> set:
    """The letters of `text` that stand in their isolated form."""
    out = set()
    for w in text.split():
        L = [c for c in w if c in ARABIC]
        for i, c in enumerate(L):
            prev_joins = i > 0 and L[i - 1] not in NON_LEFT and L[i - 1] != "ء"
            next_joins = i + 1 < len(L) and c not in NON_LEFT and c != "ء"
            if not prev_joins and not next_joins:
                out.add(c)
    return out


def allowed(text: str, font: str) -> bool:
    if not font.startswith("traced"):
        return True
    e = EXCLUDE.get(Path(font).stem, {})
    if e == "DROP":
        return False
    if not set(text.replace(" ", "")) <= ARABIC:
        return False
    if set(text) & set(e.get("chars", "")):
        return False
    return not (isolated_letters(text) & set(e.get("iso", "")))


def fill_damage(grey: np.ndarray, rng: random.Random) -> np.ndarray:
    ink = (grey < 128).astype(np.uint8)
    e = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    ink = cv2.dilate(ink, e, iterations=rng.choice([1, 1, 2]))
    n, lab, st, _ = cv2.connectedComponentsWithStats(1 - ink, connectivity=4)
    H, W = ink.shape
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if x > 0 and y > 0 and x + w < W and y + h < H and a < 0.04 * H * H and rng.random() < 0.8:
            ink[lab == k] = 1
    g = np.where(ink > 0, 25, 245).astype(np.uint8)
    return damage(g, rng, "mild")


def damaged(grey: np.ndarray, level: str, seed: int) -> np.ndarray:
    rng = random.Random(seed)
    if level == "clean":
        return grey
    if level == "fill":
        return fill_damage(grey, rng)
    return damage(grey, rng, level)


def texts(n_max: int = 6000, every: int = 50, offset: int = 23):
    """Held-out-ish text: every 50th corpus line from an offset other than exp 79's mcrcmp (7)."""
    out = []
    with gzip.open(S.TEXT, "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            if i % every == offset:
                out.append(json.loads(l)["t"])
            if len(out) >= n_max:
                break
    return out


def pick_lines(n: int, faces: str, seed: int = 8200, need_loop: bool = True):
    """n line specs: dict(text, font, px, seed)."""
    rng = random.Random(seed)
    T = texts()
    fonts = MODERN if faces == "modern" else TRACED
    out = []
    while len(out) < n:
        t = cut(rng.choice(T), rng)
        if len(t) < 8 or (need_loop and not (set(t) & LOOPS)):
            continue
        f = fonts[len(out) % len(fonts)]
        if not allowed(t, f) or not S.covers(FONTS / f, t):
            continue
        out.append(dict(text=t, font=f, px=round(62.0 * rng.uniform(0.85, 1.15), 1), seed=rng.randrange(1 << 30)))
    return out


def render(spec: dict):
    S.H = 96
    return S.render(spec["text"], FONTS / spec["font"], px_per_em=spec["px"])
