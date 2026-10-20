"""Experiment 47: the ink layer. Azure's JSON (the same for every run) gives each page's words in Azure's order and
its non-empty lines (the 'P:N' labels flags, patches, judge targets and fixes use); a run's ALTO gives its blocks,
lines and words with boxes in 300-dpi page pixels. Each ALTO word is matched to its Azure word by box, so every
place a run names (a block part, a line, a word span) becomes an ink anchor '<stem>|p<page>|w<first>-<last>' in
Azure's own numbering, which no later run can renumber."""
from __future__ import annotations

import bisect
import json
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

from common47 import E43, REPO

ALTO_NS = "{http://www.loc.gov/standards/alto/ns-v4#}"
XLINK = "{http://www.w3.org/1999/xlink}href"


# ------------------------------------------------------------------ where each stem's Azure JSON is on this machine
def azure_paths() -> dict:
    """stem -> local Azure JSON path, from the sample files of experiments 41/43 (the paths the runs read)."""
    out = {}
    for f in (E43 / "sample43.json", E43 / "sample43b.json", REPO / "experiments/41_azure_structure/out/sample.json"):
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        for a in (d["articles"] if isinstance(d, dict) else d):
            p = Path(a.get("azure") or "")
            if a.get("stem") and p.exists():
                out.setdefault(a["stem"], p)
    fetch = E43 / "out" / "fetch"
    for sub in (fetch, fetch / "reserve"):
        if sub.exists():
            for d in sub.iterdir():
                p = d / f"{d.name}.json"
                if p.exists():
                    out.setdefault(d.name, p)
    return out


