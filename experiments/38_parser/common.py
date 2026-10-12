"""Experiment 38: shared paths, readers of the inputs, and the one Gemini client (cap, cache, spend log).

Inputs (all in the main checkout, read only):
  yardstick pages     experiments/34_yardstick/out/gold/<pid>.json + .jpg (300 dpi grey; every box in its pixels)
  Azure's words       the page's oldest saved version (gold/.history/<pid>/ first file), else the page itself:
                      the draft is Azure's reading, words with boxes and confidences, before any correction
  dots.mocr           experiments/36_vlm_bakeoff/out/raw/dots_mocr/<pid>.json (blocks in the resized image's pixels,
                      scaled here to the page's)
  Kraken              experiments/36_vlm_bakeoff/out/kraken/<pid>.json
  old editions        experiments/35_edition/out/editions/<stem>/
  masters (front)     experiments/29_catalogue/out/merged/<stem>.jats.xml (+ the faithful PDF, for colour crops)

Gemini: every call goes through `Gemini.call`, which refuses a call whose worst case would cross CAP (all of this
experiment's calls, logged in out/gemini_spend.jsonl at list price rounded up), caches answers by a hash of model,
prompt and images (out/gemini_cache.jsonl), never prints the key, and never retries a truncated answer.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))     # this worktree's inkscript

LOCK = threading.Lock()
INFLIGHT = [0.0]          # worst-case cost of calls sent and not yet logged (threads)

MAIN = Path("/home/yassine/inkscript")
OUT = MAIN / "experiments/38_parser/out"
GOLD = MAIN / "experiments/34_yardstick/out/gold"
B36 = MAIN / "experiments/36_vlm_bakeoff/out"
OLD_EDITIONS = MAIN / "experiments/35_edition/out/editions"
MASTERS = MAIN / "experiments/29_catalogue/out/merged"
CAP = 6.0
SPEND = OUT / "gemini_spend.jsonl"
CACHE = OUT / "gemini_cache.jsonl"


def pages() -> list[dict]:
    return json.loads((OUT / "pages.json").read_text(encoding="utf-8"))["pages"]


def gold(pid: str) -> dict:
    return json.loads((GOLD / f"{pid}.json").read_text(encoding="utf-8"))


def azure_draft(pid: str) -> dict:
    """Azure's reading of the page as drafted, before the owner touched it."""
    h = GOLD / ".history" / pid
    if h.exists():
        fs = sorted(h.glob("*.json"))
        if fs:
            return json.loads(fs[0].read_text(encoding="utf-8"))
    return gold(pid)


def azure_words(pid: str) -> list[dict]:
    """Every Azure word of the page in Azure's reading order: text, box [x0,y0,x1,y1], conf, its line's id and kind."""
    d = azure_draft(pid)
    by = {ln["id"]: ln for ln in d["lines"]}
    out = []
    for li in d["order"]:
        ln = by[li]
        words = ln.get("words") or []
        # the draft's words are Azure's; a line whose text was edited still carries Azure's words
        for k, w in enumerate(words):
            out.append(dict(id=f"{li}w{k:02d}", text=w["text"], box=list(w["box"]), conf=w.get("conf"), line=li,
                            line_kind=ln.get("kind"), lang=ln.get("lang")))
    return out


def dots_blocks(pid: str) -> list[dict]:
    """dots.mocr's blocks in its reading order, boxes in page pixels [x0,y0,x1,y1]."""
    r = json.loads((B36 / "raw/dots_mocr" / f"{pid}.json").read_text(encoding="utf-8"))
    W, H = r["orig_size"]
    w, h = r.get("seen_size") or (W, H)
    sx, sy = W / w, H / h
    s = r.get("output") or ""
    try:
        bl = json.loads(s)
    except Exception:
        bl = _salvage(s)
    out = []
    for i, b in enumerate(bl):
        if not isinstance(b, dict) or "bbox" not in b:
            continue
        x0, y0, x1, y1 = b["bbox"]
        out.append(dict(i=i, cat=b.get("category") or "Text", text=b.get("text") or "",
                        box=[x0 * sx, y0 * sy, x1 * sx, y1 * sy]))
    return out


def _salvage(s: str) -> list:
    """Output cut at the token cap: keep the complete objects."""
    out, depth, start, ins, esc = [], 0, None, False, False
    for i, ch in enumerate(s):
        if ins:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                ins = False
            continue
        if ch == '"':
            ins = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    out.append(json.loads(s[start:i + 1]))
                except Exception:
                    pass
    return out


def kraken_lines(pid: str) -> list[dict]:
    f = B36 / "kraken" / f"{pid}.json"
    if not f.exists():
        return []
    return json.loads(f.read_text(encoding="utf-8"))["lines"]


