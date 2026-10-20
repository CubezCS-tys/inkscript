"""Experiment 43: a page render that shows its text, checked against Azure's words (fix round 3, 2026-10-20).

The proof pack found 0529-004-007-007 sent to Gemini and the judge as pages without Arabic: the PDF's
SimplifiedArabic fonts are not embedded (CID, Identity-H), so the renderer has no glyphs and draws nothing, while
Azure read the PDF's text. Before a page image is used (the model's request, the judge, crops for the masters) its
ink is compared with Azure's word boxes:

  check     share of Azure's words whose box holds ink (dark pixels >= INK_MIN of the box); a page with
            >= MIN_WORDS words without ink and a share under BLANK_SHARE is "blank where Azure has text"
            (0529 p2: the flow chart's embedded-font words have ink, the body around it has none)
  re-render the PDF page again with the missing fonts embedded from the system (a non-embedded font whose name
            is in FONTS gets that TrueType file as its FontFile2; the PDF on disk is not touched), at 300 dpi, into
            out/pages_fixed/<stem>_pNNN.jpg; checked again; kept only when its share is higher
  record    out/render_check.jsonl: one line per page checked (share before / after, fonts embedded, kept)

install(ST) wraps structure.page_image: a page with a kept re-render returns out/pages_fixed/...; a page never
checked is checked on first use (once per process; the record file is the cache across processes).

    render43.py check --set c [--stems ...]     check (and re-render) every page of a sample
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
FIXED = OUT / "pages_fixed"
RECORD = OUT / "render_check.jsonl"
WINFONTS = Path("/mnt/c/Windows/Fonts")
FONTS = {                                   # PDF font name (subset prefix and style suffixes stripped) -> system file
    "SimplifiedArabic": "simpo.ttf", "SimplifiedArabic-Bold": "simpbdo.ttf",
    "TraditionalArabic": "trado.ttf", "TraditionalArabic-Bold": "tradbdo.ttf",
    "ArialMT": "arial.ttf", "Arial-BoldMT": "arialbd.ttf", "Arial": "arial.ttf",
    "TimesNewRomanPSMT": "times.ttf", "TimesNewRomanPS-BoldMT": "timesbd.ttf",
    "TimesNewRomanPS-ItalicMT": "timesi.ttf", "TimesNewRomanPS-BoldItalicMT": "timesbi.ttf",
    "CourierNewPSMT": "cour.ttf", "Tahoma": "tahoma.ttf", "Tahoma-Bold": "tahomabd.ttf",
}
INK_MIN = 0.03                              # a word box "has ink" from this share of dark pixels
DARK = 140                                  # grey level under which a pixel is ink
MIN_WORDS = 20                              # a page is blank where Azure has text when at least this many of its
BLANK_SHARE = 0.8                           # words have no ink and they are over a fifth of its words

_done: dict = {}
_rec: dict | None = None


def records() -> dict:
    global _rec
    if _rec is None:
        _rec = {}
        if RECORD.exists():
            for ln in RECORD.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                _rec[(r["stem"], r["page"])] = r
    return _rec


def word_boxes(a: dict, p: int) -> list[list[float]]:
    """Azure's word boxes on page p, px at 300 dpi (the frame of out/pages)."""
    sys.path.insert(0, str(HERE.parent / "41_azure_structure"))
    import masters as M
    pg = M.azure_raw(a)["pages"][p - 1]
    s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
    out = []
    for w in pg.get("words", []):
        xs, ys = w["polygon"][0::2], w["polygon"][1::2]
        out.append([min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s])
    return out


