"""Experiment 43: the second key — code checks that confirm (or not) an edit the judge proposes (judge43.py), from the
scan and Azure, never from a model. No model calls.

    python3 evidence43.py --build-words          out/judge/arwords.txt (Arabic word list from the MARC catalogue)
    python3 evidence43.py --stem S --page P      every line of the page: ink, non-words, Azure confidence

Show-through / bleed / scanner junk (action mark_noise) is confirmed when the target lines are
  pale     their ink is much lighter than the page's own text: share of really dark pixels (grey < DARK) in the line
           box, divided by the same share in the page's ordinary text lines (75th percentile of all lines) <= PALE
  and one of
  garbled  share of their words (Arabic, >= 2 letters) not in the word list (folded, with and without the common
           prefixes و ف ب ل ك ال) >= NONWORD
  unsure   Azure's mean word confidence <= the page's 75th percentile minus CONF_DROP
Mirrored glyphs are not checked separately: Azure reads mirrored Arabic as non-words (0744 p1), which the second
test sees. Structure edits get geometry checks (`check()`): a block kind fits where the block sits, a new order is
a permutation that follows the columns better, a split point is a real gap, a merge joins neighbours, another
article's block opens or closes the page, a picture box holds ink and covers no running text.
Thresholds are set on the calibration pages (README "The judge").
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out"
WORDS = OUT / "judge" / "arwords.txt"
MARC = Path(os.path.expanduser("~/data/marc/marc.db"))

DARK = 100          # grey below this is real ink (print); show-through stays lighter
PALE = 0.45         # line's dark share / page text's dark share at or below this: pale
NONWORD = 0.20      # share of non-words at or above this: garbled
CONF_DROP = 0.20    # mean Azure confidence this far under the page's good lines (75th percentile): unsure

AR = re.compile(r"[ء-ي]+")
DIAC = re.compile(r"[ً-ْٰـ]")
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})
PREFIXES = ("وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك")
SUFFIXES = ("هما", "كما", "هم", "هن", "ها", "نا", "كم", "ات", "ون", "ين", "ان", "ه", "ي", "ك")


def fold(w: str) -> str:
    return DIAC.sub("", w).translate(FOLD)


def build_words(n_abstracts: int = 300000):
    """Word list: every folded Arabic word seen at least twice in the catalogue's titles and a slice of abstracts."""
    from collections import Counter
    c = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    cnt = Counter()
    for (t,) in c.execute("select coalesce(title,'') || ' ' || coalesce(subtitle,'') from records"):
        cnt.update(fold(w) for w in AR.findall(t))
    for (t,) in c.execute(f"select text from abstracts limit {n_abstracts}"):
        cnt.update(fold(w) for w in AR.findall(t or ""))
    keep = sorted(w for w, k in cnt.items() if k >= 2 and len(w) >= 2)
    WORDS.parent.mkdir(parents=True, exist_ok=True)
    WORDS.write_text("\n".join(keep), encoding="utf-8")
    print(f"{len(keep)} words (of {len(cnt)} seen) -> {WORDS}")


@lru_cache(maxsize=1)
def wordset() -> frozenset:
    if not WORDS.exists():
        build_words()
    return frozenset(WORDS.read_text(encoding="utf-8").split())


def is_word(w: str) -> bool:
    f, S = fold(w), wordset()
    if f in S:
        return True
    for p in PREFIXES:
        if f.startswith(p) and len(f) - len(p) >= 2:
            r = f[len(p):]
            if r in S or any(r.endswith(s) and r[:-len(s)] in S for s in SUFFIXES if len(r) - len(s) >= 2):
                return True
    return any(f.endswith(s) and f[:-len(s)] in S for s in SUFFIXES if len(f) - len(s) >= 2)


def nonword_share(text: str) -> tuple[float, int]:
    ws = [w for w in AR.findall(text) if len(fold(w)) >= 2]
    if not ws:
        return 0.0, 0
    return sum(not is_word(w) for w in ws) / len(ws), len(ws)


@lru_cache(maxsize=4)
def _grey(path: str):
    import cv2
    return cv2.imread(path, cv2.IMREAD_GRAYSCALE)


def dark_share(img, px) -> float:
    x0, y0, x1, y1 = (int(round(v)) for v in px)
    h, w = img.shape
    x0, x1, y0, y1 = max(0, x0), min(w, x1), max(0, y0), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float((img[y0:y1, x0:x1] < DARK).mean())


