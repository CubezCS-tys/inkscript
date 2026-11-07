"""Versioned Pydantic schemas: sources, renders, manifest entries, engine contract messages, page predictions.

Conventions (README "Conventions"):
* pages are one-based everywhere public (manifests, predictions, API);
* a box is [x0, y0, x1, y1] in pixels of the canonical render named by `render_id`, top-left origin, x1/y1 exclusive;
* `raw_text` is the engine's text for a block exactly as emitted (after JSON decoding only); derived forms live in
  other fields (`search_text`) and never replace it; inline offsets are Unicode code points into `raw_text`;
* a measurement that could not be taken is null with a reason in `null_reasons`, never 0.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import SCHEMA_VERSION

BlockType = Literal["paragraph", "heading", "title", "list", "footnote", "header", "footer", "page_number", "table",
                    "equation", "figure", "caption", "bibliography", "abstract", "text", "unknown"]
PageStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]
ErrorKind = Literal["unreadable_pdf", "render_error", "worker_crash", "timeout", "oom", "truncated", "invalid_output",
                    "missing_output", "protocol_error", "load_error", "other"]
NativeStatus = Literal["unverified", "usable", "suspect", "absent"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------------------------------ ingestion

class SourceRecord(_M):
    schema_version: str = SCHEMA_VERSION
    source_id: str                       # "src_" + first 16 hex of sha256
    sha256: str
    original_name: str
    media_type: str
    page_count: int
    stored_path: str                     # relative to the data root
    ingest_version: str
    ingested_at: str


class NativeText(_M):
    present: bool
    chars: int
    text: Optional[str] = None
    status: NativeStatus = "unverified"
    warnings: list[str] = []


class RenderRecord(_M):
    schema_version: str = SCHEMA_VERSION
    render_id: str                       # "r_" + first 16 hex of sha256 of the image bytes
    source_id: str
    page_number: int = Field(ge=1)
    path: str                            # relative to the data root
    sha256: str
    width: int
    height: int
    dpi: int
    rotation: int = 0                    # degrees applied by the renderer (0: page as stored)
    renderer: str                        # e.g. "pypdfium2 5.12.1 / pdfium 152.0.7947.0"
    colour: Literal["grey", "rgb"] = "grey"
    pdf_to_render: Optional[list[float]] = None   # affine [a,b,c,d,e,f]: px = a*x+c*y+e, py = b*x+d*y+f (PDF pt -> px)


class ManifestEntry(_M):
    schema_version: str = SCHEMA_VERSION
    dataset: str
    document_id: str                     # stable: from the source identity (stem when known)
    page_id: str                         # document_id + "_p" + 3-digit one-based page
    page_number: int = Field(ge=1)
    source_id: str
    render_id: Optional[str] = None
    category: str                        # e.g. "clean_modern_arabic"
    languages: list[str] = []
    provenance: str
    usage: str                           # usage permissions (Mandumah pages: private, never uploaded)
    split: Literal["dev", "test", "train", "none"] = "none"
    annotation: Optional[str] = None     # truth file reference (relative to the data root or repo)
    native_text: Optional[NativeText] = None
    force_ocr: bool = True
    source_policy: Literal["ocr_only", "native_only", "native_then_ocr"] = "ocr_only"


# ------------------------------------------------------------------------------------------------ engine contract

class EngineCapabilities(_M):
    engine: str
    model: str
    revision: Optional[str] = None
    is_fixture: bool = False             # a fixture worker never appears in results
    full_page: bool
    crops: bool
    text_granularity: Literal["page", "block", "line", "word"]
    box_granularity: Literal["none", "block", "line", "word"]
    output_types: list[str]
    image_budget: Optional[str] = None
    configurable: list[str] = []
    known_limitations: list[str] = []
    licence: Optional[str] = None


class EngineHealth(_M):
    ok: bool
    detail: str = ""
    device: Optional[str] = None
    versions: dict[str, str] = {}


class EngineConfig(_M):
    engine: str
    variant: str = "default"             # e.g. "pipeline", "bare_ocr", "as_written"
    settings: dict[str, Any] = {}        # every setting that affects outputs (decoding, image limits, prompts)
    model_revision: Optional[str] = None


class PageRequest(_M):
    request_id: str
    page_id: str
    page_number: int = Field(ge=1)
    render_id: str
    width: int
    height: int
    image_path: Optional[str] = None     # a path the worker can read, or
    image_b64: Optional[str] = None      # the image bytes (remote workers over ssh)
    image_name: str = "page.png"
    crop: Optional[list[int]] = None     # [x0,y0,x1,y1) on the render when the request is a crop

    @model_validator(mode="after")
    def _one_image(self):
        if not self.image_path and not self.image_b64:
            raise ValueError("a page request needs image_path or image_b64")
        return self


# ------------------------------------------------------------------------------------------------ predictions

class Span(_M):
    start: int                           # code points into raw_text
    end: int
    lang: Optional[str] = None
    direction: Optional[Literal["rtl", "ltr"]] = None


class TableCell(_M):
    row: int = Field(ge=0)               # zero-based, spatial order as emitted
    col: int = Field(ge=0)
    row_span: int = 1
    col_span: int = 1
    text: str
    header: bool = False
    box: Optional[list[float]] = None


class Block(_M):
    block_id: str                        # per-run id; never an annotation identity
    type: BlockType
    raw_label: Optional[str] = None      # the engine's own label, verbatim (unmapped labels stay visible)
    box: Optional[list[float]] = None    # None when the engine gives no geometry (never invented)
    box_source: Optional[str] = None     # "engine" or the derivation method
    raw_text: str = ""
    search_text: Optional[str] = None
    order: Optional[int] = None          # reading-order position (0-based) when the engine gives one
    order_source: Optional[str] = None
    parent: Optional[str] = None
    spans: list[Span] = []
    cells: list[TableCell] = []
    latex: Optional[str] = None
    equation_display: Optional[bool] = None
    confidence: Optional[float] = None
    confidence_meaning: Optional[str] = None
    flags: list[str] = []

    @field_validator("box")
    @classmethod
    def _box(cls, v):
        if v is not None:
            if len(v) != 4 or v[2] < v[0] or v[3] < v[1]:
                raise ValueError(f"bad box {v}")
        return v


class Timing(_M):
    render_s: Optional[float] = None
    load_s: Optional[float] = None
    inference_s: Optional[float] = None
    normalise_s: Optional[float] = None
    total_s: Optional[float] = None
    warm: Optional[bool] = None
    stages: dict[str, float] = {}        # engine-reported stages (e.g. layout, vl_rec), labelled as such
    null_reasons: dict[str, str] = {}


class Resources(_M):
    peak_gpu_mem_mb: Optional[float] = None
    peak_gpu_mem_method: Optional[str] = None
    output_tokens: Optional[int] = None
    input_pixels: Optional[list[int]] = None   # effective model input [w, h] after the engine's own resize
    device: Optional[str] = None
    null_reasons: dict[str, str] = {}


class ErrorRecord(_M):
    kind: ErrorKind
    message: str
    retryable: bool = False


class PredictionResult(_M):
    """What a worker returns for one page (the transport adds run/attempt ids)."""
    schema_version: str = SCHEMA_VERSION
    request_id: str
    page_id: str
    status: Literal["succeeded", "failed"]
    empty: bool = False                  # succeeded with no text at all (kept distinct from failure)
    blocks: list[Block] = []
    raw: Any = None                      # the engine's response, verbatim (JSON-able); text responses as strings
    raw_format: str = "json"
    page_text: Optional[str] = None      # the engine's whole-page text as emitted, when it has one
    truncated: Optional[bool] = None
    timing: Timing = Timing()
    resources: Resources = Resources()
    settings_used: dict[str, Any] = {}   # decoding / image settings actually used (temperature, max tokens…)
    error: Optional[ErrorRecord] = None

    @model_validator(mode="after")
    def _check(self):
        if self.status == "failed" and self.error is None:
            raise ValueError("a failed prediction needs an error")
        validate_order(self.blocks)
        return self


class PagePrediction(_M):
    """A stored prediction: the worker result plus its run identity and render frame."""
    schema_version: str = SCHEMA_VERSION
    run_id: str
    attempt_id: str
    document_id: str
    page_number: int = Field(ge=1)
    page_id: str
    render_id: str
    width: int
    height: int
    engine: str
    variant: str
    result: PredictionResult
    raw_artifact: Optional[str] = None   # path of the verbatim raw file (relative to the data root)


def validate_order(blocks: list[Block]) -> None:
    """Parent edges must point at existing blocks without cycles; orders must be unique when given."""
    ids = {b.block_id for b in blocks}
    if len(ids) != len(blocks):
        raise ValueError("duplicate block ids")
    parent = {b.block_id: b.parent for b in blocks}
    for b in blocks:
        if b.parent is not None and b.parent not in ids:
            raise ValueError(f"block {b.block_id} has unknown parent {b.parent}")
        seen, cur = set(), b.block_id
        while cur is not None:
            if cur in seen:
                raise ValueError(f"parent cycle through {cur}")
            seen.add(cur)
            cur = parent.get(cur)
    orders = [b.order for b in blocks if b.order is not None]
    if len(orders) != len(set(orders)):
        raise ValueError("duplicate reading-order positions")


# ------------------------------------------------------------------------------------------------ truth

class TruthLine(_M):
    line_id: str                         # stable annotation id (never a predicted box)
    text: str                            # as printed
    box: Optional[list[float]] = None
    region: Optional[str] = None
    kind: str = "text"


class TruthRegion(_M):
    region_id: str
    type: str                            # canonical type (paragraph, heading, header, footer, page_number, footnote…)
    coarse: str                          # body | furniture | footnote (the class layout is scored on)
    box: list[float]
    order: int


class TruthPage(_M):
    schema_version: str = SCHEMA_VERSION
    page_id: str
    document_id: str
    page_number: int = Field(ge=1)
    width: int
    height: int
    revision: str                        # e.g. "agent-v1"; a correction creates a new revision
    status: str                          # e.g. "agent-checked (owner check pending)", "owner-gold"
    provenance: str
    conventions: list[str] = []
    lines: list[TruthLine]
    order: list[str]                     # line ids in reading order
    regions: list[TruthRegion] = []
    changes: list[dict] = []             # every change from the draft it was made from

    @model_validator(mode="after")
    def _check(self):
        ids = [ln.line_id for ln in self.lines]
        if sorted(ids) != sorted(self.order) or len(set(ids)) != len(ids):
            raise ValueError("order must list every line id exactly once")
        rids = {r.region_id for r in self.regions}
        for ln in self.lines:
            if ln.region is not None and self.regions and ln.region not in rids:
                raise ValueError(f"line {ln.line_id} names unknown region {ln.region}")
        return self


# ------------------------------------------------------------------------------------------------ protocol

class Message(_M):
    protocol: str
    id: str
    op: Literal["capabilities", "health", "load", "predict", "close"]
    payload: dict[str, Any] = {}


class Reply(_M):
    protocol: str
    id: str
    ok: bool
    result: Any = None
    error: Optional[ErrorRecord] = None
