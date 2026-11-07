"""The final reader (v7-28M) as a small local service for the Desk's "Try our reader" page (2026-11-06).

    nice -n 19 ../81_heldout_scale/out/venv/bin/python serve_reader.py [--port 8171]      (or ./serve_reader.sh)

    POST /read     body = the image bytes (PNG / JPEG / WebP / BMP, at most 5 MB, at most 40 megapixels)
                   -> {text, chars, alternatives, inverted, lines[{box, crop, text, chars, alternatives}], ms, ...}
    GET  /health   -> {ok, model, params}

Bound to 127.0.0.1 only.  Nothing is written to disk or logged about an image: it is decoded in memory, read, and
dropped when the request ends (the access log is switched off).

Preprocessing is the one experiment 86 used to read arbitrary line images (prep86.py, unchanged, imported): the image
is laid on white, made grey (BT.601), inverted when the ink is lighter than the ground (prep86.polarity), the ink box
is found and turned into the polygon Azure would have drawn (calib86.json, fitted on our own dev crops), and the line
is cut by experiment 77's common77.cut_line(test=True) at height 48.  Several lines: prep86.split_lines (our simple
horizontal-profile splitter) gives each line's ink box, top to bottom.  The network input is then exactly the one of
train89.py's LineSet + collate (flipped left-right, padded with white to a multiple of 8, ink -> positive).

Reading: greedy CTC (as every score of experiment 89) gives `text`; a small CTC prefix beam (width 8) gives up to 3
alternatives.  Per-character confidence = the highest probability the character got in the frames that emitted it.
One request reads at a time (a lock), on 2 CPU threads.
"""
from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import math
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "86_public_bench"))
import prep86  # noqa: E402  (brings common77 too)

MAX_BYTES = 5 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_SIDE = 12000
MAX_LINES = 60
MAX_CROP_W = 6000          # a "line" wider than this after scaling to 48 px is not read (a page of noise)
BEAM = 8