class PageEvidence:
    """Ink, words and Azure confidence for every line of one page (ids as in the answers: "p:n")."""

    def __init__(self, a: dict, p: int):
        import masters43 as M43
        self.a, self.p = a, p
        ls, self.W, self.H = M43.ST.page_lines(a, p)
        self.lines = {L["id"]: L for L in ls}
        img = _grey(str(M43.ST.page_image(a, p)))
        words = M43.azure_words(a)
        self.m = {}
        for lid, L in self.lines.items():
            ws = words(lid)
            cf = [w["conf"] for w in ws if w.get("conf") is not None]
            nw, n = nonword_share(L["text"])
            self.m[lid] = dict(dark=dark_share(img, L["px"]), nonword=nw, nwords=n,
                               conf=float(np.mean(cf)) if cf else None)
        ds = [v["dark"] for v in self.m.values()]
        self.ref_dark = float(np.percentile(ds, 75)) if ds else 0.0
        cs = [v["conf"] for v in self.m.values() if v["conf"] is not None]
        self.ref_conf = float(np.percentile(cs, 75)) if cs else None

    def line(self, lid: str) -> dict:
        base = lid if lid in self.m else re.sub(r"[a-z]$", "", lid)
        return self.m.get(base)

    def noise_check(self, lids: list[str]) -> dict:
        """Are these lines show-through / bleed / junk? Weighted by words."""
        ms = [(i, self.line(i)) for i in lids]
        ms = [(i, m) for i, m in ms if m]
        if not ms or not self.ref_dark:
            return dict(ok=False, why="no lines measured")
        wt = [max(1, m["nwords"]) for _, m in ms]
        pale = sum(m["dark"] * w for (_, m), w in zip(ms, wt)) / sum(wt) / self.ref_dark
        nw_n = sum(m["nwords"] for _, m in ms)
        nonword = sum(m["nonword"] * m["nwords"] for _, m in ms) / nw_n if nw_n else 0.0
        cf = [m["conf"] for _, m in ms if m["conf"] is not None]
        conf = float(np.mean(cf)) if cf else None
        unsure = conf is not None and self.ref_conf is not None and conf <= self.ref_conf - CONF_DROP
        is_pale, garbled = pale <= PALE, nonword >= NONWORD
        ok = is_pale and (garbled or unsure)
        why = (f"ink {pale:.2f} of the page's text ({'pale' if is_pale else 'not pale'}), "
               f"non-words {nonword:.0%} of {nw_n} ({'garbled' if garbled else 'words'}), "
               f"Azure conf {conf if conf is None else round(conf, 2)} vs page {self.ref_conf and round(self.ref_conf, 2)}"
               f"{' (unsure)' if unsure else ''}")
        # per-line split: lines that pass alone (the judge may lump a real line in with the junk)
        per = {i: bool(m["dark"] / self.ref_dark <= PALE and (m["nonword"] >= NONWORD or
                       (m["conf"] is not None and self.ref_conf is not None and m["conf"] <= self.ref_conf - CONF_DROP)))
               for i, m in ms}
        return dict(ok=ok, pale=round(pale, 3), nonword=round(nonword, 3), conf=conf, why=why,
                    lines_pass=[i for i, v in per.items() if v], lines_fail=[i for i, v in per.items() if not v])


# ----------------------------------------------------------------------------------------- structure checks

def union(bs):
    bs = [b for b in bs if b]
    if not bs:
        return None
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def overlap(a, b) -> float:
    """share of a's area inside b"""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    return w * h / max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))


RUNNING = {"paragraph", "footnote", "list_item", "verse", "quote", "reference", "abstract", "boxed", "other"}


