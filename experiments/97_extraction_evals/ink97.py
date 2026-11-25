#!/usr/bin/env python3
"""Experiment 97, part R0: the ink ledger. The printed ink is the map.

Every connected blob of ink on the 214 exam pages is assigned to the pieces that claim it:
  once     claimed by exactly one extracted piece (block, figure, or page region)
  twice    claimed by two or more pieces
  dropped  inside an Azure line (the reader saw it) but claimed by no piece
  unseen   in no Azure line and no piece (nobody saw it)
Page regions the parser set aside as non-content (noise, pictureJunk, ornament, otherArticle, showThrough) count as a
claim, but are reported apart ("set aside") and their text-like ink is listed for the blind labellers too.

Method, per page (full 300 dpi image, boxes scaled from the ALTO page size to the JPEG size):
  1. Sauvola threshold (window WIN, k K) computed with box filters; ink = grey < T and grey < ABS_MAX.
     Sauvola, not a global Otsu: scans here have grey gradients and dark gutters; a local mean/std threshold keeps
     faint strokes in dark corners and does not turn blank paper into ink (the std term stays small on paper).
  2. 8-connected components; components below MIN_AREA pixels are specks (counted, not assigned).
  3. Component -> Azure line: line box containing the ink centroid; else line box covering >= 50% of the component
     box; else, for components smaller than a glyph, the nearest line box within NEAR_FRAC of that line's height
     (dots and diacritics just outside a tight box).
  4. Component -> pieces: line_map rows of its Azure line(s) (the ALTO sub-box containing the centre, or the nearest
     sub-box of that line); figures boxes always (container claims); block_parts and page_regions boxes only when
     line_map gave nothing. Table cells and a figure's caption count as the figure's own piece (not a double claim).
Run:  nice -n 19 ionice -c3 env OMP_NUM_THREADS=2 .venv/bin/python ink97.py [--only STEM_pNNN ...] [--force]
"""
import json, os, sqlite3, sys, time
import numpy as np
import cv2

cv2.setNumThreads(2)
HERE = os.path.dirname(os.path.abspath(__file__))
DB = "/home/appuser/data/desk/releases/R20261104T151029.db"
PAGES = "/home/appuser/inkscript/experiments/43_rehearsal/out/pages/"
OUT = f"{HERE}/out/ink"
WIN, K, R, ABS_MAX = 61, 0.25, 128.0, 215
MIN_AREA = 6           # px at 300 dpi; see SUMMARY.md for the measured speck/dot distribution
NEAR_FRAC = 0.45       # tolerance around a line box for sub-glyph components, as a share of the line height
SET_ASIDE = {"noise", "pictureJunk", "ornament", "otherArticle", "showThrough"}
FURNITURE = {"pageHeader", "pageNumber", "pageFooter"}
PICTURE_ROLES = {"pictureText", "pictureJunk", "formulaInk"}
STATUS = ["once", "twice", "dropped", "unseen"]
COL = {  # BGR
    "once": (120, 120, 120), "twice": (0, 140, 255), "dropped": (0, 0, 230), "unseen": (200, 40, 160),
    "speck": (215, 215, 215), "setaside": (140, 170, 60)}


def sauvola(g):
    f = g.astype(np.float32)
    m = cv2.boxFilter(f, -1, (WIN, WIN), borderType=cv2.BORDER_REFLECT)
    m2 = cv2.boxFilter(f * f, -1, (WIN, WIN), borderType=cv2.BORDER_REFLECT)
    s = np.sqrt(np.maximum(m2 - m * m, 0))
    t = m * (1 + K * (s / R - 1))
    return ((f < t) & (g < ABS_MAX)).astype(np.uint8)


