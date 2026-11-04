"""The article beside its scan (2026-10-23): the full page images and, for each page, the boxes of what the reading
made of it, so the Article page can show the scan and the text side by side and outline a block on the ink.

- `page_image`: a page scan, downscaled to one of a few widths and cached on disk (DESK_CROPS/pages/), so a 30-page
  article loads ~150 KB per page instead of 1.2 MB. The source is the 300 dpi image experiment 43 cut
  (`43_rehearsal/out/pages/<pages.page_image_key>`); an article without one there (the v2_55 run) falls back to
  experiment 41's view scans (`41_azure_structure/out/views/<run>/scans/<stem>/pNNN.jpg`). The stem and page are
  checked against the reading; file names never come from the request.
- `layout`: per page, its size in the ALTO frame (`pages.width_px` × `height_px`, the frame every box is in), its
  printed folio, the boxes of each block (`block_parts`, else the block's ink anchor), the figures, and the page
  furniture the reader kept out of the text (`page_regions`: running heads, page numbers, the other article...).
  The screen turns boxes into fractions of the page, so the image's own size does not matter."""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

from .crops import PAGES, CropError, crops_dir
from .pages import VIEWS, _has_table, _rows

WIDTHS = (640, 1000, 1400)
# page furniture worth showing on the scan (noise, picture junk and formula ink are left out: they are not text)
REGIONS = {"pageHeader": "running head", "pageFooter": "running foot", "pageNumber": "page number",
           "otherArticle": "another article on this page", "ornament": "ornament", "showThrough": "show-through",
           "pictureText": "text inside a picture"}


def _doc(con, stem: str):
    r = con.execute("SELECT v.version_id, v.run FROM documents d JOIN versions v ON v.stem = d.stem AND v.is_current = 1 "
                    "WHERE d.stem = ?", (stem,)).fetchone()
    if not r:
        raise CropError(404, "no such article in the reading")
    return r[0], r[1]


def source_of(con, stem: str, page: int) -> Path | None:
    """The page's image file on this server, or None."""
    _, run = _doc(con, stem)
    pg = con.execute("SELECT page_image_key FROM pages WHERE stem = ? AND page = ?", (stem, page)).fetchone()
    if not pg:
        raise CropError(404, "no such page in the reading")
    f = (PAGES / (pg[0] or f"{stem}_p{page:03d}.jpg")).resolve()
    if f.parent == PAGES.resolve() and f.is_file():
        return f
    if run and all(c.isalnum() or c in "_-" for c in run):
        d = (VIEWS / run / "scans" / stem).resolve()
        f = (d / f"p{page:03d}.jpg").resolve()
        if d.parent == (VIEWS / run / "scans").resolve() and f.parent == d and f.is_file():
            return f
    return None


def page_image(con, stem: str, page: int, width: int = 1000) -> tuple[bytes, str]:
    """JPEG bytes of the page scan at the nearest allowed width (never upscaled), and the cache file name."""
    src = source_of(con, stem, page)
    if src is None:
        raise CropError(404, "the page image is not on this server")
    w = min(WIDTHS, key=lambda x: abs(x - width))
    key = hashlib.sha1(repr((str(src), w, src.stat().st_mtime)).encode()).hexdigest()
    out = crops_dir() / "pages" / key[:2] / f"{key}.jpg"
    if out.exists():
        return out.read_bytes(), out.name
    from PIL import Image
    with Image.open(src) as im:
        im = im.convert("L")
        if im.width > w:
            im = im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
    data = buf.getvalue()
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out)
    return data, out.name


def layout(con, stem: str) -> dict:
    """Every page of the article with its boxes (ALTO frame), for the beside-the-scan view."""
    vid, run = _doc(con, stem)
    pages = _rows(con, "SELECT page, width_px w, height_px h, printed_folio folio FROM pages WHERE stem = ? "
                       "ORDER BY page", (stem,))
    by_page = {p["page"]: dict(p, image=False, blocks=[], figures=[], regions=[]) for p in pages}
    for p in by_page.values():
        p["image"] = source_of(con, stem, p["page"]) is not None
    roles = {r[0]: (r[1], r[2]) for r in con.execute(
        "SELECT block_id, role, figure_id FROM blocks WHERE version_id = ?", (vid,))}
    seen = set()
    for r in _rows(con, "SELECT block_id, part, page, x, y, w, h FROM block_parts WHERE version_id = ? "
                        "ORDER BY block_id, part", (vid,)):
        if r["page"] in by_page and r["x"] is not None:
            role, fig = roles.get(r["block_id"], (None, None))
            by_page[r["page"]]["blocks"].append(dict(id=r["block_id"], role=role, part=r["part"],
                                                     x=r["x"], y=r["y"], w=r["w"], h=r["h"]))
            seen.add(r["block_id"])
    # a block without parts: its ink anchor's box
    for r in _rows(con, "SELECT b.block_id, b.role, a.page, a.x, a.y, a.w, a.h FROM blocks b "
                        "JOIN ink_anchors a ON a.anchor_pk = b.anchor_pk WHERE b.version_id = ?", (vid,)):
        if r["block_id"] not in seen and r["page"] in by_page and r["x"] is not None:
            by_page[r["page"]]["blocks"].append(dict(id=r["block_id"], role=r["role"], part=1,
                                                     x=r["x"], y=r["y"], w=r["w"], h=r["h"]))
    for r in _rows(con, "SELECT figure_id, kind, page, x, y, w, h FROM figures WHERE version_id = ?", (vid,)):
        if r["page"] in by_page and r["x"] is not None and r["w"]:
            by_page[r["page"]]["figures"].append(dict(id=r["figure_id"], kind=r["kind"], x=r["x"], y=r["y"],
                                                      w=r["w"], h=r["h"]))
    if _has_table(con, "page_regions"):
        q = ",".join("?" * len(REGIONS))
        for r in _rows(con, f"SELECT region_id, page, role, text, x, y, w, h FROM page_regions WHERE version_id = ? "
                            f"AND role IN ({q}) ORDER BY page, y", (vid, *REGIONS)):
            if r["page"] in by_page and r["x"] is not None:
                by_page[r["page"]]["regions"].append(dict(id=r["region_id"], role=r["role"], label=REGIONS[r["role"]],
                                                          text=r["text"], x=r["x"], y=r["y"], w=r["w"], h=r["h"]))
    return dict(stem=stem, run=run, widths=list(WIDTHS), pages=[by_page[k] for k in sorted(by_page)])
