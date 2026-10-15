"""Experiment 41: the one Gemini client (cap, cache, spend log). Copied from experiment 40's common.py on 2026-10-15;
only the paths, CAP and the price table changed (experiment 41 has its own spend log, out/gemini_spend.jsonl).

Every Gemini call of this experiment goes through `gemini()`:
  * it refuses a call whose WORST CASE (estimated input + max_out at list price) would take the experiment past CAP
    ($20), counting calls already logged in out/gemini_spend.jsonl and calls in flight on other threads;
  * `subcap=(tag_prefix, usd)` also refuses a call that could take the spend of tags starting with tag_prefix past
    usd (each approach owns a tag prefix, e.g. "a1_", and its own sub-cap);
  * answers are cached by a hash of model, prompt, settings and every attached image / PDF (out/gemini_cache.jsonl):
    a rerun costs nothing for what is done;
  * a truncated or unparsable answer is logged as spend, NOT cached and NOT retried; its raw text is kept in
    out/truncated/<tag>.txt so nothing paid for is lost;
  * the key is read by inkscript's own loader (GEMINI_API_KEY or the checkout's .env) and never printed.

Usage
    import sys; sys.path.insert(0, "/home/yassine/inkscript/experiments/41_azure_structure")
    from common import gemini, spent, page_jpeg, sample
    ans, usd = gemini(prompt, images=[page_jpeg(pid)], tag="a1_" + pid, json_out=False, max_out=16000,
                      thinking="low", subcap=("a1_", 3.0))
    ans, usd = gemini(prompt, pdf=DOCS / f"{stem}.pdf", tag="a5_" + stem, json_out=False, max_out=60000,
                      subcap=("a5_", 3.0))
`ans` is the parsed JSON (json_out=True, optional `schema`) or the text (json_out=False); None when refused,
failed or truncated. Pass `info={}` to get finish reason, tokens and seconds back.
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = HERE.parents[1]                                   # the checkout (/home/yassine/inkscript)
sys.path.insert(0, str(MAIN / "src"))

OUT = HERE / "out"
PAGES = OUT / "pages"                                    # <pid>.jpg, 300 dpi, the pixels every reference box is in
DOCS = OUT / "docs"                                      # <stem>.pdf (+ <stem>.json, Azure's) whole documents
SPEND = OUT / "gemini_spend.jsonl"
CACHE = OUT / "gemini_cache.jsonl"
GOLD = MAIN / "experiments/34_yardstick/out/gold"
B36 = MAIN / "experiments/36_vlm_bakeoff/out"
B39 = MAIN / "experiments/39_ink_geometry/out"
CAP = 20.0
MAX_THREADS = 4

# USD per million tokens (input, output; thinking is billed as output).
# Checked 2026-10-15 on https://ai.google.dev/gemini-api/docs/pricing: gemini-4-argon Standard tier $2.00 / $10.00
# "through Nov 30, 2026", then $4.00 / $20.00 from Dec 1, 2026 (Batch/Flex half price; no long-context tier listed).
# Runs after the change dates use the later price automatically: PRICE_LATER.
# Experiment 41 re-checked the page on 2026-10-15: gemini-3.8-flash is $0.75 / $3.75 through Dec 31, 2026, then
# $1.50 / $7.50 from Jan 1, 2027 (Batch half) - not the $1 / $5 the brief assumed.
PRICE = {"gemini-4-argon": (2.0, 10.0), "gemini-3.1-pro-preview": (2.0, 12.0), "gemini-3.8-flash": (0.75, 3.75)}
PRICE_LATER = {"gemini-4-argon": ("2026-12-01", (4.0, 20.0)), "gemini-3.8-flash": ("2027-01-01", (1.5, 7.5))}
DEFAULT_MODEL = "gemini-4-argon"

LOCK = threading.Lock()
INFLIGHT: dict[str, float] = {}       # worst case of calls sent and not yet logged, by tag


# ------------------------------------------------------------------------------------------------ the sample

def sample() -> dict:
    """out/sample.json: {"pages": [...], "docs": [...]}; see choose_sample.py."""
    return json.loads((OUT / "sample.json").read_text(encoding="utf-8"))


def page_ids() -> list[str]:
    return [p["page_id"] for p in sample()["pages"]]


def page_info(pid: str) -> dict:
    return next(p for p in sample()["pages"] if p["page_id"] == pid)


def page_jpeg(pid: str, max_side: int = 3000, quality: int = 90) -> bytes:
    """The page image as JPEG bytes (whole 300 dpi page unless max_side is smaller)."""
    f = PAGES / f"{pid}.jpg"
    if max_side >= 3600:
        return f.read_bytes()
    import cv2
    img = cv2.imread(str(f), cv2.IMREAD_COLOR)
    return jpeg(img, max_side, quality)


def page_image_path(pid: str) -> Path:
    """out/pages/<pid>.jpg; a page of a sample document that is not a sample page is rendered on first use
    (colour, 300 dpi, from out/docs/<stem>.pdf)."""
    f = PAGES / f"{pid}.jpg"
    if not f.exists():
        stem, p = pid.rsplit("_p", 1)
        import pymupdf
        with pymupdf.open(str(DOCS / f"{stem}.pdf")) as d:
            PAGES.mkdir(parents=True, exist_ok=True)
            d[int(p) - 1].get_pixmap(dpi=300, alpha=False).save(str(f), jpg_quality=92)
    return f


def azure_lines(pid: str) -> list[dict]:
    """Azure's lines of a sample page in Azure's order: text, box [x0,y0,x1,y1] in the page image's pixels, kind."""
    return json.loads((B36 / "ref/azure" / f"{pid}.json").read_text(encoding="utf-8"))["lines"]