def page_image(pid: str):
    import cv2
    return cv2.imread(str(GOLD / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE)


def colour_page(pid: str, stem: str, page: int):
    """The page in colour at the gold image's size, from the faithful PDF; None if it cannot be matched."""
    import numpy as np
    import pymupdf
    g = gold(pid)
    W, H = g["image"]["width"], g["image"]["height"]
    pdf = MASTERS / f"{stem}.pdf"
    if not pdf.exists():
        return None
    with pymupdf.open(str(pdf)) as d:
        if page - 1 >= len(d):
            return None
        pg = d[page - 1]
        zx = W / pg.rect.width
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(zx, H / pg.rect.height), alpha=False)
        a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3]
        if abs(pix.width - W) > 2 or abs(pix.height - H) > 2:
            return None
        import cv2
        return cv2.cvtColor(np.ascontiguousarray(a), cv2.COLOR_RGB2BGR)


# ------------------------------------------------------------------------------------------------ geometry

def area(b) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter(a, b) -> float:
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def union(boxes):
    boxes = list(boxes)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def gap(a, b) -> float:
    dx = max(0.0, max(a[0], b[0]) - min(a[2], b[2]))
    dy = max(0.0, max(a[1], b[1]) - min(a[3], b[3]))
    return (dx * dx + dy * dy) ** 0.5


# ------------------------------------------------------------------------------------------------ Gemini

PRICE = {"gemini-3.1-pro-preview": (2.0, 12.0), "gemini-3.8-flash": (1.0, 5.0), "gemini-3.7-flash": (0.75, 3.75)}


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in SPEND.read_text().splitlines() if l.strip())


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


def jpeg(img, max_side: int = 1600, quality: int = 85) -> bytes:
    import cv2
    h, w = img.shape[:2]
    s = min(1.0, max_side / max(h, w))
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])[1].tobytes()


def gemini(prompt: str, images: list[bytes], tag: str, model: str = "gemini-3.8-flash", max_out: int = 4000,
           schema: dict | None = None, thinking: str = "low", est_in: int | None = None,
           resolution: str = "high"):
    """One call. Returns (answer or None, usd). Refuses a call whose worst case would cross CAP."""
    key = hashlib.sha256((model + "\0" + prompt + "\0" + thinking + resolution).encode()
                         + b"".join(hashlib.sha256(i).digest() for i in images)).hexdigest()
    c = _load_cache()
    if key in c:
        return c[key], 0.0
    pin, pout = PRICE[model]
    tin = est_in or (1200 * len(images) + len(prompt) / 2.5)
    worst = tin / 1e6 * pin + max_out / 1e6 * pout
    with LOCK:
        if spent() + INFLIGHT[0] + worst > CAP:
            print(f"STOP: spent ${spent():.3f}; a call (up to ${worst:.3f}) could cross the ${CAP} cap", flush=True)
            return None, 0.0
        INFLIGHT[0] += worst
    try:
        return _send(model, prompt, images, tag, max_out, schema, thinking, resolution, key, pin, pout)
    finally:
        with LOCK:
            INFLIGHT[0] -= worst


def _send(model, prompt, images, tag, max_out, schema, thinking, resolution, key, pin, pout):
    c = _load_cache()
    from google import genai
    from google.genai import types
    from inkscript.enrich.judge import _key
    client = genai.Client(api_key=_key())
    lvl = {"high": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
           "medium": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_MEDIUM}[resolution]
    parts = []
    for k, im in enumerate(images, 1):
        parts.append(types.Part(text=f"Image {k}:"))
        parts.append(types.Part(inline_data=types.Blob(data=im, mime_type="image/jpeg"),
                                media_resolution=types.PartMediaResolution(level=lvl)))
    parts.append(types.Part(text=prompt))
    cfg = dict(temperature=0.0, max_output_tokens=max_out, response_mime_type="application/json",
               thinking_config=types.ThinkingConfig(thinking_level=thinking))
    if schema:
        cfg["response_schema"] = schema
    try:
        r = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                           config=types.GenerateContentConfig(**cfg))
    except Exception as e:
        print("  request failed:", type(e).__name__, str(e)[:200], flush=True)
        return None, 0.0
    um = r.usage_metadata
    tin = um.prompt_token_count or 0
    tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
    usd = tin / 1e6 * pin + tout / 1e6 * pout
    fin = str(r.candidates[0].finish_reason) if r.candidates else "none"
    SPEND.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        with open(SPEND, "a") as f:
            f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=model, tag=tag, tin=tin, tout=tout,
                                    usd=round(usd, 6), finish=fin, total=round(spent() + usd, 4))) + "\n")
    try:
        ans = json.loads(r.text)
    except Exception:
        print(f"  truncated or unparsable answer ({fin}) for {tag}: kept as a failure, not retried", flush=True)
        return None, usd
    with LOCK:
        with open(CACHE, "a", encoding="utf-8") as f:
            f.write(json.dumps(dict(key=key, tag=tag, model=model, answer=ans), ensure_ascii=False) + "\n")
        c[key] = ans
    return ans, usd


TASHKEEL = re.compile("[ً-ٰٟۖ-ۭ]")