# ------------------------------------------------------------------ Azure
def read_azure(path: Path) -> dict:
    j = json.loads(Path(path).read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    pages = {}
    for pg in ar.get("pages") or []:
        p = pg["pageNumber"]
        s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
        words = []
        for k, w in enumerate(pg.get("words") or [], 1):
            xs, ys = w["polygon"][0::2], w["polygon"][1::2]
            x0, y0, x1, y1 = min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s
            words.append(dict(n=k, text=w.get("content"), conf=w.get("confidence"), x=x0, y=y0, w=x1 - x0,
                              h=y1 - y0, off=(w.get("span") or {}).get("offset", -1)))
        offs = [w["off"] for w in words]
        order = sorted(range(len(words)), key=lambda i: offs[i])
        soffs = [offs[i] for i in order]
        lines, word_line = [], {}
        nonempty = [ln for ln in pg.get("lines") or [] if (ln.get("content") or "").strip()]
        for n, ln in enumerate(nonempty, 1):
            ids = []
            for sp in ln.get("spans") or []:
                a, b = sp["offset"], sp["offset"] + sp["length"]
                i = bisect.bisect_left(soffs, a)
                while i < len(soffs) and soffs[i] < b:
                    ids.append(words[order[i]]["n"])
                    i += 1
            xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
            for i in ids:
                word_line.setdefault(i, n)
            confs = [words[i - 1]["conf"] for i in ids if words[i - 1]["conf"] is not None]
            lines.append(dict(line_no=n, x=min(xs) * s, y=min(ys) * s, w=(max(xs) - min(xs)) * s,
                              h=(max(ys) - min(ys)) * s, first=min(ids) if ids else None,
                              last=max(ids) if ids else None, n_words=len(ids),
                              wc_min=min(confs) if confs else None, text=ln.get("content")))
        confs = [w["conf"] for w in words if w["conf"] is not None]
        pages[p] = dict(page=p, width=(pg.get("width") or 0) * s, height=(pg.get("height") or 0) * s,
                        angle=pg.get("angle"), words=words, lines=lines, word_line=word_line,
                        n_words=len(words), wc_mean=sum(confs) / len(confs) if confs else None,
                        wc_min=min(confs) if confs else None, n_low=sum(1 for c in confs if c < 0.5))
    return dict(pages=pages, gemini_front_page=j.get("gemini_front_page"))


# ------------------------------------------------------------------ ALTO
def _box(el):
    try:
        return tuple(float(el.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
    except (TypeError, ValueError):
        return None


def read_alto(path: Path) -> dict:
    """{page: dict(w, h, blocks=[dict(id, tags, box, idnext, composed, lines=[dict(id, box, strings=[...])])])}"""
    pages = {}
    if not Path(path).exists():
        return pages
    root = etree.parse(str(path)).getroot()
    for pg in root.iter(ALTO_NS + "Page"):
        n = int(pg.get("PHYSICAL_IMG_NR") or pg.get("ID", "page0")[4:] or 0)
        P = pages.setdefault(n, dict(w=float(pg.get("WIDTH") or 0), h=float(pg.get("HEIGHT") or 0), blocks=[],
                                     composed=[], illustrations={}))
        for il in pg.iter(ALTO_NS + "Illustration"):
            P.setdefault("illustrations", {})[il.get("ID")] = dict(type=il.get("TYPE"), box=_box(il))
        for cb in pg.iter(ALTO_NS + "ComposedBlock"):
            P["composed"].append(dict(id=cb.get("ID"), type=cb.get("TYPE"), box=_box(cb)))
        for tb in pg.iter(ALTO_NS + "TextBlock"):
            par = tb.getparent()
            B = dict(id=tb.get("ID"), tags=(tb.get("TAGREFS") or "").split(), box=_box(tb), idnext=tb.get("IDNEXT"),
                     lang=tb.get("LANG"), href=tb.get(XLINK),
                     composed=par.get("ID") if par is not None and par.tag == ALTO_NS + "ComposedBlock" else None,
                     lines=[])
            for tl in tb.iter(ALTO_NS + "TextLine"):
                L = dict(id=tl.get("ID"), box=_box(tl), strings=[])
                for s in tl.iter(ALTO_NS + "String"):
                    alt = s.find(ALTO_NS + "ALTERNATIVE")
                    wc = s.get("WC")
                    L["strings"].append(dict(id=s.get("ID"), content=s.get("CONTENT"),
                                             wc=float(wc) if wc not in (None, "") else None,
                                             alt=alt.text if alt is not None else None,
                                             tags=(s.get("TAGREFS") or "").split(), box=_box(s)))
                B["lines"].append(L)
            P["blocks"].append(B)
    return pages


def role_of(tags: list[str]) -> str | None:
    for t in tags:
        if t.startswith("role."):
            return t[5:]
    return None


# ------------------------------------------------------------------ ALTO word -> Azure word, ALTO line -> Azure line
def match_words(az_page: dict, alto_page: dict) -> dict:
    """ALTO String id -> list of Azure word ordinals (a fix can join or split words: then several, by box)."""
    words = az_page["words"]
    exact = {}
    for w in words:
        exact.setdefault((round(w["x"]), round(w["y"])), []).append(w["n"])
    grid = defaultdict(list)
    G = 100.0
    for w in words:
        cx, cy = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2
        grid[(int(cx // G), int(cy // G))].append(w)
    out = {}
    for b in alto_page["blocks"]:
        for ln in b["lines"]:
            for s in ln["strings"]:
                bx = s["box"]
                if not bx:
                    continue
                k = (round(bx[0]), round(bx[1]))
                hit = None
                for dk in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                    c = exact.get((k[0] + dk[0], k[1] + dk[1]))
                    if c:
                        cands = [words[i - 1] for i in c]
                        best = min(cands, key=lambda w: abs(w["w"] - bx[2]) + abs(w["h"] - bx[3]))
                        if abs(best["w"] - bx[2]) < 3 and abs(best["h"] - bx[3]) < 3:
                            hit = [best["n"]]
                            break
                if hit is None:
                    x0, y0, x1, y1 = bx[0] - 2, bx[1] - 2, bx[0] + bx[2] + 2, bx[1] + bx[3] + 2
                    hit = []
                    for gx in range(int((x0) // G), int((x1) // G) + 1):
                        for gy in range(int((y0) // G), int((y1) // G) + 1):
                            for w in grid.get((gx, gy), ()):
                                cx, cy = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2
                                if x0 <= cx <= x1 and y0 <= cy <= y1:
                                    hit.append(w["n"])
                    hit = sorted(set(hit))
                out[s["id"]] = hit
    return out


def line_map(az_page: dict, alto_page: dict, wmap: dict) -> dict:
    """ALTO TextLine id -> dict(azure_line_no, first, last, method, wc_min, n_strings)."""
    wl = az_page["word_line"]
    out = {}
    for b in alto_page["blocks"]:
        for ln in b["lines"]:
            ords = [n for s in ln["strings"] for n in wmap.get(s["id"], [])]
            if ords:
                c = Counter(wl.get(n) for n in ords if wl.get(n))
                azl = c.most_common(1)[0][0] if c else None
                out[ln["id"]] = dict(azure_line_no=azl, first=min(ords), last=max(ords), method="box-overlap")
            else:
                out[ln["id"]] = dict(azure_line_no=None, first=None, last=None, method="none")
    return out
