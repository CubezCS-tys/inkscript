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
                chd = 0.5 * (self.dists[c][b["edge"]].mean() + b["dist"][self.edges[c]].mean())
                if chd <= self.ch:
                    self.counts[c] += 1; return c
        self.protos.append(b); self.fills.append(b["fill"]); self.edges.append(b["edge"]); self.dists.append(b["dist"]); self.counts.append(1)
        ci = len(self.protos) - 1; self.index.setdefault(self.key(b), []).append(ci); return ci

    def __len__(self): return len(self.protos)
