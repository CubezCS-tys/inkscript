"""Born-digital pages with exact truth (experiment 36's second page set), from experiment 33's held-out test documents.

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python bd.py survey     # every candidate page's features
    ... bd.py build [--n 60]                                                           # pick, render, write truth + Azure

Documents: 33's test split that passed its doc_quality filter (30 documents, 25 journals, 2005+ print).
Truth lines: 33's lines.py reconstruction from the PDF's own glyphs, with the document's decoding variant chosen by
33 (build_data.py); the text is lines.py's, NOT 33's `faithful` (which folds digit kinds): digits stay as the PDF
stores them (some producers store Western codes for Arabic-Indic glyphs: score born-digital digits folded).
Reading order: recursive XY-cut on the line boxes (right column first; a table Azure found is kept as one block read
row by row; a horizontal strip whose lines leave the same gutter as its neighbour is merged with it, so a two-column
body is cut into columns, not rows). Checked against Azure's order and the PDF's own content-stream order (survey).
Azure: the page's Azure lines in Azure's reading order (src/inkscript/gold/draft.py, the yardstick's own drafting).
Pages are left out when the truth would be incomplete: PUA or U+FFFD code points, or more than 5% of Azure's words
outside every truth line (text in pictures, rotated text, a Dummy-only part).
Everything in px of a 300 dpi render of the page (the pack's JPEG).
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

E33 = Path("/home/yassine/inkscript/experiments/33_kraken")
E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")
DPI = 300
S = DPI / 72.0
sys.path.insert(0, str(E33))
from lines import page_glyphs, group_lines, logical, born_digital  # noqa: E402  (33's reconstruction, read only)


def doc_dir(d: str) -> Path:
    for p in (E19 / "docs" / d, E33 / "out" / "docs" / d):
        if (p / f"{d}.pdf").exists() and (p / f"{d}.json").exists():
            return p
    raise FileNotFoundError(d)


def candidates() -> list[str]:
    dq = json.load(open(E33 / "out" / "doc_quality.json"))
    return sorted(d for d, v in dq.items() if v["split"] in ("test", "dev") and v["keep"])


def rules(page) -> tuple[list, list]:
    """The page's ruling in points: vertical (x, y0, y1) and horizontal (y, x0, x1) segments."""
    V, H = [], []
    for path in page.get_drawings():
        stroked = path.get("color") is not None
        for it in path["items"]:
            if it[0] == "l":
                p1, p2 = it[1], it[2]
                if abs(p1.x - p2.x) < 1.5 and abs(p1.y - p2.y) > 5:
                    V.append((p1.x, min(p1.y, p2.y), max(p1.y, p2.y)))
                elif abs(p1.y - p2.y) < 1.5 and abs(p1.x - p2.x) > 5:
                    H.append((p1.y, min(p1.x, p2.x), max(p1.x, p2.x)))
            elif it[0] == "re":
                r = it[1]
                if r.width < 2.5 and r.height > 5:
                    V.append(((r.x0 + r.x1) / 2, r.y0, r.y1))
                elif r.height < 2.5 and r.width > 5:
                    H.append(((r.y0 + r.y1) / 2, r.x0, r.x1))
                elif stroked and r.width > 5 and r.height > 5:
                    V += [(r.x0, r.y0, r.y1), (r.x1, r.y0, r.y1)]; H += [(r.y0, r.x0, r.x1), (r.y1, r.x0, r.x1)]
    return V, H


