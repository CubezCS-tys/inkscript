"""A shape alphabet: group identical ink shapes across pages, scale-normalised
per page and compared as outlines. Used to measure how far a page's shapes
repeat (saturation) and whether grouped shapes really carry the same text
(purity). Not yet used to share glyphs inside the PDFs."""
from __future__ import annotations
import numpy as np, cv2

C = 48          # normalised canvas
IOU_T = 0.75    # filled-outline overlap required
CH_T = 1.5      # mean boundary distance allowed (canvas px)
GATE = 0.12     # size gate in page units


def canvas(paths, holes, w, h):
    """Outline drawn into CxC, aspect preserved. Returns (fill, boundary, distance transform)."""
    s = (C - 2) / max(w, h, 1)
    ox, oy = (C - w * s) / 2, (C - h * s) / 2
    img = np.zeros((C, C), np.uint8)
    for p, hole in zip(paths, holes):
        pts = (p * s + [ox, oy]).astype(np.int32)
        cv2.fillPoly(img, [pts], 0 if hole else 255)
    fill = img > 0
    edge = fill ^ cv2.erode(img, np.ones((3, 3), np.uint8)).astype(bool)
    dist = cv2.distanceTransform((~edge).astype(np.uint8), cv2.DIST_L2, 3)
    return fill, edge, dist


def prepare(blobs, origin=(0, 0)):
    """Give each blob its normalised canvas and size in page units (median letter height)."""
    hs = [b["h"] for b in blobs if b["w"] * b["h"] >= 40]
    unit = float(np.median(hs)) if hs else 1.0
    ox, oy = origin
    for b in blobs:
        b["hu"], b["wu"] = b["h"] / unit, b["w"] / unit
        local = [p - [ox, oy] - [b["x"] - ox, b["y"] - oy] for p in b["paths"]]
        b["fill"], b["edge"], b["dist"] = canvas([p - [b["x"], b["y"]] for p in b["paths"]], b["holes"], b["w"], b["h"])
    return unit


class Alphabet:
    """Greedy dictionary of shapes; assign() returns the shape id for a blob."""

    def __init__(self, iou=IOU_T, ch=CH_T, gate=GATE):
        self.iou, self.ch, self.gate = iou, ch, gate
        self.protos, self.fills, self.edges, self.dists, self.counts, self.index = [], [], [], [], [], {}

    @staticmethod
    def key(b): return (int(b["hu"] * 8), int(b["wu"] * 8))

    def assign(self, b) -> int:
        kh, kw = self.key(b); cands = []
        for dh in (-1, 0, 1):
            for dw in (-1, 0, 1):
                cands += self.index.get((kh + dh, kw + dw), [])
        cands = [c for c in cands if abs(self.protos[c]["hu"] - b["hu"]) <= self.gate * max(b["hu"], 0.3)
                 and abs(self.protos[c]["wu"] - b["wu"]) <= self.gate * max(b["wu"], 0.3)]
        if cands:
            F = np.stack([self.fills[c] for c in cands])
            inter = np.logical_and(F, b["fill"]).sum((1, 2)); union = np.logical_or(F, b["fill"]).sum((1, 2))
            iou = inter / np.maximum(union, 1)
            for o in np.argsort(-iou)[:5]:
                if iou[o] < self.iou: break
                c = cands[o]
                chd = 0.5 * (float(self.dists[c][b["edge"]].mean()) + float(b["dist"][self.edges[c]].mean()))
                if chd <= self.ch:
                    self.counts[c] += 1; return c
        self.protos.append(b); self.fills.append(b["fill"]); self.edges.append(b["edge"]); self.dists.append(b["dist"].astype(np.float16)); self.counts.append(1)
        ci = len(self.protos) - 1; self.index.setdefault(self.key(b), []).append(ci); return ci

    def assign_and_release(self, b) -> int:
        """assign(), then drop the matching arrays from a blob that did not
        become a prototype. A 238-page document holds ~400k blobs; keeping
        three 48x48 arrays on each of them ran the machine out of memory."""
        ci = self.assign(b)
        if self.protos[ci] is not b:
            for k in ("fill", "edge", "dist"):
                b.pop(k, None)
        return ci

    def __len__(self): return len(self.protos)