def shape_class(x, y, w, h, area, W, H, glyph_h):
    """speck-free component -> edge | rule | grid | mass | glyph | small"""
    if (x <= 2 or y <= 2 or x + w >= W - 2 or y + h >= H - 2) and (w > 0.1 * W or h > 0.1 * H or area > 4000):
        return "edge"
    lng, sht = max(w, h), max(1, min(w, h))
    fill = area / float(w * h)
    if lng >= 12 * sht and lng >= 4 * glyph_h:
        return "rule"
    if lng >= 8 * glyph_h and area / float(lng) < 0.15 * glyph_h:
        return "rule"            # a rule with a bracket or ornament at its end; dotted leader joined into one
    if w > 6 * glyph_h and h > 4 * glyph_h and fill < 0.12:
        return "grid"            # table ruling / frame: big box, little ink
    if h > 3.5 * glyph_h and w > 3.5 * glyph_h:
        return "mass"
    if area < 0.04 * glyph_h * glyph_h:
        return "small"
    return "glyph"


def load_db():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return c


def page_inputs(c, stem, vid, page, sx, sy):
    def sc(b):
        x, y, w, h = b
        if x is None or y is None or w is None or h is None:
            return None
        return (x * sx, y * sy, w * sx, h * sy)
    nobox = []
    lines = [(r[0], sc(r[1:5]), r[5]) for r in c.execute(
        "select line_no, x, y, w, h, text from azure_lines where stem=? and page=? order by line_no", (stem, page))]
    nobox += [("azure_line", l[0]) for l in lines if l[1] is None]
    lines = [l for l in lines if l[1] is not None]
    lm = [(r[0], r[1], r[2], r[3], sc(r[4:8])) for r in c.execute(
        "select alto_line_id, azure_line_no, block_id, region_id, x, y, w, h from line_map where version_id=? and page=?",
        (vid, page))]
    bparts = [(r[0], sc(r[1:5])) for r in c.execute(
        "select block_id, x, y, w, h from block_parts where version_id=? and page=?", (vid, page))]
    regions = {r[0]: (r[1], sc(r[2:6])) for r in c.execute(
        "select region_id, role, x, y, w, h from page_regions where version_id=? and page=?", (vid, page))}
    figs = [(r[0], r[1], sc(r[2:6]), r[6]) for r in c.execute(
        "select figure_id, kind, x, y, w, h, caption_block_id from figures where version_id=? and page=?", (vid, page))]
    nobox += [("figure", f[0]) for f in figs if f[2] is None]
    figs = [f for f in figs if f[2] is not None]
    nobox += [("line_map", l[0]) for l in lm if l[4] is None]
    lm = [l for l in lm if l[4] is not None]
    nobox += [("block_part", b[0]) for b in bparts if b[1] is None]
    bparts = [b for b in bparts if b[1] is not None]
    nobox += [("region", k) for k, v in regions.items() if v[1] is None]
    regions = {k: v for k, v in regions.items() if v[1] is not None}
    roles = dict(c.execute("select block_id, role from blocks where version_id=? and (page=? or last_page>=?)",
                           (vid, page, page)).fetchall())
    owner = {}   # block -> figure piece (table cells, captions)
    for fid, bid in c.execute("select figure_id, block_id from table_cells where version_id=? and block_id is not null",
                              (vid,)):
        owner[bid] = fid
    for fid, kind, box, cap in figs:
        if cap:
            owner[cap] = fid
    angle = c.execute("select angle from pages where stem=? and page=?", (stem, page)).fetchone()[0]
    return lines, lm, bparts, regions, figs, roles, owner, angle, nobox


def contains(box, px, py, pad_x=0.0, pad_y=0.0):
    x, y, w, h = box
    return x - pad_x <= px <= x + w + pad_x and y - pad_y <= py <= y + h + pad_y


def box_dist(box, px, py):
    x, y, w, h = box
    dx = max(x - px, 0, px - (x + w))
    dy = max(y - py, 0, py - (y + h))
    return dx, dy


def overlap(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx)); iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    return ix * iy


def iou(a, b):
    o = overlap(a, b)
    return o / float(a[2] * a[3] + b[2] * b[3] - o + 1e-9)


def piece_kind(key, regions):
    if key.startswith("R:"):
        role = regions[key[2:]][0]
        return "setaside" if role in SET_ASIDE else ("furniture" if role in FURNITURE else "region")
    if key.startswith("F:"):
        return "figure"
    return "block"