def _load_train89():
    spec = importlib.util.spec_from_file_location("train89", HERE / "train89.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["train89"] = m
    spec.loader.exec_module(m)
    return m


T = _load_train89()
CAL = json.loads((E / "86_public_bench/out/calib86.json").read_text())
FINAL = json.loads((HERE / "FINAL_READER.json").read_text())


class Model:
    def __init__(self, ckpt: Path):
        ck = torch.load(ckpt, map_location="cpu", weights_only=False)
        mm = ck["meta"]
        self.cs = T.Charset(mm["chars"])
        self.model = T.Reader(len(self.cs), arch=mm.get("arch", "lstm"), hid=mm.get("hid", 384), cw=mm.get("cw", 1.0),
                              feat=mm.get("feat", 384)).to(memory_format=torch.channels_last)
        self.model.load_state_dict(ck["model"])
        self.model.eval()
        self.params = int(mm.get("params") or sum(p.numel() for p in self.model.parameters()))
        self.lock = threading.Lock()

    @torch.no_grad()
    def probs(self, crops: list[np.ndarray]) -> list[np.ndarray]:
        """Per-line (frames, classes) softmax, in visual order (frame 0 = the line's right end)."""
        out = []
        for crop in crops:                       # one line at a time: no padding effects, little memory
            batch = [(np.ascontiguousarray(crop[:, ::-1]), [], 0)]
            x, widths, _, _ = T.collate(batch)
            lo = self.model(x, widths // 4).float()
            n = int(widths[0] // 4)
            out.append(lo[0, :n].softmax(-1).numpy())
        return out


# ------------------------------------------------------------------------------------------------ decoding

def _perm_from_visual(v: str) -> list[int]:
    """Indices into v in the order from_visual(v) lays its characters out (so per-character data follows)."""
    s, idx = v[::-1], list(range(len(v)))[::-1]
    if not T._ARABIC.search(s):
        s2, idx2 = s[::-1], idx[::-1]
    else:
        idx2 = list(idx)
        for m in T._RUNS.finditer(s):
            a, z = m.span()
            idx2[a:z] = idx2[a:z][::-1]
    return idx2[::-1]


def greedy_chars(p: np.ndarray, cs) -> tuple[str, list[dict]]:
    ids = p.argmax(-1)
    vis, conf, prev = [], [], 0
    for t, i in enumerate(ids.tolist()):
        if i != 0 and i != prev:
            vis.append(cs.chars[i - 1])
            conf.append(float(p[t, i]))
        elif i != 0 and i == prev:
            conf[-1] = max(conf[-1], float(p[t, i]))
        prev = i
    v = "".join(vis)
    text = T.from_visual(v)
    order = _perm_from_visual(v)
    chars = [dict(c=vis[k], p=round(conf[k], 3)) for k in order]
    assert "".join(c["c"] for c in chars) == text
    return text, chars


def beam(p: np.ndarray, cs, width: int = BEAM, n_best: int = 3) -> list[dict]:
    """CTC prefix beam search (probabilities in log space); candidate classes per frame: the top 6 plus blank."""
    lp = np.log(np.maximum(p, 1e-12))
    NEG = -1e30

    def lse(a, b):
        if a < b:
            a, b = b, a
        return a if b <= NEG else a + math.log1p(math.exp(b - a))

    beams = {(): (0.0, NEG)}                     # prefix -> (log p ending in blank, log p ending in non-blank)
    for t in range(lp.shape[0]):
        row = lp[t]
        cand = np.argpartition(-row, 6)[:6]
        nb = {}
        for pre, (pb, pnb) in beams.items():
            tot = lse(pb, pnb)
            b0, n0 = nb.get(pre, (NEG, NEG))
            nb[pre] = (lse(b0, tot + row[0]), n0)          # blank
            for c in cand.tolist():
                if c == 0:
                    continue
                q = row[c]
                ext = pre + (c,)
                b1, n1 = nb.get(ext, (NEG, NEG))
                if pre and pre[-1] == c:
                    nb[ext] = (b1, lse(n1, pb + q))                     # repeat needs a blank between
                    b0, n0 = nb[pre]
                    nb[pre] = (b0, lse(n0, pnb + q))                    # collapse into the same character
                else:
                    nb[ext] = (b1, lse(n1, tot + q))
        beams = dict(sorted(nb.items(), key=lambda kv: -lse(*kv[1]))[:width])
    ranked = sorted(beams.items(), key=lambda kv: -lse(*kv[1]))
    out, seen = [], set()
    for pre, sc in ranked:
        s = T.from_visual("".join(cs.chars[i - 1] for i in pre))
        if s in seen:
            continue
        seen.add(s)
        out.append(dict(text=s, logp=round(float(lse(*sc)), 3)))
        if len(out) == n_best:
            break
    return out


# ------------------------------------------------------------------------------------------------ images

class Refused(Exception):
    pass


def image_size(b: bytes):
    """(w, h) from the PNG / JPEG header, before decoding (so a decompression bomb is refused cheaply); None if the
    format is not one we parse here (cv2 then decodes and the size is checked after)."""
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        j = 2
        while j < len(b) - 9:
            if b[j] != 0xFF:
                j += 1
                continue
            m = b[j + 1]
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", b[j + 5:j + 9])
                return w, h
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                j += 2
                continue
            j += 2 + ((b[j + 2] << 8) | b[j + 3])
    return None


def decode_grey(b: bytes) -> np.ndarray:
    if len(b) > MAX_BYTES:
        raise Refused(f"the image is {len(b) / 1e6:.1f} MB; the limit is 5 MB")
    sz = image_size(b)
    if sz and (sz[0] * sz[1] > MAX_PIXELS or max(sz) > MAX_SIDE):
        raise Refused(f"the image is {sz[0]} x {sz[1]} pixels; the limit is 40 megapixels (a crop of the lines works best)")
    a = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_UNCHANGED)
    if a is None:
        raise Refused("this is not an image we can open (PNG, JPEG, WebP or BMP)")
    if a.shape[0] * a.shape[1] > MAX_PIXELS or max(a.shape[:2]) > MAX_SIDE:
        raise Refused("the image is too large; the limit is 40 megapixels")
    if a.dtype != np.uint8:
        a = (a.astype(np.float32) / (65535.0 if a.dtype == np.uint16 else float(a.max() or 1)) * 255).astype(np.uint8)
    if a.ndim == 3 and a.shape[2] == 4:                     # prep86.load_grey, from bytes
        al = a[..., 3:4].astype(np.float32) / 255.0
        a = (a[..., :3].astype(np.float32) * al + 255.0 * (1 - al)).astype(np.uint8)
    if a.ndim == 3:
        a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    return np.ascontiguousarray(a)


def png_data_url(crop: np.ndarray) -> str:
    ok, b = cv2.imencode(".png", crop)
    return "data:image/png;base64," + base64.b64encode(b.tobytes()).decode("ascii")


def split_lines(g: np.ndarray):
    """prep86.split_lines with one change: the line pitch for cutting touching lines is the median distance between
    the bands' starts (only when there are several bands), not the row profile's autocorrelation peak.  On a single
    line image the autocorrelation peak sits at the smallest lag searched (6 rows), and prep86's rule then cut one line
    into 6-11 slivers (measured on 5 of 5 judge crops, 2026-11-06); exp 86 only ever ran it on whole pages."""
    thr, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = g <= thr
    rows = ink.sum(1) > 0
    bands, y = [], 0
    while y < len(rows):
        if rows[y]:
            s = y
            while y < len(rows) and rows[y]:
                y += 1
            bands.append([s, y])
        y += 1
    if not bands:
        return []
    med = float(np.median([b[1] - b[0] for b in bands]))
    merged = []
    for b in bands:                                         # (prep86: dots and marks join the nearest band)
        if b[1] - b[0] < 0.3 * med and merged and (b[0] - merged[-1][1]) < 0.6 * med:
            merged[-1][1] = b[1]
        elif merged and (merged[-1][1] - merged[-1][0]) < 0.3 * med and b[0] - merged[-1][1] < 0.6 * med:
            merged[-1][1] = b[1]
        else:
            merged.append(list(b))
    # the pitch comes from bands inside the image (a band touching the top or bottom edge may be a cut-off sliver of
    # a neighbour line): with fewer than two inside bands, nothing is cut
    inner = [m for m in merged if m[0] > 1 and m[1] < len(rows) - 1]
    big = [m for m in inner if m[1] - m[0] >= 0.3 * max(m[1] - m[0] for m in inner)] if inner else []
    if len(big) >= 2:
        prof = ink.sum(1).astype(np.float64)
        starts = [m[0] for m in big]
        hs = sorted(m[1] - m[0] for m in big)
        pitch = float(np.median(np.diff(starts)))
        pitch = min(pitch, 1.6 * hs[len(hs) // 2]) if pitch > 0 else hs[len(hs) // 2]
        cut = []
        for a, z in merged:
            n = int(round((z - a) / pitch))
            if (z - a) > 1.5 * pitch and n >= 2:
                edges = [a]
                for k in range(1, n):
                    c = a + k * (z - a) / n
                    w0, w1 = int(c - pitch * 0.3), int(c + pitch * 0.3) + 1
                    edges.append(w0 + int(np.argmin(prof[w0:w1])))
                edges.append(z)
                cut += [[edges[k], edges[k + 1]] for k in range(n)]
            else:
                cut.append([a, z])
        merged = cut
        med = float(np.median([z - a for a, z in merged]))
    out = []
    for a, z in merged:
        if z - a < 0.3 * med:
            continue
        bb = prep86.ink_box(g[a:z])
        if bb is None:
            continue
        out.append((bb[0], bb[1] + a, bb[2], bb[3] + a))
    return out


def cuts(g: np.ndarray, bg: float):
    """[(box, crop)] top to bottom: our splitter's lines when it finds several, else the whole image's ink box."""
    boxes = split_lines(g)
    boxes = [b for b in boxes if b[3] - b[1] >= 6]          # 1-5 px bands: halftone stripes or rules, not lines
    if boxes:
        # a screenshot of one line often catches the next line's feet or the last line's heads at its edges: a band
        # touching the top or bottom edge that is under 60% of the tallest is such a sliver, and any band under 35%
        # of the tallest is a stray mark (on 12 judge crops of one line, 5 had such slivers before this rule)
        hmax = max(b[3] - b[1] for b in boxes)
        H0 = g.shape[0]
        boxes = [b for b in boxes if (b[3] - b[1]) >= 0.35 * hmax and
                 not ((b[1] <= 1 or b[3] >= H0 - 1) and (b[3] - b[1]) < 0.6 * hmax)]
    if not boxes:
        b = prep86.ink_box(g)
        boxes = [b] if b is not None else []
    if len(boxes) > MAX_LINES:
        raise Refused(f"{len(boxes)} lines found; this page reads at most {MAX_LINES} (crop a part of the page)")
    out = []
    for b in boxes:
        crop, _ = prep86.cut_from_box(g, b, CAL, bg)
        if crop is None or crop.shape[1] > MAX_CROP_W:
            continue
        out.append(([int(round(v)) for v in b], crop))
    if not out and len(boxes) > 1:                          # nothing usable from the split: read the whole ink box
        b = prep86.ink_box(g)
        crop = prep86.cut_from_box(g, b, CAL, bg)[0] if b is not None else None
        if crop is not None and crop.shape[1] <= MAX_CROP_W:
            out.append(([int(round(v)) for v in b], crop))
    return out


def read(model: Model, b: bytes) -> dict:
    t0 = time.perf_counter()
    g0 = decode_grey(b)
    g, inv, bg = prep86.polarity(g0)
    pieces = cuts(g, bg)
    if not pieces:
        raise Refused("no ink found in the image")
    with model.lock:
        t1 = time.perf_counter()
        P = model.probs([c for _, c in pieces])
        lines = []
        for (box, crop), p in zip(pieces, P):
            text, chars = greedy_chars(p, model.cs)
            alts = [a for a in beam(p, model.cs) if a["text"] != text][:3]
            lines.append(dict(box=box, crop=png_data_url(crop), crop_w=int(crop.shape[1]), text=text, chars=chars,
                              alternatives=alts))
        t2 = time.perf_counter()
    one = lines[0] if len(lines) == 1 else None
    return dict(text="\n".join(l["text"] for l in lines), chars=one["chars"] if one else None,
                alternatives=one["alternatives"] if one else [], inverted=bool(inv), lines=lines,
                size=[int(g0.shape[1]), int(g0.shape[0])], model=FINAL["name"], params=model.params,
                ms=round((time.perf_counter() - t0) * 1000), ms_read=round((t2 - t1) * 1000))


# ------------------------------------------------------------------------------------------------ server

_WRITE_LOCK = threading.Lock()


def write(body: bytes) -> dict:
    """POST /write (experiment 87's writer): JSON {crop: the line crop the reader returned (PNG data URL or base64),
    text: its reading} -> the line written by the writer in the style fitted to this crop (written, overlay PNGs, IoU,
    chamfer, ms).  Imported on first use; nothing is stored."""
    try:
        d = json.loads(body.decode("utf-8"))
        crop, text = d["crop"], str(d["text"])
    except (ValueError, KeyError, TypeError):
        raise Refused("send JSON with the line crop and its reading")
    if not text.strip():
        raise Refused("there is no reading to write")
    if len(text) > 300:
        raise Refused("the reading is too long for one line")
    b64 = crop.split(",", 1)[1] if crop.startswith("data:") else crop
    g = decode_grey(base64.b64decode(b64))
    if g.shape[0] != 48:
        g = cv2.resize(g, (max(8, int(round(g.shape[1] * 48 / g.shape[0]))), 48), interpolation=cv2.INTER_AREA)
    if g.shape[1] > 2400:
        raise Refused("the line is too wide to write")
    sys.path.insert(0, str(E / "87_writer"))
    import write87
    with _WRITE_LOCK:
        return write87.fit_write(g, text)


class Handler(BaseHTTPRequestHandler):
    model: Model = None
    server_version = "reader89"

    def log_message(self, fmt, *args):        # no access log: nothing about an upload is kept
        pass

    def _json(self, code: int, obj: dict):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/health":
            return self._json(200, dict(ok=True, model=FINAL["name"], params=self.model.params))
        self._json(404, dict(detail="not found"))

    def do_POST(self):
        if self.path not in ("/read", "/write"):
            return self._json(404, dict(detail="not found"))
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            return self._json(400, dict(detail="send the image as the request body"))
        if n > MAX_BYTES:
            return self._json(413, dict(detail=f"the image is {n / 1e6:.1f} MB; the limit is 5 MB"))
        b = self.rfile.read(n)
        try:
            if self.path == "/write":
                return self._json(200, write(b))
            return self._json(200, read(self.model, b))
        except Refused as e:
            return self._json(422, dict(detail=str(e)))
        except Exception as e:                  # noqa: BLE001
            return self._json(500, dict(detail=f"the {'writer' if self.path == '/write' else 'reader'} failed: {type(e).__name__}"))
        finally:
            del b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8171)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    torch.set_num_interop_threads(1)
    cv2.setNumThreads(1)
    # READER_WEIGHTS (absolute path) overrides FINAL_READER.json, e.g. exp 91's t91 (2026-11-06)
    w = os.environ.get("READER_WEIGHTS")
    Handler.model = Model(Path(w) if w else E.parent / FINAL["weights"])
    if w:
        FINAL["name"] = os.environ.get("READER_NAME", Path(w).parent.name)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"reader {FINAL['name']} ({Handler.model.params:,} parameters) on http://127.0.0.1:{a.port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
