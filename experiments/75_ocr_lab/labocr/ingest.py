"""Ingestion and rendering: immutable sources with SHA-256, one-based pages, pypdfium2 renders with their own hashes,
native-text inspection, a versioned JSONL manifest.

Data root layout (relative paths everywhere in records):
    sources/<sha[:2]>/<sha>.<ext>     the file exactly as received, read-only
    sources.jsonl                     SourceRecord per source (append-only, one per sha)
    renders/<render_id>.png           canonical page renders (lossless)
    renders.jsonl                     RenderRecord per render
    datasets/<name>/manifest.jsonl    ManifestEntry per page
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

from . import INGEST_VERSION
from .schemas import ManifestEntry, NativeText, RenderRecord, SourceRecord

SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._,\-]{0,120}$")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def renderer_name() -> str:
    from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO
    return f"pypdfium2 {PYPDFIUM_INFO} / pdfium {PDFIUM_INFO}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _jsonl_read(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _jsonl_append(p: Path, obj: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def atomic_write(p: Path, data: bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


def safe_child(root: Path, rel: str) -> Path:
    """root/rel, refusing anything that escapes root (absolute paths, .., symlinks out)."""
    root = root.resolve()
    p = (root / rel).resolve()
    if p != root and root not in p.parents:
        raise ValueError(f"path escapes the data root: {rel!r}")
    return p


# ------------------------------------------------------------------------------------------------ sources

def ingest_source(path: Path, root: Path) -> SourceRecord:
    path = Path(path)
    sha = sha256_file(path)
    for r in _jsonl_read(root / "sources.jsonl"):
        if r["sha256"] == sha:
            return SourceRecord.model_validate(r)
    ext = path.suffix.lower() if re.fullmatch(r"\.[a-z0-9]{1,5}", path.suffix.lower()) else ""
    rel = f"sources/{sha[:2]}/{sha}{ext}"
    dst = safe_child(root, rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copyfile(path, dst)
        os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP)
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    pages = page_count(dst, media)
    rec = SourceRecord(source_id="src_" + sha[:16], sha256=sha, original_name=path.name, media_type=media,
                       page_count=pages, stored_path=rel, ingest_version=INGEST_VERSION, ingested_at=_now())
    _jsonl_append(root / "sources.jsonl", rec.model_dump())
    return rec


def page_count(p: Path, media: str) -> int:
    if media == "application/pdf":
        import pypdfium2 as pdfium
        try:
            return len(pdfium.PdfDocument(str(p)))
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"unreadable PDF: {e}") from e
    return 1


def source_by_id(root: Path, source_id: str) -> SourceRecord:
    for r in _jsonl_read(root / "sources.jsonl"):
        if r["source_id"] == source_id:
            return SourceRecord.model_validate(r)
    raise KeyError(source_id)


# ------------------------------------------------------------------------------------------------ native text

def native_text(src: SourceRecord, root: Path, page_number: int) -> NativeText:
    if src.media_type != "application/pdf":
        return NativeText(present=False, chars=0, status="absent")
    import pypdfium2 as pdfium
    import pypdfium2.raw as R
    pdf = pdfium.PdfDocument(str(root / src.stored_path))
    pg = pdf[page_number - 1]
    tp = pg.get_textpage()
    n = tp.count_chars()
    text = tp.get_text_bounded() if n else ""
    warnings = []
    w, h = pg.get_size()
    big_image = False
    n_images = 0
    for o in pg.get_objects(max_depth=5):
        if o.type == R.FPDF_PAGEOBJ_IMAGE:
            n_images += 1
            l, b, r, t = o.get_bounds()
            if (r - l) * (t - b) > 0.8 * w * h:
                big_image = True
    status = "absent" if n == 0 else "unverified"
    if n and n_images >= 10:
        warnings.append(f"the page is drawn from {n_images} image pieces with a text layer beside them: the layer's "
                        "origin is unknown; not used in place of OCR here")
    if n and big_image:
        status = "suspect"
        warnings.append("a page-sized image carries the page and a text layer lies over it: probably a "
                        "third-party OCR layer, not born-digital text; never used in place of OCR here")
    return NativeText(present=n > 0, chars=n, text=text or None, status=status, warnings=warnings)


# ------------------------------------------------------------------------------------------------ renders

def render_page(src: SourceRecord, root: Path, page_number: int, dpi: int = 300, grey: bool = True) -> RenderRecord:
    import cv2
    import numpy as np
    if page_number < 1 or page_number > src.page_count:
        raise ValueError(f"page {page_number} outside 1..{src.page_count}")
    if src.media_type == "application/pdf":
        import pypdfium2 as pdfium
        try:
            pdf = pdfium.PdfDocument(str(root / src.stored_path))
            pg = pdf[page_number - 1]
            rot = pg.get_rotation()
            bm = pg.render(scale=dpi / 72, grayscale=grey)
            a = bm.to_numpy()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"render error: {e}") from e
        if a.ndim == 3 and grey:
            a = a[..., 0]
        elif a.ndim == 3:
            a = a[..., :3]          # pypdfium gives BGR(x) for rgb renders, which is what cv2 writes
        w_pt, h_pt = pg.get_size()
        s = dpi / 72
        affine = [s, 0.0, 0.0, -s, 0.0, h_pt * s] if rot == 0 else None   # PDF (bottom-left) -> px (top-left)
        renderer = renderer_name()
    else:
        a = cv2.imread(str(root / src.stored_path), cv2.IMREAD_GRAYSCALE if grey else cv2.IMREAD_COLOR)
        if a is None:
            raise RuntimeError("unreadable image")
        rot, affine, renderer = 0, None, f"opencv {cv2.__version__} (image source, no resampling)"
    ok, buf = cv2.imencode(".png", np.ascontiguousarray(a))
    if not ok:
        raise RuntimeError("PNG encode failed")
    data = buf.tobytes()
    sha = hashlib.sha256(data).hexdigest()
    rid = "r_" + sha[:16]
    rel = f"renders/{rid}.png"
    for r in _jsonl_read(root / "renders.jsonl"):
        if r["render_id"] == rid:
            return RenderRecord.model_validate(r)
    atomic_write(safe_child(root, rel), data)
    rec = RenderRecord(render_id=rid, source_id=src.source_id, page_number=page_number, path=rel, sha256=sha,
                       width=int(a.shape[1]), height=int(a.shape[0]), dpi=dpi, rotation=rot, renderer=renderer,
                       colour="grey" if a.ndim == 2 else "rgb", pdf_to_render=affine)
    _jsonl_append(root / "renders.jsonl", rec.model_dump())
    return rec


def render_by_id(root: Path, render_id: str) -> RenderRecord:
    for r in _jsonl_read(root / "renders.jsonl"):
        if r["render_id"] == render_id:
            return RenderRecord.model_validate(r)
    raise KeyError(render_id)


# ------------------------------------------------------------------------------------------------ manifest

def manifest_path(root: Path, dataset: str) -> Path:
    if not SAFE_ID.fullmatch(dataset):
        raise ValueError(f"bad dataset name {dataset!r}")
    return root / "datasets" / dataset / "manifest.jsonl"


def read_manifest(root: Path, dataset: str) -> list[ManifestEntry]:
    return [ManifestEntry.model_validate(r) for r in _jsonl_read(manifest_path(root, dataset))]


def write_manifest(root: Path, dataset: str, entries: list[ManifestEntry]) -> str:
    body = "".join(json.dumps(e.model_dump(), ensure_ascii=False) + "\n" for e in entries).encode("utf-8")
    atomic_write(manifest_path(root, dataset), body)
    return hashlib.sha256(body).hexdigest()


def manifest_hash(root: Path, dataset: str) -> str:
    return sha256_file(manifest_path(root, dataset))


def page_id_of(document_id: str, page_number: int) -> str:
    if not SAFE_ID.fullmatch(document_id):
        raise ValueError(f"bad document id {document_id!r}")
    return f"{document_id}_p{page_number:03d}"


def check_leakage(entries: list[ManifestEntry]) -> list[str]:
    """Documents that appear in more than one split (grouped splits by document)."""
    seen: dict[str, set] = {}
    for e in entries:
        seen.setdefault(e.document_id, set()).add(e.split)
    return sorted(d for d, s in seen.items() if len(s - {"none"}) > 1)