def process(c, art, kind, page, force=False):
    stem, vid = art["stem"], art["version_id"]
    name = f"{stem}_p{page:03d}"
    jpath = f"{OUT}/pages/{name}.json"
    if os.path.exists(jpath) and not force:
        return json.load(open(jpath))
    g = cv2.imread(f"{PAGES}{name}.jpg", cv2.IMREAD_GRAYSCALE)
    H, W = g.shape
    wpx, hpx = c.execute("select width_px, height_px from pages where stem=? and page=?", (stem, page)).fetchone()
    sx, sy = W / wpx, H / hpx
    lines, lm, bparts, regions, figs, roles, owner, angle, nobox = page_inputs(c, stem, vid, page, sx, sy)
    ink = sauvola(g)
    n, lab, st, cen = cv2.connectedComponentsWithStats(ink, connectivity=8)
    st = st[1:]; cen = cen[1:]
    areas = st[:, 4]
    keep = areas >= MIN_AREA
    # typical glyph height: median line height of Azure lines (fallback 40 px)
    lh = np.array([b[3] for _, b, _ in lines]) if lines else np.array([40.0])
    glyph_h = float(np.median(lh)) * 0.6 if lines else 25.0
    glyph_h = max(12.0, min(glyph_h, 60.0))

    lm_by_line = {}
    for alto, aln, bid, rid, box in lm:
        lm_by_line.setdefault(aln, []).append((alto, bid, rid, box))

    def key_of(bid, rid):
        if rid:
            return "R:" + rid
        if bid in owner:
            return "F:" + owner[bid]
        return bid

    figkind = {f[0]: f[1] for f in figs}
    comps = []
    for i in np.nonzero(keep)[0]:
        x, y, w, h, a = (int(v) for v in st[i])
        cx, cy = float(cen[i][0]), float(cen[i][1])
        cls = shape_class(x, y, w, h, a, W, H, glyph_h)
        big = cls in ("rule", "grid", "mass", "edge")
        cbox = (x, y, w, h)

        def hit(box, pad=0.0):
            # glyph-sized ink: its centroid is inside the box; rules, grids, masses: half of its box is inside
            if big:
                return overlap(box, cbox) >= 0.5 * w * h
            return contains(box, cx, cy, pad, pad)
        # (a) Azure lines
        ls = [(ln, b) for ln, b, _ in lines if hit(b)]
        if len(ls) > 1:
            if big:
                bestb = max(ls, key=lambda t: overlap(t[1], cbox))[1]
            else:
                bestb = min(ls, key=lambda t: abs(t[1][1] + t[1][3] / 2 - cy))[1]
            ls = [t for t in ls if iou(t[1], bestb) > 0.7]
        ls = [t[0] for t in ls]
        how = "centre" if not big else "overlap"
        if not ls and not big:
            best, bo = None, 0
            for ln, b, _ in lines:
                o = overlap(b, cbox)
                if o > bo:
                    best, bo = ln, o
            if best is not None and bo >= 0.5 * w * h:
                ls, how = [best], "overlap"
        if not ls and not big and h < 1.2 * glyph_h and w < 2.5 * glyph_h:
            best, bd = None, 1e9
            for ln, b, _ in lines:
                dx, dy = box_dist(b, cx, cy)
                tol = NEAR_FRAC * b[3]
                if dx <= tol and dy <= tol and dx + dy < bd:
                    best, bd = ln, dx + dy
            if best is not None:
                ls, how = [best], "near"
        if not ls:
            how = "none"
        # (b) pieces
        pieces = set()
        for ln in ls:
            cand = lm_by_line.get(ln, [])
            if big:
                inside = [r for r in cand if hit(r[3])]
            else:
                inside = [r for r in cand if contains(r[3], cx, cy, 0.25 * r[3][3] if how != "centre" else 2,
                                                      NEAR_FRAC * r[3][3] if how != "centre" else 2)]
            if not inside and cand:
                inside = [min(cand, key=lambda r: sum(box_dist(r[3], cx, cy)))]
            for alto, bid, rid, box in inside:
                pieces.add(key_of(bid, rid))
        # ALTO lines with no Azure source: purely geometric
        for alto, bid, rid, box in lm_by_line.get(None, []):
            if hit(box):
                pieces.add(key_of(bid, rid))
        via = "line_map" if pieces else ""
        for fid, fk, box, cap in figs:
            if hit(box, 3):
                if ("F:" + fid) not in pieces:
                    pieces.add("F:" + fid)
                    via = via or "figure"
        # block_parts / page_regions boxes are envelopes (a block that turns a column has a box over both columns):
        # used only when neither line_map nor a figure claims the ink
        if not pieces:
            for bid, box in bparts:
                if hit(box):
                    pieces.add(key_of(bid, None))
            for rid, (role, box) in regions.items():
                if hit(box):
                    pieces.add("R:" + rid)
            if pieces:
                via = "box"
        # same piece, not a double claim: a picture-text / formula region inside a figure; an inline formula or
        # inline picture inside a text line (it is part of that line's block)
        if any(k.startswith("F:") for k in pieces):
            pieces = {k for k in pieces if not (k.startswith("R:") and regions[k[2:]][0] in PICTURE_ROLES)}
        inl = {k for k in pieces if k.startswith("F:") and figkind.get(k[2:]) in ("inline-equation", "inline-picture")}
        if inl and len(pieces) > len(inl):
            pieces -= inl
        # a figure box that only adds itself on top of a set-aside or furniture region is not a second claim of text
        if len(pieces) == 0:
            status = "dropped" if ls else "unseen"
        elif len(pieces) == 1:
            status = "once"
        else:
            status = "twice"
        pk = sorted(pieces)
        comps.append([x, y, w, h, a, round(cx, 1), round(cy, 1), cls, ls, how, pk, via, status,
                      [piece_kind(k, regions) for k in pk]])

    # region clustering of dropped / unseen / set-aside ink
    def cluster(sel):
        if not sel:
            return []
        scale = 4
        m = np.zeros((H // scale + 2, W // scale + 2), np.uint8)
        for j in sel:
            x, y, w, h = comps[j][:4]
            m[y // scale:(y + h) // scale + 1, x // scale:(x + w) // scale + 1] = 1
        gx = max(3, int(round(1.0 * glyph_h / scale)))
        gy = max(1, int(round(0.35 * glyph_h / scale)))
        m = cv2.dilate(m, np.ones((2 * gy + 1, 2 * gx + 1), np.uint8))
        nn, ll = cv2.connectedComponents(m, connectivity=8)
        groups = {}
        for j in sel:
            x, y, w, h = comps[j][:4]
            groups.setdefault(int(ll[(y + h // 2) // scale, (x + w // 2) // scale]), []).append(j)
        return list(groups.values())

    def guess(members):
        cl = [comps[j][7] for j in members]
        ar = np.array([comps[j][4] for j in members], float)
        tot = ar.sum()
        xs = [comps[j][0] for j in members]; ys = [comps[j][1] for j in members]
        xe = [comps[j][0] + comps[j][2] for j in members]; ye = [comps[j][1] + comps[j][3] for j in members]
        x0, y0 = min(xs), min(ys)
        bw, bh = max(1, max(xe) - x0), max(1, max(ye) - y0)
        fill = tot / float(bw * bh)
        g2 = glyph_h * glyph_h
        by = {}
        for k, a in zip(cl, ar):
            by[k] = by.get(k, 0) + a
        top = max(by, key=by.get)
        nglyph = sum(1 for k in cl if k == "glyph")
        n = len(members)
        # share of the ink whose centre lies in the inner 70% of the region box (a frame is hollow)
        inner = sum(comps[j][4] for j in members
                    if x0 + 0.15 * bw <= comps[j][5] <= x0 + 0.85 * bw and y0 + 0.15 * bh <= comps[j][6] <= y0 + 0.85 * bh)
        if top == "edge":
            return "scan edge / border"
        if top in ("rule", "grid") and by[top] >= 0.6 * tot:
            return "long thin rule"
        if top == "mass" and by[top] >= 0.5 * tot:
            return "large picture-like mass"
        if (bh < 0.45 * glyph_h and bw > 3 * glyph_h) or (bw < 0.45 * glyph_h and bh > 3 * glyph_h):
            return "long thin rule"          # dotted / dashed / broken rule, leader dots
        if bw > 8 * glyph_h and tot / bw < 0.15 * glyph_h:
            return "long thin rule"          # a rule ending in a bracket or ornament (round a page number)
        if bw * bh > 0.12 * W * H and inner < 0.25 * tot:
            return "frame / border ornament"
        if n >= 20 and tot / n < 0.06 * g2:
            return "halftone / speckle texture"
        if n >= 20 and fill > 0.35:
            return "shaded band / tint"
        if nglyph >= 3 and bw >= 1.2 * bh and tot >= 0.6 * g2:
            return "text-like row of glyph-sized blobs"
        if nglyph >= 4:
            return "text-like row of glyph-sized blobs"
        if tot < 0.25 * g2 or (nglyph == 0 and n <= 3):
            return "isolated speck"
        return "small mark (1-3 glyph-sized blobs)"

    regions_out = []
    for group, test in [("dropped", lambda cm: cm[12] == "dropped"), ("unseen", lambda cm: cm[12] == "unseen"),
                        ("set_aside", lambda cm: cm[12] == "once" and cm[13] == ["setaside"])]:
        sel = [j for j, cm in enumerate(comps) if test(cm)]
        for members in cluster(sel):
            xs = min(comps[j][0] for j in members); ys = min(comps[j][1] for j in members)
            xe = max(comps[j][0] + comps[j][2] for j in members); ye = max(comps[j][1] + comps[j][3] for j in members)
            ga = guess(members)
            area = int(sum(comps[j][4] for j in members))
            rid = f"{name}_{group[0]}{len(regions_out):03d}"
            crop = None
            if ga != "isolated speck":
                pad = 12
                crop = f"crops/{rid}.jpg"
                cv2.imwrite(f"{OUT}/{crop}", g[max(0, ys - pad):ye + pad, max(0, xs - pad):xe + pad],
                            [cv2.IMWRITE_JPEG_QUALITY, 85])
            setaside_role = None
            if group == "set_aside":
                rk = comps[members[0]][10][0]
                setaside_role = regions[rk[2:]][0]
            regions_out.append(dict(id=rid, group=group, box=[xs, ys, xe - xs, ye - ys], ink_area=area,
                                    n_components=len(members), guess=ga, crop=crop, setaside_role=setaside_role))

    # tallies
    tot_a = float(sum(cm[4] for cm in comps)) or 1.0
    tally = {}
    for scope, f in [("all", lambda cm: True), ("text", lambda cm: cm[7] in ("glyph", "small"))]:
        sel = [cm for cm in comps if f(cm)]
        A = float(sum(cm[4] for cm in sel)) or 1.0
        N = len(sel) or 1
        t = {"ink_px": int(sum(cm[4] for cm in sel)), "n": len(sel)}
        for s in STATUS:
            ss = [cm for cm in sel if cm[12] == s]
            t[s] = {"area": int(sum(cm[4] for cm in ss)), "n": len(ss),
                    "area_share": round(sum(cm[4] for cm in ss) / A, 6), "n_share": round(len(ss) / N, 6)}
        sub = {}
        for cm in sel:
            if cm[12] == "once":
                sub[cm[13][0]] = sub.get(cm[13][0], 0) + cm[4]
        t["once_by_piece_kind_area"] = sub
        pairs = {}
        for cm in sel:
            if cm[12] == "twice":
                k = "+".join(sorted(cm[13]))
                pairs[k] = pairs.get(k, 0) + cm[4]
        t["twice_by_pair_area"] = pairs
        tally[scope] = t
    specks = int((~keep).sum()); speck_px = int(areas[~keep].sum())
    # specks inside Azure line boxes (would be dot fragments if the speck cut were too high)
    lmask = np.zeros((H, W), np.uint8)
    for ln, b, _ in lines:
        x, y, w, h = (int(round(v)) for v in b)
        lmask[max(0, y):y + h, max(0, x):x + w] = 1
    sp = np.nonzero(~keep)[0]
    spc = np.clip(cen[sp].astype(int), 0, [W - 1, H - 1])
    inl = lmask[spc[:, 1], spc[:, 0]].astype(bool)
    speck_in_lines = dict(n=int(inl.sum()), px=int(areas[sp][inl].sum()))
    small_hist = {str(t): int(((areas >= t) & (areas < 2 * t)).sum()) for t in (1, 2, 4, 8, 16, 32)}
    small_hist_in = {}
    allc = np.clip(cen.astype(int), 0, [W - 1, H - 1]); allin = lmask[allc[:, 1], allc[:, 0]].astype(bool)
    for t in (1, 2, 4, 8, 16, 32):
        sel = (areas >= t) & (areas < 2 * t)
        small_hist_in[str(t)] = int((sel & allin).sum())
    del lmask
    res = dict(stem=stem, page=page, kind=kind, journal=art["journal"], version_id=vid, image=[W, H],
               scale=[round(sx, 5), round(sy, 5)], angle=angle, glyph_h=round(glyph_h, 1),
               params=dict(win=WIN, k=K, abs_max=ABS_MAX, min_area=MIN_AREA, near_frac=NEAR_FRAC),
               n_azure_lines=len(lines), without_box=nobox, specks=specks, speck_px=speck_px, speck_in_lines=speck_in_lines,
               area_hist_all=small_hist, area_hist_in_lines=small_hist_in,
               how_counts={h: sum(1 for cm in comps if cm[9] == h) for h in ("centre", "overlap", "near", "none")},
               tally=tally, regions=regions_out,
               comp_fields=["x", "y", "w", "h", "area", "cx", "cy", "shape", "azure_lines", "line_how", "pieces", "via",
                            "status", "piece_kinds"],
               components=comps)
    # overlay
    lut = np.zeros((n, 3), np.uint8); lut[:] = 255
    lut[1:][~keep] = COL["speck"]
    for i, cm in zip(np.nonzero(keep)[0], comps):
        col = COL[cm[12]]
        if cm[12] == "once" and cm[13] == ["setaside"]:
            col = COL["setaside"]
        lut[i + 1] = col
    ov = lut[lab]
    s = 1200.0 / W
    ov = cv2.resize(ov, (1200, int(round(H * s))), interpolation=cv2.INTER_AREA)
    for ln, b, _ in lines:
        x, y, w, h = (int(round(v * s)) for v in b)
        cv2.rectangle(ov, (x, y), (x + w, y + h), (235, 200, 150), 1)
    for r in regions_out:
        if r["guess"] == "isolated speck":
            continue
        x, y, w, h = (int(round(v * s)) for v in r["box"])
        colr = {"dropped": COL["dropped"], "unseen": COL["unseen"], "set_aside": COL["setaside"]}[r["group"]]
        cv2.rectangle(ov, (x - 2, y - 2), (x + w + 2, y + h + 2), colr, 1)
    cv2.imwrite(f"{OUT}/overlays/{name}.png", ov, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    tmp = jpath + ".tmp"
    json.dump(res, open(tmp, "w"), ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, jpath)
    return res


def main():
    args = sys.argv[1:]
    force = "--force" in args
    only = set(a for a in args if not a.startswith("--"))
    for d in ("pages", "crops", "overlays"):
        os.makedirs(f"{OUT}/{d}", exist_ok=True)
    lock = json.load(open(f"{HERE}/LOCKED_EVAL.json"))
    c = load_db()
    t0 = time.time(); k = 0
    for art in lock["articles"]:
        for kind, page in art["pages"].items():
            name = f"{art['stem']}_p{page:03d}"
            if only and name not in only:
                continue
            r = process(c, art, kind, page, force=force)
            k += 1
            ta = r["tally"]["all"]
            print(f"{k:3d} {name} {kind:6s} once {ta['once']['area_share']:.3f} twice {ta['twice']['area_share']:.3f} "
                  f"dropped {ta['dropped']['area_share']:.4f} unseen {ta['unseen']['area_share']:.4f} "
                  f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