def ruled_tables(V, H) -> list[list[float]]:
    """Boxes (points) of ruled tables: clusters of touching rules with a vertical rule inside the cluster's box and a
    horizontal one inside it (a page frame, a rule under the running head, are not tables)."""
    segs = [("v", x, y0, x, y1) for x, y0, y1 in V] + [("h", x0, y, x1, y) for y, x0, x1 in H]
    n = len(segs)
    if n < 4 or n > 4000:
        return []
    par = list(range(n))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]; i = par[i]
        return i
    t = 2.5
    for i in range(n):
        a = segs[i]
        for j in range(i + 1, n):
            b = segs[j]
            if a[1] - t <= b[3] and b[1] - t <= a[3] and a[2] - t <= b[4] and b[2] - t <= a[4]:
                par[find(i)] = find(j)
    cl = {}
    for i in range(n):
        cl.setdefault(find(i), []).append(segs[i])
    out = []
    for ss in cl.values():
        x0 = min(s[1] for s in ss); y0 = min(s[2] for s in ss); x1 = max(s[3] for s in ss); y1 = max(s[4] for s in ss)
        if x1 - x0 < 50 or y1 - y0 < 25:
            continue
        iv = any(s[0] == "v" and x0 + 4 < s[1] < x1 - 4 for s in ss)
        ih = any(s[0] == "h" and y0 + 4 < s[2] < y1 - 4 for s in ss)
        if iv and ih:
            out.append([x0, y0, x1, y1])
    return out