def ink_share(img_path: Path, boxes) -> float | None:
    import cv2
    img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
    if img is None or not boxes:
        return None
    H, W = img.shape[:2]
    hit = n = 0
    for x0, y0, x1, y1 in boxes:
        x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(W, int(x1) + 1), min(H, int(y1) + 1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        n += 1
        hit += float((img[y0:y1, x0:x1] < DARK).mean()) >= INK_MIN
    return round(hit / n, 3) if n else None


def base_name(name: str) -> str:
    return name.lstrip("/").split("+", 1)[-1]


def rerender(a: dict, p: int, dst: Path) -> list[str]:
    """The page rendered with its non-embedded fonts embedded from the system; returns the fonts embedded."""
    import pymupdf
    d = pymupdf.open(a["pdf"])
    got, data = [], {}
    for x in range(1, d.xref_length()):
        try:
            if d.xref_get_key(x, "Type")[1] != "/FontDescriptor":
                continue
        except Exception:                                    # noqa: BLE001
            continue
        name = base_name(d.xref_get_key(x, "FontName")[1])
        if any(d.xref_get_key(x, k)[0] != "null" for k in ("FontFile", "FontFile2", "FontFile3")):
            continue
        f = WINFONTS / FONTS.get(name, "-")
        if not f.exists():
            continue
        if name not in data:
            b = f.read_bytes()
            nx = d.get_new_xref()
            d.update_object(nx, "<<>>")
            d.update_stream(nx, b)
            d.xref_set_key(nx, "Length1", str(len(b)))
            data[name] = nx
        d.xref_set_key(x, "FontFile2", f"{data[name]} 0 R")
        got.append(name)
    if got:
        dst.parent.mkdir(parents=True, exist_ok=True)
        d[p - 1].get_pixmap(dpi=300, alpha=False).save(str(dst), jpg_quality=88)
    d.close()
    return sorted(set(got))


def check(a: dict, p: int, img: Path) -> dict:
    key = (a["stem"], p)
    r = records().get(key)
    if r is not None:
        return r
    boxes = word_boxes(a, p)
    share = ink_share(img, boxes)
    r = dict(stem=a["stem"], page=p, words=len(boxes), share=share, blank=False, when=time.strftime("%Y-%m-%d %H:%M"))
    if share is not None and (1 - share) * len(boxes) >= MIN_WORDS and share < BLANK_SHARE:
        r["blank"] = True
        dst = FIXED / img.name
        try:
            fonts = rerender(a, p, dst)
        except Exception as e:                               # noqa: BLE001
            fonts, r["error"] = [], f"{type(e).__name__}: {e}"
        r["fonts_embedded"] = fonts
        if fonts and dst.exists():
            s2 = ink_share(dst, boxes)
            r["share_after"] = s2
            r["kept"] = bool(s2 is not None and s2 > share)
            if not r["kept"]:
                dst.unlink()
        else:
            r["kept"] = False
        r["how"] = "pymupdf, non-embedded fonts embedded from the system (render43.rerender)"
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    with RECORD.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    records()[key] = r
    return r


def install(ST):
    """Wrap structure.page_image (idempotent): the checked, possibly re-rendered page."""
    if getattr(ST.page_image, "_render43", False):
        return
    orig = ST.page_image

    def page_image(a, p):
        f = orig(a, p)
        if Path(f).parent.resolve() != (OUT / "pages").resolve():
            return f                                 # experiment 41's own renders: not checked here
        k = (a["stem"], p)
        if k not in _done:
            try:
                _done[k] = check(a, p, Path(f))
            except Exception as e:                   # noqa: BLE001  (a check must never stop a build)
                _done[k] = dict(error=str(e))
        alt = FIXED / Path(f).name
        return alt if _done[k].get("kept") and alt.exists() else f
    page_image._render43 = True
    ST.page_image = page_image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check"])
    ap.add_argument("--set", default="c")
    ap.add_argument("--stems", nargs="*")
    a = ap.parse_args()
    import run43
    import masters43 as M43
    M43.ST.PAGES = OUT / "pages"
    install(M43.ST)
    n = blank = kept = 0
    for art in run43.articles(a.set):
        if a.stems and art["stem"] not in a.stems:
            continue
        for p in range(art["first"], art["last"] + 1):
            M43.ST.page_image(art, p)
            r = _done.get((art["stem"], p)) or {}
            n += 1
            blank += bool(r.get("blank"))
            kept += bool(r.get("kept"))
            if r.get("blank"):
                print(f"  {art['stem']} p{p}: share {r.get('share')} -> {r.get('share_after')} "
                      f"fonts {r.get('fonts_embedded')} kept {r.get('kept')}", flush=True)
    print(f"pages {n}: blank where Azure has text {blank}, re-rendered and kept {kept}")


if __name__ == "__main__":
    main()
