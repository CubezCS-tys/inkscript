"""Blobs handed to words and lines: which ink belongs to which Azure box,
page furniture set aside, superscript marker lines folded into their row,
boxes carrying several tokens split into one glyph per token."""
from __future__ import annotations

from ..text import norm

def overlap(a0, a1, b0, b1):
    return max(0, min(a1, b1) - max(a0, b0))


def layout_page(pwords, texts, az_lines, blobs, sx, sy):
    """Words in pixels grouped into lines, each with its ink blobs. Returns (lines, stray blobs)."""
    wpx = []
    for b, t in zip(pwords, texts):
        x0, y0, x1, y1 = b["box"]
        wpx.append(dict(x0=x0 * sx, y0=y0 * sy, x1=x1 * sx, y1=y1 * sy, off=b["off"], text=t or "", az=b["text"], blobs=[]))
    lines = []
    for L in az_lines:
        lo = L["spans"][0]["offset"]; hi = lo + L["spans"][0]["length"]
        ws = [w for w in wpx if lo <= w["off"] < hi]
        if ws:
            lines.append(ws)
    seen = {id(w) for L in lines for w in L}
    lines += [[w] for w in wpx if id(w) not in seen]

    # Superscript footnote markers — `(2)` beside a body line — come back from
    # Azure as lines of their own, sitting vertically between two body lines.
    # As separate text objects their boxes overlap both neighbours, and pdfium
    # then merges or reorders the lines around them. Fold a short line into
    # the line it sits beside: same row (vertical overlap over half its own
    # height), no horizontal overlap, and clearly smaller than that line.
    def box(L): return min(w["x0"] for w in L), min(w["y0"] for w in L), max(w["x1"] for w in L), max(w["y1"] for w in L)
    merged = True
    while merged:
        merged = False
        for i, A in enumerate(lines):
            if len(A) > 2: continue
            ax0, ay0, ax1, ay1 = box(A); ah = ay1 - ay0
            for k, Bl in enumerate(lines):
                if k == i or len(Bl) <= 2: continue
                bx0, by0, bx1, by1 = box(Bl); bh = by1 - by0
                if overlap(ay0, ay1, by0, by1) > 0.5 * ah and overlap(ax0, ax1, bx0, bx1) <= 0:
                    Bl.extend(A); del lines[i]; merged = True; break
            if merged: break

    for bl in blobs:
        inside = [w for w in wpx if w["x0"] <= bl["cx"] <= w["x1"] and w["y0"] <= bl["cy"] <= w["y1"]]
        if inside:
            bl["word"] = min(inside, key=lambda w: (w["x1"] - w["x0"]) * (w["y1"] - w["y0"])); continue
        best = max(wpx, key=lambda w: overlap(bl["x"], bl["x"] + bl["w"], w["x0"], w["x1"]) * overlap(bl["y"], bl["y"] + bl["h"], w["y0"], w["y1"]), default=None)
        if best and overlap(bl["x"], bl["x"] + bl["w"], best["x0"], best["x1"]) * overlap(bl["y"], bl["y"] + bl["h"], best["y0"], best["y1"]) > 0:
            bl["word"] = best; continue
        for L in lines:                                   # dots and marks just outside their word's box
            lh = max(w["y1"] for w in L) - min(w["y0"] for w in L)
            if min(w["y0"] for w in L) - 0.3 * lh <= bl["cy"] <= max(w["y1"] for w in L) + 0.1 * lh:
                cands = [w for w in L if overlap(bl["x"], bl["x"] + bl["w"], w["x0"], w["x1"]) > 0]
                if cands:
                    bl["word"] = min(cands, key=lambda w: abs((w["x0"] + w["x1"]) / 2 - bl["cx"])); break
    for bl in blobs:                                      # rules are furniture, not letters
        w = bl["word"]
        if w is not None and bl["w"] > 8 * bl["h"] and not (w["y0"] <= bl["cy"] <= w["y1"]):
            bl["word"] = None
    for bl in blobs:
        if bl["word"] is not None:
            bl["word"]["blobs"].append(bl)
    stray = [bl for bl in blobs if bl["word"] is None]

    for L in lines:                                       # punctuation that rode on a neighbour gets its own box back
        for k, w in enumerate(L):
            if not w["text"].strip() and w["blobs"]:
                w["text"] = w["az"]
                for nb in (L[k - 1] if k else None, L[k + 1] if k + 1 < len(L) else None):
                    if nb and nb["text"].endswith(" " + w["az"]):
                        nb["text"] = nb["text"][: -len(w["az"]) - 1]; break

    def split_tokens(w, lh):
        toks = w["text"].split()
        if len(toks) < 2 or not w["blobs"]:
            return [w]
        bs = sorted(w["blobs"], key=lambda b: b["x"])
        groups, cur = [], [bs[0]]
        for b in bs[1:]:
            if b["x"] - max(c["x"] + c["w"] for c in cur) > 0.12 * lh:
                groups.append(cur); cur = [b]
            else:
                cur.append(b)
        groups.append(cur)
        if len(groups) != len(toks):
            return [w]
        return [dict(w, text=t, az=t, blobs=g, x0=min(b["x"] for b in g), x1=max(b["x"] + b["w"] for b in g))
                for g, t in zip(groups, reversed(toks))]
    for L in lines:
        lh = max(w["y1"] for w in L) - min(w["y0"] for w in L)
        L[:] = [g for w in L for g in split_tokens(w, lh)]
    return lines, stray