def _split_at_rules(ln: list, V: list) -> list[list]:
    """A visual line that crosses a vertical rule is two cells."""
    ink = [g for g in ln if not g["s"].isspace()]
    if not ink or not V:
        return [ln]
    yc = sorted((g["y0"] + g["y1"]) / 2 for g in ink)[len(ink) // 2]
    lx0 = min(g["x0"] for g in ink); lx1 = max(g["x1"] for g in ink)
    xs = sorted({round(x, 1) for x, y0, y1 in V if y0 - 1 <= yc <= y1 + 1 and lx0 + 1 < x < lx1 - 1})
    if not xs:
        return [ln]
    parts = [[] for _ in range(len(xs) + 1)]
    for g in ln:
        parts[sum((g["x0"] + g["x1"]) / 2 > x for x in xs)].append(g)
    return [p for p in parts if any(not g["s"].isspace() for g in p)]


def gutters(vis: list[list]) -> list[float]:
    """x (points) of column gutters that lines.py's 2.5 em rule did not see (a narrow gutter joins the columns into
    one visual line): an x where at least 5 lines, and half the lines crossing it, have a gap of 0.5 em or more."""
    from collections import Counter
    gap, span = Counter(), Counter()
    for ln in vis:
        ink = sorted((g for g in ln if not g["s"].isspace()), key=lambda g: g["x0"])
        if len(ink) < 2:
            continue
        em = sorted(g["size"] for g in ink)[len(ink) // 2]
        for b in range(int(ink[0]["x0"] // 2), int(max(g["x1"] for g in ink) // 2) + 1):
            span[b] += 1
        end = ink[0]["x1"]
        for g in ink[1:]:
            if g["x0"] - end > 0.5 * em:
                for b in range(int(end // 2) + 1, int(g["x0"] // 2)):
                    gap[b] += 1
            end = max(end, g["x1"])
    bins = sorted(b for b in gap if gap[b] >= 5 and gap[b] >= 0.5 * span[b])
    out, run = [], []
    for b in bins:
        if run and b != run[-1] + 1:
            out.append((run[0] + run[-1] + 1)); run = []
        run.append(b)
    if run:
        out.append((run[0] + run[-1] + 1))
    # a gutter has a column on each side: the text left and right of it is at least 4 em wide (a hanging list
    # number "4)" beside its entry is no column)
    keep = []
    for x in out:
        lw, rw = [], []
        for ln in vis:
            ink = [g for g in ln if not g["s"].isspace()]
            if len(ink) < 2 or not (min(g["x0"] for g in ink) < x < max(g["x1"] for g in ink)):
                continue
            if any(g["x0"] < x < g["x1"] for g in ink):
                continue
            em = sorted(g["size"] for g in ink)[len(ink) // 2]
            lw.append((x - min(g["x0"] for g in ink)) / em); rw.append((max(g["x1"] for g in ink) - x) / em)
        if lw and sorted(lw)[len(lw) // 2] >= 4 and sorted(rw)[len(rw) // 2] >= 4:
            keep.append(float(x))
    return keep                                                      # bin centre *2 = points


def _split_at_x(ln: list, xs: list) -> list[list]:
    """Split a visual line at gutter x's that no glyph of the line crosses."""
    ink = [g for g in ln if not g["s"].isspace()]
    if not ink or not xs:
        return [ln]
    lx0 = min(g["x0"] for g in ink); lx1 = max(g["x1"] for g in ink)
    cut = [x for x in xs if lx0 < x < lx1 and not any(g["x0"] < x < g["x1"] for g in ink)]
    if not cut:
        return [ln]
    parts = [[] for _ in range(len(cut) + 1)]
    for g in ln:
        parts[sum((g["x0"] + g["x1"]) / 2 > x for x in cut)].append(g)
    return [p for p in parts if any(not g["s"].isspace() for g in p)]


def _split_at_strip(ln: list, strips: list, em: float) -> list[list]:
    """Split a visual line that runs into a column gutter strip at its own widest gap (>= 0.5 em) near the strip."""
    ink = sorted((g for g in ln if not g["s"].isspace()), key=lambda g: g["x0"])
    if len(ink) < 2 or not strips:
        return [ln]
    cuts = []
    for a, b in strips:
        if not (ink[0]["x0"] < a and ink[-1]["x1"] > b):
            continue                                                 # the line does not span this gutter
        best, end = None, ink[0]["x1"]
        for g in ink[1:]:
            lo, hi = end, g["x0"]
            if hi - lo >= 0.5 * em and hi > a - em and lo < b + em and (best is None or hi - lo > best[1] - best[0]):
                best = (lo, hi)
            end = max(end, g["x1"])
        if best:
            cuts.append((best[0] + best[1]) / 2)
    return _split_at_x(ln, cuts) if cuts else [ln]


def truth_lines(page, variant) -> tuple[list[dict], bool, list, list]:
    """lines.py's page_lines for one decoding variant, split at a table's vertical rules, plus each line's first
    glyph in the content stream and whether it sits in a ruled table. Also returns the table boxes (px)."""
    gl, junk = page_glyphs(page)
    for k, g in enumerate(gl):
        g["seq"] = k
    V, H = rules(page)
    tabs = ruled_tables(V, H)
    Vt = [v for v in V if any(t[0] - 3 <= v[0] <= t[2] + 3 and t[1] - 3 <= v[1] and v[2] <= t[3] + 3 for t in tabs)]
    vis = group_lines(gl)
    gut = gutters(vis)
    parts = [q for ln0 in vis for p in _split_at_x(ln0, gut) for q in _split_at_rules(p, Vt)]
    # second pass: the page's column gutters seen from the lines' edges (a line run across a gutter narrower than
    # 2.5 em, whose neighbours lines.py did split, is cut there too)
    bx = []
    for q in parts:
        ink = [g for g in q if not g["s"].isspace()]
        if ink:
            bx.append((min(g["x0"] for g in ink), min(g["y0"] for g in ink), max(g["x1"] for g in ink), max(g["y1"] for g in ink)))
    if bx:
        hs = sorted(b[3] - b[1] for b in bx)
        em2 = hs[len(hs) // 2]
        gut2 = col_gutters(bx, em2, page.rect.width, step=1, strips=True)
        parts = [r for q in parts for r in _split_at_strip(q, gut2, em2)]
    else:
        gut2 = []
    out = []
    for ln in parts:
        if True:
            ink = [g for g in ln if not g["s"].isspace()]
            if not ink:
                continue
            sizes = sorted(g["size"] for g in ink)
            b = (min(g["x0"] for g in ink), min(g["y0"] for g in ink), max(g["x1"] for g in ink), max(g["y1"] for g in ink))
            t = logical(ln, *variant)
            if not t.strip():
                continue
            cx = (b[0] + b[2]) / 2; cy = (b[1] + b[3]) / 2
            intab = any(tb[0] <= cx <= tb[2] and tb[1] <= cy <= tb[3] for tb in tabs)
            out.append(dict(text=t, box=[round(v * S, 1) for v in b], size=round(sizes[len(sizes) // 2], 2),
                            bold=sum(g["bold"] for g in ink) > 0.6 * len(ink), seq=min(g["seq"] for g in ink),
                            kind="cell" if intab else "text"))
    gstrips = [(x * S - 2, x * S + 2) for x in gut] + [(a * S, b * S) for a, b in gut2]
    return out, junk, [[round(v * S, 1) for v in tb] for tb in tabs], gstrips


# ---------------------------------------------------------------- reading order

def rows_sorted(items, em, rtl=True):
    """Top to bottom by rows (vertical centres within half a line height), each row right to left (or left to right)."""
    it = sorted(items, key=lambda x: (x["box"][1] + x["box"][3]) / 2)
    rows = []
    for x in it:
        yc = (x["box"][1] + x["box"][3]) / 2
        if rows and yc - rows[-1][0] <= 0.5 * em:
            rows[-1][1].append(x)
        else:
            rows.append([yc, [x]])
    out = []
    for _, r in rows:
        out.extend(sorted(r, key=lambda x: -x["box"][2] if rtl else x["box"][0]))
    return out


def col_gutters(boxes: list, em: float, width: float, step: float = 4, strips: bool = False) -> list:
    """x (px) of the page's column gutters: a strip at least 0.6 em wide that at most 5% of the lines cross, with at
    least 5 lines ending just right of it and 5 starting just left of it (justified columns share their edges), and
    the lines on each side 3.5 line heights wide or more (a column of list numbers is no column)."""
    if len(boxes) < 10:
        return []
    nb = int(width // step) + 2
    cover = [0] * nb; ends = [0] * nb; starts = [0] * nb
    for x0, y0, x1, y1 in boxes:
        for k in range(max(0, int(x0 // step)), min(nb, int(x1 // step) + 1)):
            cover[k] += 1
        starts[min(nb - 1, int(x1 // step))] += 1                # a line's right edge (its start, in Arabic)
        ends[max(0, int(x0 // step))] += 1                        # its left edge
    lim = max(1, 0.05 * len(boxes))
    free = [c <= lim for c in cover]
    out, k = [], 0
    reach = int(3 * em // step) + 1
    while k < nb:
        if not free[k]:
            k += 1; continue
        j = k
        while j < nb and free[j]:
            j += 1
        if (j - k) * step >= 0.6 * em and k > 0 and j < nb:
            left_side = sum(starts[max(0, k - reach):k + 1])      # lines whose right edge is just left of the strip
            right_side = sum(ends[j - 1:min(nb, j + reach)])     # lines whose left edge is just right of it
            lw = sorted(b[2] - b[0] for b in boxes if k * step - reach * step <= b[2] <= k * step + step)
            rw = sorted(b[2] - b[0] for b in boxes if j * step - step <= b[0] <= j * step + reach * step)
            wide = lw and rw and lw[len(lw) // 2] >= 3.5 * em and rw[len(rw) // 2] >= 3.5 * em   # a column each side
            if left_side >= 5 and right_side >= 5 and wide:
                out.append((k * step, j * step) if strips else (k + j) * step / 2)
        k = j
    return out


def _margin_line(it, items, em) -> bool:
    """A line (or a row of them) a line height clear of every other line above it or below it, at the page's top or bottom edge."""
    other = [x for x in items if not (it["box"][1] <= (x["box"][1] + x["box"][3]) / 2 <= it["box"][3])]
    if not other:
        return False
    return it["box"][1] > max(x["box"][3] for x in other) + 0.8 * em or it["box"][3] < min(x["box"][1] for x in other) - 0.8 * em


def order_page(lines: list[dict], tables: list[list[float]], rtl: bool = True, width: float = 2480,
               extra_strips=()) -> tuple[list, float, int]:
    """Truth lines in reading order. Lines inside a table box form one item read row by row. Column gutters are
    found on the page; an item crossing a gutter (a title, a full-width paragraph, a footnote) separates sections;
    within a section, columns are read rightmost first (on an Arabic page), each top to bottom."""
    hs = sorted(l["box"][3] - l["box"][1] for l in lines)
    em = hs[len(hs) // 2] if hs else 40
    items, used = [], set()
    for tb in tables:
        mem = [i for i, l in enumerate(lines) if i not in used and tb[0] - 5 <= (l["box"][0] + l["box"][2]) / 2 <= tb[2] + 5
               and tb[1] - 5 <= (l["box"][1] + l["box"][3]) / 2 <= tb[3] + 5]
        if mem:
            used.update(mem)
            out = rows_sorted([lines[i] for i in mem], em, rtl)
            items.append(dict(box=[min(l["box"][0] for l in out), min(l["box"][1] for l in out),
                                   max(l["box"][2] for l in out), max(l["box"][3] for l in out)], members=out, table=True))
    for i, l in enumerate(lines):
        if i not in used:
            items.append(dict(box=l["box"], members=[l], ar=any("\u0600" <= c <= "\u06ff" for c in l["text"])))
    strips = col_gutters([it["box"] for it in items if not it.get("table")], em, width, strips=True)
    for a, b in extra_strips:                                    # gutters seen while cutting the lines (truth_lines)
        if not any(a <= d and c <= b for c, d in strips):
            strips.append((a, b))
    strips.sort()
    if not strips:
        res = [m for it in rows_sorted(items, em, rtl) for m in it["members"]]
        return res, em, 1
    gut = [(a + b) / 2 for a, b in strips]
    m = 0.3 * em                                                  # crossing = reaching past both sides of the strip
    span = lambda it: any(it["box"][0] < a - m and it["box"][2] > b + m for a, b in strips)
    # the columns' body: from the first to the last line of the column items; a line wholly above or below it (a
    # running head, a page number) separates like a full-width line
    colit = [it for it in items if not span(it)]
    if colit:
        top = min(it["box"][1] for it in colit if not _margin_line(it, colit, em))
        bot = max(it["box"][3] for it in colit if not _margin_line(it, colit, em))
    else:
        top, bot = 0, 0
    sep = lambda it: span(it) or it["box"][1] > bot + 0.5 * em or it["box"][3] < top - 0.5 * em
    seps = rows_sorted([it for it in items if sep(it)], em, rtl)
    rest = [it for it in items if not sep(it)]
    res = []
    bounds = [-1e9] + [(s["box"][1] + s["box"][3]) / 2 for s in seps] + [1e9]
    ncol = 1
    for k in range(len(bounds) - 1):
        if k > 0:
            res.extend(seps[k - 1]["members"])
        sec = [it for it in rest if bounds[k] <= (it["box"][1] + it["box"][3]) / 2 < bounds[k + 1]]
        cols = [[] for _ in range(len(gut) + 1)]
        for it in sec:
            cols[sum((it["box"][0] + it["box"][2]) / 2 > g for g in gut)].append(it)
        ncol = max(ncol, sum(len(c) >= 4 for c in cols))
        for c in (cols[::-1] if rtl else cols):
            res.extend(mm for it in rows_sorted(c, em, rtl) for mm in it["members"])
    return res, em, ncol


# ---------------------------------------------------------------- Azure

def azure_doc(d: str):
    from inkscript.enrich import document, structure
    doc = document.load(doc_dir(d) / f"{d}.json")
    try:
        info = structure.analyse(doc)
    except Exception:
        info = None
    return doc, info


def azure_page(doc, info, d: str, p: int, w: int, h: int) -> dict:
    from inkscript.gold.draft import draft_page
    g = draft_page(doc, info, p, dict(stem=d, split="test"), dict(width=w, height=h), DPI)
    return g


def azure_tables(d: str, p: int) -> list[list[float]]:
    j = json.load(open(doc_dir(d) / f"{d}.json")); ar = j.get("analyzeResult", j)
    out = []
    for t in ar.get("tables", []):
        for br in t.get("boundingRegions", []):
            if br["pageNumber"] == p:
                xs = br["polygon"][0::2]; ys = br["polygon"][1::2]
                out.append([min(xs) * DPI, min(ys) * DPI, max(xs) * DPI, max(ys) * DPI])
    return out


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def concord(seq):
    n = len(seq); c = sum(seq[a] < seq[b] for a in range(n) for b in range(a + 1, n)); t = n * (n - 1) // 2
    return c / t if t else 1.0


def page_record(d, variant, pdoc, p, adoc, ainfo, want_azure=True):
    page = pdoc[p - 1]
    w = int(round(page.rect.width * S)); h = int(round(page.rect.height * S))
    lines, junk, rtabs, gstrips = truth_lines(page, variant)
    tables = rtabs + azure_tables(d, p)
    rtl = sum(any("؀" <= c <= "ۿ" for c in l["text"]) for l in lines) >= 0.5 * len(lines)
    ordered, em, nc = order_page(lines, tables, rtl, w, gstrips) if lines else ([], 40, 0)
    rec = dict(doc=d, page=p, width=w, height=h, lines=ordered, tables=tables, junk=junk, em=em, ncols=nc)
    bad = sum(any(0xE000 <= ord(c) <= 0xF8FF or c == "�" for c in l["text"]) for l in lines)
    rec["bad_lines"] = bad
    # order checks: PDF stream order and Azure's order, on the truth lines matched to an Azure line
    rec["stream_concord"] = concord([l["seq"] for l in ordered])
    if want_azure:
        ag = azure_page(adoc, ainfo, d, p, w, h)
        alines = [dict(text=l["draft"]["azure"], box=l["box"], conf=min((x["conf"] or 0) for x in l["words"]) if l["words"] else None,
                       kind=l["kind"]) for l in sorted(ag["lines"], key=lambda l: ag["order"].index(l["id"]))]
        rec["azure"] = alines
        words = [x for l in ag["lines"] for x in l["words"]]
        outside = 0
        for wd in words:
            cx = (wd["box"][0] + wd["box"][2]) / 2; cy = (wd["box"][1] + wd["box"][3]) / 2
            if not any(b["box"][0] - 6 <= cx <= b["box"][2] + 6 and b["box"][1] - 6 <= cy <= b["box"][3] + 6 for b in lines):
                outside += 1
        rec["azure_words"] = len(words); rec["azure_outside"] = outside
        seq = []
        for k, l in enumerate(ordered):
            best = max(range(len(alines)), key=lambda j: _iou(l["box"], alines[j]["box"]), default=None)
            if best is not None and _iou(l["box"], alines[best]["box"]) >= 0.3:
                seq.append(best)
        rec["azure_concord"] = concord(seq)
        rec["azure_matched"] = len(seq)
    return rec


def survey():
    import pymupdf
    sp = json.load(open(E33 / "out" / "splits.json"))["docs"]
    OUT.mkdir(parents=True, exist_ok=True)
    f = open(OUT / "bd_survey.jsonl", "w")
    for d in candidates():
        variant = tuple(sp[d]["variant"])
        pdoc = pymupdf.open(str(doc_dir(d) / f"{d}.pdf"))
        adoc, ainfo = azure_doc(d)
        lj = json.load(open(E33 / "out" / "lines" / f"{d}.json"))
        for pg in lj["pages"]:
            p = pg["page"]
            try:
                r = page_record(d, variant, pdoc, p, adoc, ainfo)
            except Exception as e:
                print(d, p, "error", e, flush=True); continue
            r["split33"] = sp[d]["split"]
            r["cells"] = sum(l["kind"] == "cell" for l in r["lines"]); r.pop("lines"); r.pop("azure")
            r["nlines"] = len(pg["lines"])
            f.write(json.dumps(r) + "\n"); f.flush()
            print(d, p, r["nlines"], r["ncols"], len(r["tables"]), r["bad_lines"], r["azure_outside"], r["azure_words"],
                  round(r["stream_concord"], 3), round(r["azure_concord"], 3), flush=True)


HARAKAT = re.compile("[\u064B-\u0652\u0670]")
AR = re.compile("[\u0621-\u064A]")
LAT = re.compile("[A-Za-z]")


def gold_text(t: str) -> str:
    """The yardstick's text rules (src/inkscript/gold/format.py) on a PDF line: presentation forms to letters, no
    tatweel, single spaces (gold.text.faithful), and Persian code points that print like Arabic letters folded
    (a Persian keyboard's ی: ى at the end of a word, ي elsewhere; ک -> ك; ھ -> ه). Digits stay as stored."""
    from inkscript.gold.text import faithful
    s = faithful(t)
    s = re.sub("\u06CC(?![\u0621-\u064A\u066E-\u06D3])", "\u0649", s).replace("\u06CC", "\u064A")
    return s.replace("\u06A9", "\u0643").replace("\u06BE", "\u0647")


def lang(t: str) -> str:
    a = len(AR.findall(t)); l = len(LAT.findall(t))
    return "ar" if l == 0 else "la" if a == 0 else "mixed"


def select(n_test=2, n_dev=1, seed=36) -> list[dict]:
    """Up to 2 pages per test document (1 per 33-dev document): a multi-column page if the document has one, else
    (for the first 16 documents with tables, by name) a table page; then a page without a table, at random."""
    R = [json.loads(l) for l in open(OUT / "bd_survey.jsonl")]
    ok = [r for r in R if r["bad_lines"] == 0 and r["azure_outside"] <= 0.05 * max(1, r["azure_words"]) and r["nlines"] >= 8]
    by = {}
    for r in ok:
        by.setdefault(r["doc"], []).append(r)
    rnd = random.Random(seed)
    out, ntab = [], 0
    for d in sorted(by):
        pages = sorted(by[d], key=lambda r: r["page"])
        k = n_test if pages[0]["split33"] == "test" else n_dev
        pick = []
        multi = [r for r in pages if r["ncols"] >= 2]
        tab = [r for r in pages if r["cells"] > 0]
        if multi:
            pick.append(rnd.choice(multi))
        elif tab and ntab < 16 and k >= 2:
            pick.append(rnd.choice(tab)); ntab += 1
        rest = [r for r in pages if r not in pick and r["cells"] == 0] or [r for r in pages if r not in pick]
        while len(pick) < k and rest:
            r = rnd.choice(rest); rest.remove(r); pick.append(r)
        out += sorted(pick, key=lambda r: r["page"])
    return out


def build():
    """Render the chosen pages and write out/pack/bd/<pid>.jpg, out/ref/bdtruth/<pid>.json, out/ref/azure/<pid>.json,
    out/bd_pages.json (their manifest rows)."""
    import pymupdf
    from inkscript.gold.draft import render
    sp = json.load(open(E33 / "out" / "splits.json"))["docs"]
    meta = json.load(open(E33 / "out" / "meta.json"))
    sel = select()
    for sub in ("pack/bd", "ref/bdtruth", "ref/azure"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    rows, cache = [], {}
    for s in sel:
        d, p = s["doc"], s["page"]
        if d not in cache:
            cache.clear()
            cache[d] = (pymupdf.open(str(doc_dir(d) / f"{d}.pdf")), *azure_doc(d))
        pdoc, adoc, ainfo = cache[d]
        r = page_record(d, tuple(sp[d]["variant"]), pdoc, p, adoc, ainfo)
        pid = f"bd_{d}_p{p:03d}"
        jpg, w, h = render(str(doc_dir(d) / f"{d}.pdf"), p, DPI)
        assert abs(w - r["width"]) <= 2 and abs(h - r["height"]) <= 2, (pid, w, h, r["width"], r["height"])
        (OUT / "pack/bd" / f"{pid}.jpg").write_bytes(jpg)
        tl = [dict(text=gold_text(l["text"]), box=l["box"], kind=l["kind"], lang=lang(l["text"])) for l in r["lines"]]
        truth = dict(page_id=pid, source="born-digital PDF text layer, experiment 33 lines.py (doc variant "
                     f"{list(sp[d]['variant'])}), split at gutters and table rules, reading order bd.py",
                     image=dict(width=w, height=h, dpi=DPI), lines=tl, tables=[], equations=[])
        json.dump(truth, open(OUT / "ref/bdtruth" / f"{pid}.json", "w"), ensure_ascii=False, indent=1)
        az = dict(page_id=pid, source="Azure Document Intelligence (Mandumah's reading), lines in Azure's order "
                  "(src/inkscript/gold/draft.py)", image=dict(width=w, height=h, dpi=DPI),
                  lines=[dict(text=l["text"], box=l["box"], conf=l["conf"], kind=l["kind"]) for l in r["azure"]])
        json.dump(az, open(OUT / "ref/azure" / f"{pid}.json", "w"), ensure_ascii=False, indent=1)
        text = " ".join(l["text"] for l in tl)
        persian = sum(c in "\u06CC\u06A9\u06BE" for l in r["lines"] for c in l["text"])
        words = text.split()
        voc = sum(bool(HARAKAT.search(wd)) for wd in words) / max(1, len(words))
        tags = []
        if r["ncols"] >= 2:
            tags.append("columns")
        if sum(l["kind"] == "cell" for l in tl) >= 6:
            tags.append("table")
        if voc >= 0.15:
            tags.append("vowelled")
        if sum(l["lang"] != "ar" for l in tl) >= 0.1 * len(tl):
            tags.append("mixed_latin")
        if p == 1:
            tags.append("first_page")
        if d.startswith("0493"):
            tags.append("magazine")
        # digits: the PDF's codes against Azure's (some producers store Western codes under Arabic-Indic glyphs)
        wd_t = len(re.findall("[0-9]", text)); ai_t = len(re.findall("[\u0660-\u0669\u06F0-\u06F9]", text))
        at = " ".join(l["text"] for l in r["azure"])
        wd_a = len(re.findall("[0-9]", at)); ai_a = len(re.findall("[\u0660-\u0669\u06F0-\u06F9]", at))
        if wd_t + ai_t >= 5 and abs(wd_t - wd_a) > 0.3 * (wd_t + ai_t):
            tags.append("digit_codes_differ")
        m = meta.get(d, {})
        yr = m.get("year")
        rows.append(dict(page_id=pid, kind="born-digital", split=sp[d]["split"], stem=d, page=p,
                         journal=m.get("journal", ""), journal_code=d[:4], year=str(yr or ""),
                         decade=f"{int(yr) // 10 * 10}s" if yr else "", tags=tags, width=w, height=h, dpi=DPI,
                         file=f"pages/{pid}.jpg", lines=len(tl), ncols=r["ncols"],
                         azure_order_agreement=round(r["azure_concord"], 3), vowelled_share=round(voc, 3),
                         persian_folded=persian, digits=dict(pdf_western=wd_t, pdf_indic=ai_t, azure_western=wd_a, azure_indic=ai_a)))
        print(pid, len(tl), tags, flush=True)
    json.dump(rows, open(OUT / "bd_pages.json", "w"), ensure_ascii=False, indent=1)
    print(len(rows), "pages")


if __name__ == "__main__":
    if sys.argv[1] == "survey":
        survey()
    elif sys.argv[1] == "build":
        build()