# ---- the alphabet as artifacts: knowledge about the document's ink, never a
# drawing shortcut. The pages keep every occurrence's own outline.

def prototypes(A: "Alphabet"):
    """Shape ids ranked by frequency, with each prototype's outline in its own pixel frame."""
    order = sorted(range(len(A)), key=lambda c: -A.counts[c])
    out = []
    for rank, c in enumerate(order):
        p = A.protos[c]
        out.append(dict(id=c, rank=rank, count=A.counts[c], w=p["w"], h=p["h"], page=p.get("page"),
                        paths=[(q - [p["x"], p["y"]]).tolist() for q in p["paths"]], holes=p["holes"]))
    return out


def to_json(A, path, placements):
    import json
    doc = dict(shapes=len(A), blobs=sum(A.counts), alphabet=prototypes(A), placements=placements)
    path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def to_svg(A, path, cols=16, cell=96):
    """One <symbol> per shape, plus a sheet laying them out by frequency — a
    typeface specimen a browser can open, with each shape addressable by id."""
    import html
    protos = prototypes(A)
    rows = -(-len(protos) // cols)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             f'width="{cols * cell}" height="{rows * (cell + 18)}" viewBox="0 0 {cols * cell} {rows * (cell + 18)}">',
             "<style>text{font:11px ui-monospace,monospace;fill:#666}</style><defs>"]
    for p in protos:
        d = " ".join("M" + " L".join(f"{x},{y}" for x, y in q) + " Z" for q in p["paths"])
        parts.append(f'<symbol id="s{p["id"]}" viewBox="0 0 {max(1, p["w"])} {max(1, p["h"])}"><path d="{d}" fill-rule="evenodd"/></symbol>')
    parts.append("</defs>")
    for k, p in enumerate(protos):
        r, c = divmod(k, cols); s = min((cell - 12) / max(p["w"], p["h"], 1), 3.0)
        w, h = p["w"] * s, p["h"] * s
        x, y = c * cell + (cell - w) / 2, r * (cell + 18) + 4
        parts.append(f'<use xlink:href="#s{p["id"]}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}"/>'
                     f'<text x="{c * cell + 3}" y="{r * (cell + 18) + cell + 12}">{p["id"]}:{p["count"]}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def to_sheet(A, path, cols=16, cell=64, limit=320):
    """PNG glyph sheet of the most frequent shapes, drawn from their outlines."""
    protos = prototypes(A)[:limit]
    rows = max(1, -(-len(protos) // cols))
    sheet = np.full((rows * (cell + 18), cols * cell), 255, np.uint8)
    for k, p in enumerate(protos):
        s = min((cell - 8) / max(p["w"], p["h"], 1), 3.0)
        g = np.full((max(1, int(p["h"] * s) + 1), max(1, int(p["w"] * s) + 1)), 255, np.uint8)
        for q, hole in zip(p["paths"], p["holes"]):
            cv2.fillPoly(g, [(np.array(q) * s).astype(np.int32)], 255 if hole else 0)
        r, c = divmod(k, cols); y0, x0 = r * (cell + 18) + 4, c * cell + (cell - g.shape[1]) // 2
        h, w = min(g.shape[0], cell - 8), min(g.shape[1], cell)
        sheet[y0:y0 + h, x0:x0 + w] = g[:h, :w]
        cv2.putText(sheet, f"{p['id']}:{p['count']}", (c * cell + 2, r * (cell + 18) + cell + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, 0, 1, cv2.LINE_AA)
    cv2.imwrite(str(path), sheet)
