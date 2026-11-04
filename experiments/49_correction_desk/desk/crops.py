"""Ink crops for the screens (DESIGN §9 `/evidence/crop`): a JPEG of some ALTO lines, a block, or an ink anchor,
cut from the 300 dpi page image `experiments/43_rehearsal/out/pages/<stem>_pNNN.jpg`.

- The stem and page are checked against the reading (documents + pages); the file name comes from the reading's
  `pages.page_image_key`, never from the request, and must resolve inside the pages folder.
- Boxes are in the ALTO pixel frame (`pages.width_px` × `height_px`, e.g. 1808.3 × 2729.2), the image is
  `image_w` × `image_h` (e.g. 1812 × 2730): each box is scaled by image/ALTO per axis (~1.002).
- ALTO lines come from the reading's `line_map` (the masters' TextLine boxes, per version); a line id missing
  there is looked up in the ALTO master itself (`v33_300_final/masters`, `v33_300b_fix3/masters`).
- Crops are cached on disk under DESK_CROPS (default /home/appuser/data/desk/crops), named by a hash of what was
  cut, so a second request is a file read."""
from __future__ import annotations

import hashlib
import io
import os
import re
from pathlib import Path

E43 = Path(__file__).resolve().parents[2] / "43_rehearsal" / "out"
PAGES = E43 / "pages"
MASTERS = [E43 / "v33_300_final" / "masters", E43 / "v33_300b_fix3" / "masters"]
LINE_ID = re.compile(r"p\d{1,4}b\d{1,4}l\d{1,4}")
BLOCK_ID = re.compile(r"p\d{1,4}[a-z]\d{1,4}")
ANCHOR = re.compile(r"[0-9A-Za-z,\-]+\|p\d{1,4}\|(w\d+-\d+|b[\d.]+,[\d.]+,[\d.]+,[\d.]+)")
PAD = 14
MAX_W = 1600


class CropError(ValueError):
    def __init__(self, status: int, msg: str):
        super().__init__(msg)
        self.status = status


def crops_dir() -> Path:
    return Path(os.environ.get("DESK_CROPS", "/home/appuser/data/desk/crops"))


def _alto_lines(stem: str, ids: set[str]) -> list[tuple]:
    """Boxes of TextLines straight from an ALTO master (fallback when line_map lacks them)."""
    from lxml import etree
    for d in MASTERS:
        f = d / f"{stem}.alto.xml"
        if f.exists() and f.resolve().parent == d.resolve():
            out = []
            for _, el in etree.iterparse(str(f), tag="{*}TextLine"):
                if el.get("ID") in ids:
                    out.append(tuple(float(el.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")))
                el.clear()
            return out
    return []


def boxes_for(con, stem: str, page: int, lines: str | None = None, block: str | None = None,
              anchor: str | None = None) -> tuple[dict, list[tuple]]:
    """Validate the request against the reading; return (page row, boxes in the ALTO frame)."""
    doc = con.execute("SELECT v.version_id FROM documents d JOIN versions v ON v.stem = d.stem AND v.is_current = 1 "
                      "WHERE d.stem = ?", (stem,)).fetchone()
    if not doc:
        raise CropError(404, "no such article in the reading")
    pg = con.execute("SELECT stem, page, width_px, height_px, image_w, image_h, page_image_key FROM pages "
                     "WHERE stem = ? AND page = ?", (stem, page)).fetchone()
    if not pg:
        raise CropError(404, "no such page in the reading")
    vid = doc[0]
    boxes: list[tuple] = []
    if anchor:
        if not ANCHOR.fullmatch(anchor) or not anchor.startswith(f"{stem}|p{page}|"):
            raise CropError(422, "anchor must be '<stem>|p<page>|w<a>-<b>' for this stem and page")
        r = con.execute("SELECT x, y, w, h FROM ink_anchors WHERE anchor_key = ?", (anchor,)).fetchone()
        if not r or r[0] is None:
            raise CropError(404, "no such ink anchor")
        boxes.append(tuple(r))
    if block:
        if not BLOCK_ID.fullmatch(block):
            raise CropError(422, "bad block id")
        rows = con.execute("SELECT x, y, w, h FROM block_parts WHERE version_id = ? AND block_id = ? AND page = ?",
                           (vid, block, page)).fetchall()
        if not rows:
            rows = con.execute("SELECT a.x, a.y, a.w, a.h FROM blocks b JOIN ink_anchors a ON a.anchor_pk = b.anchor_pk "
                               "WHERE b.version_id = ? AND b.block_id = ? AND a.page = ?", (vid, block, page)).fetchall()
        if not rows:
            raise CropError(404, "no such block on this page")
        boxes += [tuple(r) for r in rows if r[0] is not None]
    if lines:
        ids = [x.strip() for x in lines.split(",") if x.strip()]
        if not ids or len(ids) > 60 or not all(LINE_ID.fullmatch(i) for i in ids):
            raise CropError(422, "lines must be up to 60 ALTO line ids like p3b6l1, comma-separated")
        if any(int(i[1:].split("b")[0]) != page for i in ids):
            raise CropError(422, "every line must be on the page asked for")
        q = ",".join("?" * len(ids))
        found = {r[0]: tuple(r[1:]) for r in con.execute(
            f"SELECT alto_line_id, x, y, w, h FROM line_map WHERE version_id = ? AND alto_line_id IN ({q})", (vid, *ids))}
        missing = set(ids) - set(found)
        boxes += list(found.values())
        if missing:
            boxes += _alto_lines(stem, missing)
        if not boxes:
            raise CropError(404, "none of these lines is in the reading")
    if not boxes:
        raise CropError(422, "give lines=, block= or anchor=")
    return dict(pg), boxes


def crop(con, stem: str, page: int, lines: str | None = None, block: str | None = None,
         anchor: str | None = None, full_width: bool = False) -> tuple[bytes, str]:
    """JPEG bytes and the cache file name. Cached on disk."""
    pg, boxes = boxes_for(con, stem, page, lines, block, anchor)
    img_path = (PAGES / (pg["page_image_key"] or f"{stem}_p{page:03d}.jpg")).resolve()
    if img_path.parent != PAGES.resolve() or not img_path.exists():
        raise CropError(404, "the page image is not on this server")
    key = hashlib.sha1(repr((stem, page, sorted(boxes), full_width, img_path.stat().st_mtime)).encode()).hexdigest()
    out = crops_dir() / key[:2] / f"{key}.jpg"
    if out.exists():
        return out.read_bytes(), out.name
    from PIL import Image
    with Image.open(img_path) as im:
        W, H = im.size
        sx = W / (pg["width_px"] or W)
        sy = H / (pg["height_px"] or H)
        x0 = min(b[0] for b in boxes) * sx
        y0 = min(b[1] for b in boxes) * sy
        x1 = max(b[0] + b[2] for b in boxes) * sx
        y1 = max(b[1] + b[3] for b in boxes) * sy
        if full_width:
            x0, x1 = 0, W
        box = (max(0, int(x0 - PAD)), max(0, int(y0 - PAD)), min(W, int(x1 + PAD)), min(H, int(y1 + PAD)))
        if box[2] - box[0] < 4 or box[3] - box[1] < 4:
            raise CropError(422, "empty box")
        c = im.crop(box).convert("L")
        if c.width > MAX_W:
            c = c.resize((MAX_W, max(1, round(c.height * MAX_W / c.width))), Image.LANCZOS)
        buf = io.BytesIO()
        c.save(buf, "JPEG", quality=82, optimize=True)
    data = buf.getvalue()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out)
    return data, out.name