def jpeg(img, max_side: int = 1600, quality: int = 85) -> bytes:
    import cv2
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


# ------------------------------------------------------------------------------------------------ Gemini

def _log_rows() -> list[dict]:
    if not SPEND.exists():
        return []
    return [json.loads(l) for l in SPEND.read_text().splitlines() if l.strip()]


def spent(tag_prefix: str = "") -> float:
    """Logged spend, all of it or of the tags that start with tag_prefix."""
    return sum(r["usd"] for r in _log_rows() if r.get("tag", "").startswith(tag_prefix))


def _inflight(prefix: str = "") -> float:
    return sum(v for k, v in INFLIGHT.items() if k.startswith(prefix))


_cache = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for l in CACHE.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    r = json.loads(l)
                    _cache[r["key"]] = r["answer"]
    return _cache


def _price(model: str):
    if model in PRICE_LATER and time.strftime("%Y-%m-%d") >= PRICE_LATER[model][0]:
        return PRICE_LATER[model][1]
    return PRICE[model]


def pdf_pages(data: bytes) -> int:
    import pymupdf
    with pymupdf.open(stream=data, filetype="pdf") as d:
        return len(d)


def gemini(prompt: str, images: list[bytes] = (), tag: str = "untagged", model: str = DEFAULT_MODEL,
           max_out: int = 8000, schema: dict | None = None, thinking: str = "low", est_in: int | None = None,
           resolution: str = "high", pdf: bytes | str | Path | None = None, json_out: bool = True,
           subcap: tuple[str, float] | None = None, system: str | None = None, temperature: float | None = None,
           info: dict | None = None):
    """One call. Returns (answer or None, usd). Images are JPEG bytes; `pdf` is a whole PDF (bytes or path).
    thinking: "low" | "medium" | "high" (or None to leave the model's default)."""
    if pdf is not None and not isinstance(pdf, bytes):
        pdf = Path(pdf).read_bytes()
    images = list(images)
    blobs = images + ([pdf] if pdf else [])
    key = hashlib.sha256((model + "\0" + prompt + "\0" + str(thinking) + resolution + str(json_out) + "\0"
                          + json.dumps(schema, sort_keys=True) + "\0" + str(system) + str(temperature)).encode()
                         + b"".join(hashlib.sha256(i).digest() for i in blobs)).hexdigest()
    c = _load_cache()
    if key in c:
        if info is not None:
            info.update(cached=True)
        return c[key], 0.0
    pin, pout = _price(model)
    if est_in is None:
        est_in = 1200 * len(images) + int(len(prompt) / 2.5) + len(system or "") // 2 + 200
        if pdf:
            est_in += 1800 * pdf_pages(pdf)      # a scanned page at high resolution, generous
    worst = est_in / 1e6 * pin + max_out / 1e6 * pout
    with LOCK:
        if spent() + _inflight() + worst > CAP:
            print(f"STOP: spent ${spent():.3f}; a call (up to ${worst:.3f}) could cross the ${CAP} cap", flush=True)
            return None, 0.0
        if subcap and spent(subcap[0]) + _inflight(subcap[0]) + worst > subcap[1]:
            print(f"STOP: {subcap[0]}* spent ${spent(subcap[0]):.3f}; a call (up to ${worst:.3f}) could cross its "
                  f"${subcap[1]} sub-cap", flush=True)
            return None, 0.0
        ik = f"{tag}\0{time.time()}\0{threading.get_ident()}"
        INFLIGHT[ik] = worst
    try:
        return _send(model, prompt, images, pdf, tag, max_out, schema, thinking, resolution, json_out, system,
                     temperature, key, pin, pout, info)
    finally:
        with LOCK:
            INFLIGHT.pop(ik, None)