def check(action: str, payload: dict, page: dict) -> dict:
    """Geometry check of a structure edit. `page` = judge43.page_view(): blocks [{id, type, lines, box}] in order
    (boxes 0-1000), line boxes by id."""
    B = {b["id"]: b for b in page["blocks"]}
    tg = payload.get("blocks") or []
    bs = [B[t] for t in tg if t in B]
    if action in ("set_kind", "mark_other_article", "unmark_other_article", "split_block", "fix_picture_box",
                  "relink_call") and not bs:
        return dict(ok=False, why="target block not on the page")
    if action == "set_kind":
        k, b = payload.get("kind"), bs[0]
        bx, n = b["box"] or [0, 0, 0, 0], len(b["lines"])
        if k in ("header",) and bx[1] > 150:
            return dict(ok=False, why=f"a running head below the top of the page (y {bx[1]})")
        if k in ("footer",) and bx[3] < 850:
            return dict(ok=False, why=f"a footer above the foot of the page (y {bx[3]})")
        if k in ("heading", "title") and n > 4:
            return dict(ok=False, why=f"a heading of {n} lines")
        if k == "footnote" and bx[1] < 400:
            return dict(ok=False, why=f"a footnote in the upper part of the page (y {bx[1]})")
        if k in ("figure", "table") and not b.get("box"):
            return dict(ok=False, why="no box")
        return dict(ok=True, why=f"{b['type']} → {k}: {n} lines at y {bx[1]}–{bx[3]} fits")
    if action == "reorder":
        order = payload.get("order") or []
        ids = [b["id"] for b in page["blocks"]]
        if sorted(order) != sorted(ids):
            return dict(ok=False, why="not a permutation of the page's blocks")
        def inv(seq):     # inversions against a right-to-left column reading (column = right edge band)
            pos = [B[i]["box"] for i in seq if B[i].get("box")]
            bad = 0
            for i in range(len(pos)):
                for j in range(i + 1, len(pos)):
                    a, b = pos[i], pos[j]
                    same_col = min(a[2], b[2]) - max(a[0], b[0]) > 0.3 * min(a[2] - a[0], b[2] - b[0])
                    if same_col and b[3] <= a[1]:
                        bad += 1
            return bad
        before, after = inv(ids), inv(order)
        return dict(ok=after < before, why=f"blocks read upward within a column: {before} now, {after} after")
    if action == "split_block":
        b, at = bs[0], payload.get("at_line")
        if at not in b["lines"] or b["lines"].index(at) == 0:
            return dict(ok=False, why="split line not inside the block")
        k = b["lines"].index(at)
        L = page["line_box"]
        top, bot = union([L.get(i) for i in b["lines"][:k]]), union([L.get(i) for i in b["lines"][k:]])
        if not top or not bot:
            return dict(ok=False, why="no boxes")
        gap = bot[1] - top[3]
        sidecol = min(top[2], bot[2]) - max(top[0], bot[0]) < 0.5 * min(top[2] - top[0], bot[2] - bot[0])
        lh = np.median([L[i][3] - L[i][1] for i in b["lines"] if L.get(i)])
        ok = sidecol or gap > 0.8 * lh or gap < -2 * lh
        return dict(ok=bool(ok), why=f"gap {gap:.0f} (line height {lh:.0f}){', other column' if sidecol else ''}")
    if action == "merge_blocks":
        if len(bs) < 2:
            return dict(ok=False, why="fewer than two blocks")
        ids = [b["id"] for b in page["blocks"]]
        idx = sorted(ids.index(b["id"]) for b in bs)
        if idx != list(range(idx[0], idx[0] + len(idx))):
            return dict(ok=False, why="blocks not next to each other in reading order")
        if len({b["type"] for b in bs} - {"other"}) > 1:
            return dict(ok=False, why="blocks of different kinds")
        return dict(ok=True, why="neighbours in reading order, same kind")
    if action in ("mark_other_article", "unmark_other_article"):
        ids = [b["id"] for b in page["blocks"] if b["type"] not in ("header", "footer", "noise")]
        pos = sorted(ids.index(b["id"]) for b in bs if b["id"] in ids)
        if action == "unmark_other_article":
            return dict(ok=bool(pos), why="block on the page")
        edge = pos and (pos[0] == 0 or pos[-1] == len(ids) - 1 or
                        pos == list(range(pos[0], len(ids))) or pos == list(range(0, pos[-1] + 1)))
        return dict(ok=bool(edge), why="at the start or end of the page's reading order" if edge
                    else "in the middle of the page's reading order")
    if action == "fix_picture_box":
        nb = payload.get("box")
        if not nb or len(nb) != 4 or not (0 <= nb[0] < nb[2] <= 1000 and 0 <= nb[1] < nb[3] <= 1000):
            return dict(ok=False, why="box not on the page")
        own = set(bs[0]["lines"])
        hit = [i for b in page["blocks"] if b["type"] in RUNNING for i in b["lines"]
               if i not in own and page["line_box"].get(i) and overlap(page["line_box"][i], nb) > 0.3]
        if hit:
            return dict(ok=False, why=f"would cover {len(hit)} running-text lines")
        return dict(ok=True, why="covers no running text")
    if action == "relink_call":
        line = payload.get("line")
        txt = page["line_text"].get(line, "")
        mk = (payload.get("marker") or "").strip("()[] ")
        ok = bool(mk) and mk in txt and payload.get("fn") in page.get("notes", set())
        return dict(ok=ok, why=f"marker {'in' if mk and mk in txt else 'not in'} the line; note "
                    f"{'exists' if payload.get('fn') in page.get('notes', set()) else 'unknown'}")
    return dict(ok=False, why=f"no check for {action}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-words", action="store_true")
    ap.add_argument("--stem")
    ap.add_argument("--page", type=int)
    a = ap.parse_args()
    if a.build_words:
        return build_words()
    import run43
    art = next(x for x in run43.articles("b") if x["stem"] == a.stem)
    E = PageEvidence(art, a.page)
    print(f"ref dark {E.ref_dark:.3f} ref conf {E.ref_conf}")
    for lid, m in E.m.items():
        print(f"{lid:7} dark {m['dark'] / max(E.ref_dark, 1e-9):5.2f} nonword {m['nonword']:4.0%}/{m['nwords']:<3} "
              f"conf {m['conf'] if m['conf'] is None else round(m['conf'], 2)}  {E.lines[lid]['text'][:50]}")


if __name__ == "__main__":
    main()
