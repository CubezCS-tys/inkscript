"""Experiment 94, goal 4 (report only): word boxes from the frozen reader's CTC alignment, against Azure's words.

    python words94.py [N]   -> out/words94.json, out/words94_lines.jsonl

Sample: N (default 400) Arabic lines of experiment 92's test pages (seed 94), cut from Azure's polygon exactly as
experiment 92 cut them (out/crops48/az92-*.tar of experiment 92, re-used).  The final reader (v7-28M, frozen,
sha-checked) gives per-frame log-probabilities (one frame per 4 crop pixels; the network reads the crop flipped, from its right end).  Words:
the greedy path's space frames cut the crop into segments; each segment is trimmed to its ink columns and then its ink rows (Otsu; the untrimmed full-height box is reported too); a
segment with no letter on the path is dropped.  Each segment is mapped back to the page through the cut's own
transform (common77.line_geometry, PAD_V, PAD_H) and its upright bounds compared with Azure's word polygons of that
line (by span): greedy one-to-one IoU matching (full-height boxes); reported: share of Azure words matched at IoU >= 0.5, mean IoU of
each Azure word's best match, and the count agreement (lines whose word counts are equal).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import random
import sys
import tarfile

import numpy as np
import torch

from common94 import E, E92, OUT, assert_not_locked, azure_lines, iou

sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "79_signal_reader"))
sys.path.insert(0, str(E / "92_layout"))
import common77 as C77  # noqa: E402
import read81  # noqa: E402
from common92 import azure_result  # noqa: E402
from e2e92 import arabic_share  # noqa: E402


def page_scale(pdf, p, W, H):
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(pdf)
    try:
        w, h = d[p - 1].get_size()
    finally:
        d.close()
    return (w * C77.DPI / 72 if hasattr(C77, "DPI") else w * 250 / 72) / W, h * 250 / 72 / H


def crop_to_page(poly, sx, sy, Wc, u, v):
    c, ang, w, h = C77.line_geometry(poly, sx, sy)
    ph = h * (1 + 2 * C77.PAD_V)
    s = C77.H / ph
    ca, sa = math.cos(ang), math.sin(ang)
    du, dv = (u - Wc / 2) / s, (v - C77.H / 2) / s
    return c[0] + ca * du - sa * dv, c[1] + sa * du + ca * dv


def segments(lp, crop, space_id):
    """[(u0, u1)] word extents in crop pixels from the greedy path."""
    import cv2
    path = lp.argmax(-1)
    T = len(path)
    Wc = crop.shape[1]
    stride = Wc / max(1, T)
    cuts = [t for t in range(T) if path[t] == space_id]
    bounds, prev = [], 0
    for t in cuts + [T]:
        if t > prev:
            seg = path[prev:t]
            if any(x not in (0, space_id) for x in seg):
                # the network reads the crop flipped (train89.LineSet: img[:, ::-1]): frame t covers crop columns
                # Wc - (t + 1) * stride .. Wc - t * stride
                bounds.append((Wc - t * stride, Wc - prev * stride))
        prev = t + 1
    _, ink = cv2.threshold(crop, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    col = ink.sum(axis=0) > 0
    out = []
    for u0, u1 in bounds:
        a, b = int(u0), min(Wc, int(math.ceil(u1)))
        xs = np.nonzero(col[a:b])[0]
        if len(xs):
            ys = np.nonzero(ink[:, a + xs[0]:a + xs[-1] + 1].sum(axis=1) > 0)[0]
            out.append((a + xs[0], a + xs[-1] + 1, ys[0], ys[-1] + 1))
    return out


def main(N=400):
    torch.set_num_threads(2)
    fr = json.loads((E / "89_final_reader/FINAL_READER.json").read_text())
    ckpt = E.parent / fr["weights"]
    assert hashlib.sha256(ckpt.read_bytes()).hexdigest() == fr["weights_sha256"]
    m = read81.module("train89", E / "89_final_reader/train89.py")
    cs, model = read81.image_reader(m, str(ckpt))
    space_id = cs.idx[" "]
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")}
    assert_not_locked(list(pages))
    cand = []
    for k, p in pages.items():
        L, W, H = azure_lines(p["azure"], p["page"])
        for x in L:
            if x["poly"] and arabic_share(x["text"]) >= 0.5 and len(x["text"].split()) >= 2:
                cand.append((k, x["i"]))
    random.Random(94).shuffle(cand)
    cand = cand[:N]
    want = {}
    for k, i in cand:
        want.setdefault(k, set()).add(i)
    import cv2
    rows = []
    for k, ids in sorted(want.items()):
        p = pages[k]
        L, W, H = azure_lines(p["azure"], p["page"])
        byi = {x["i"]: x for x in L}
        sx, sy = page_scale(p["pdf"], p["page"], W, H)
        words = azure_result(str(p["azure"]))["pages"][p["page"] - 1].get("words", [])
        crops = {}
        with tarfile.open(E92 / "crops48" / f"az92-{k}.tar") as t:
            for mm in t:
                if mm.name.endswith(".jpg"):
                    i = int(mm.name[-7:-4])
                    if i in ids:
                        crops[i] = cv2.imdecode(np.frombuffer(t.extractfile(mm).read(), np.uint8), cv2.IMREAD_GRAYSCALE)
        if not crops:
            continue
        # the reader on exactly these crops: a one-tar store in memory
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as t:
            for i, cr in crops.items():
                b = C77.encode(cr)
                ti = tarfile.TarInfo(f"{k}_l{i:03d}.jpg")
                ti.size = len(b)
                t.addfile(ti, io.BytesIO(b))
        tmp = OUT / "words_tmp"
        tmp.mkdir(exist_ok=True)
        (tmp / "w-000.tar").write_bytes(buf.getvalue())
        st = m.Store(str(tmp), "w")
        lps = read81.image_logprobs(m, model, st, list(range(len(st.keys))))
        for key, lp in lps.items():
            i = int(key[-3:])
            x = byi[i]
            crop = crops[i]
            o, n = x["span"]
            aw = []
            for wd in words:
                sp = wd.get("span") or {}
                if o is not None and o <= sp.get("offset", -1) < o + n and wd.get("polygon"):
                    xs, ys = wd["polygon"][0::2], wd["polygon"][1::2]
                    aw.append([min(xs), min(ys), max(xs), max(ys)])
            segs = segments(lp, crop, space_id)
            pw, pf = [], []
            for u0, u1, v0, v1 in segs:
                for vv, dst in (((v0, v1), pw), ((0, crop.shape[0]), pf)):
                    pts = [crop_to_page(x["poly"], sx, sy, crop.shape[1], u, v) for u in (u0, u1) for v in vv]
                    dst.append([min(a for a, _ in pts) / sx, min(b for _, b in pts) / sy,
                                max(a for a, _ in pts) / sx, max(b for _, b in pts) / sy])
            pairs = sorted(((iou(a, b), ia, ib) for ia, a in enumerate(aw) for ib, b in enumerate(pf)), reverse=True)
            ua, ub, matched = set(), set(), 0
            for v, ia, ib in pairs:
                if v >= 0.5 and ia not in ua and ib not in ub:
                    ua.add(ia)
                    ub.add(ib)
                    matched += 1
            best = [max((iou(a, b) for b in pw), default=0.0) for a in aw]
            best_full = [max((iou(a, b) for b in pf), default=0.0) for a in aw]
            rows.append(dict(key=key, azure_words=len(aw), reader_words=len(pw), matched=matched, boxes_azure=aw, boxes_full=pf,
                             best_iou=[round(b, 3) for b in best],
                             best_iou_full_height=[round(b, 3) for b in best_full], text=x["text"]))
    A = sum(r["azure_words"] for r in rows)
    out = dict(lines=len(rows), azure_words=A, reader_words=sum(r["reader_words"] for r in rows),
               matched_at_0_5=round(sum(r["matched"] for r in rows) / max(1, A), 4),
               mean_best_iou=round(float(np.mean([b for r in rows for b in r["best_iou"]])), 4),
               mean_best_iou_full_height=round(float(np.mean([b for r in rows for b in r["best_iou_full_height"]])), 4),
               best_iou_ge_0_5=round(float(np.mean([b >= 0.5 for r in rows for b in r["best_iou"]])), 4),
               same_word_count=round(sum(r["azure_words"] == r["reader_words"] for r in rows) / max(1, len(rows)), 4),
               lines_all_matched=round(sum(r["matched"] == r["azure_words"] for r in rows) / max(1, len(rows)), 4))
    # horizontal only: the reader's box spans the cut's full height, Azure's word box is tighter
    def xi(a, b):
        i, u = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(a[2], b[2]) - min(a[0], b[0])
        return i / u if u > 0 else 0.0
    xb = [max((xi(a, b) for b in r["boxes_full"]), default=0.0) for r in rows for a in r["boxes_azure"]]
    xm = 0
    for r in rows:
        pairs = sorted(((xi(a, b), i, j) for i, a in enumerate(r["boxes_azure"]) for j, b in enumerate(r["boxes_full"])),
                       reverse=True)
        ua, ub = set(), set()
        for v, i, j in pairs:
            if v >= 0.5 and i not in ua and j not in ub:
                ua.add(i)
                ub.add(j)
                xm += 1
    out.update(mean_best_x_iou=round(sum(xb) / max(1, len(xb)), 4), x_matched_at_0_5=round(xm / max(1, A), 4),
               x_best_ge_0_8=round(sum(b >= 0.8 for b in xb) / max(1, len(xb)), 4))
    json.dump(out, open(OUT / "words94.json", "w"), indent=1)
    with open(OUT / "words94_lines.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 400)