def _client():
    from google import genai
    from inkscript.enrich.judge import _key
    return genai.Client(api_key=_key())


def _send(model, prompt, images, pdf, tag, max_out, schema, thinking, resolution, json_out, system, temperature,
          key, pin, pout, info):
    c = _load_cache()
    from google.genai import types
    client = _client()
    lvl = {"ultra_high": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_ULTRA_HIGH,
           "high": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
           "medium": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_MEDIUM,
           "low": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW}[resolution]
    parts = []
    for k, im in enumerate(images, 1):
        if len(images) > 1:
            parts.append(types.Part(text=f"Image {k}:"))
        parts.append(types.Part(inline_data=types.Blob(data=im, mime_type="image/jpeg"),
                                media_resolution=types.PartMediaResolution(level=lvl)))
    if pdf:
        if len(pdf) < 18_000_000:
            parts.append(types.Part(inline_data=types.Blob(data=pdf, mime_type="application/pdf"),
                                    media_resolution=types.PartMediaResolution(level=lvl)))
        else:                                            # inline requests are limited to ~20 MB: the File API
            import io
            f = client.files.upload(file=io.BytesIO(pdf), config=dict(mime_type="application/pdf"))
            parts.append(types.Part(file_data=types.FileData(file_uri=f.uri, mime_type="application/pdf")))
    parts.append(types.Part(text=prompt))
    cfg = dict(max_output_tokens=max_out)
    if temperature is not None:
        cfg["temperature"] = temperature
    if thinking:
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level=thinking)
    if json_out:
        cfg["response_mime_type"] = "application/json"
        if schema:
            cfg["response_schema"] = schema
    if system:
        cfg["system_instruction"] = system
    t0 = time.time()
    try:
        r = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                           config=types.GenerateContentConfig(**cfg))
    except Exception as e:
        msg = str(e).replace(client._api_client.api_key or "\0", "<key>")[:300]
        print(f"  request failed for {tag}: {type(e).__name__} {msg}", flush=True)
        if info is not None:
            info.update(error=f"{type(e).__name__} {msg}")
        return None, 0.0
    secs = time.time() - t0
    um = r.usage_metadata
    tin = um.prompt_token_count or 0
    tthink = getattr(um, "thoughts_token_count", 0) or 0
    tout = (um.candidates_token_count or 0) + tthink
    usd = tin / 1e6 * pin + tout / 1e6 * pout
    fin = str(r.candidates[0].finish_reason) if r.candidates else "none"
    SPEND.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        total = spent() + usd
        with open(SPEND, "a") as f:
            f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=model, tag=tag, tin=tin,
                                    tout=tout, think=tthink, usd=round(usd, 6), secs=round(secs, 1), finish=fin,
                                    total=round(total, 4))) + "\n")
    if info is not None:
        info.update(finish=fin, tin=tin, tout=tout, think=tthink, secs=secs, usd=usd, cached=False)
    text = r.text or ""
    bad = "MAX_TOKENS" in fin or not text.strip()
    ans = None
    if not bad:
        if json_out:
            try:
                ans = json.loads(text)
            except Exception:
                bad = True
        else:
            ans = text
    if bad:
        d = OUT / "truncated"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{tag.replace('/', '_')}.txt").write_text(text, encoding="utf-8")
        print(f"  truncated or unparsable answer ({fin}) for {tag}: kept in out/truncated, not retried", flush=True)
        return None, usd
    with LOCK:
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(key=key, tag=tag, model=model, answer=ans), ensure_ascii=False) + "\n")
        c[key] = ans
    return ans, usd


def strip_fences(s: str) -> str:
    """An HTML answer without a ```html ... ``` wrapper."""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()
