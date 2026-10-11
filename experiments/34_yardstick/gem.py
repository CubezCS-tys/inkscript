"""Gemini calls for experiment 34, with experiment 27's discipline: every answer cached (out/gemini_cache.jsonl, by a
hash of model + prompt + images: a rerun pays nothing), every request's tokens and cost appended to
out/spend.jsonl, list prices rounded up (enrich/judge.py PRICE), and no request sent that would take the
experiment's logged total over the cap (CAP = $15, the owner's limit for this experiment). Three tries, then None.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from inkscript.enrich.judge import PRICE, _key

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")
CACHE, SPEND = OUT / "gemini_cache.jsonl", OUT / "spend.jsonl"
CAP = 15.0
_lock = threading.Lock()
_cache: dict | None = None
_client = None


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in SPEND.read_text().splitlines() if l.strip())


def _load():
    global _cache
    if _cache is None:
        _cache = {}
        if CACHE.exists():
            for l in CACHE.read_text(encoding="utf-8").splitlines():
                if l.strip():
                    d = json.loads(l)
                    _cache[d["key"]] = d["answer"]
    return _cache


def call(model: str, prompt: str, images: list[bytes], schema: dict, tag: str, est_usd: float,
         resolution: str = "high", thinking: str = "low", max_out: int = 16384):
    """images: PNG/JPEG bytes in order, each preceded by 'Image n:'. Returns the parsed JSON answer or None."""
    h = hashlib.sha256((model + "\0" + prompt + "\0" + resolution).encode())
    for b in images:
        h.update(hashlib.sha256(b).digest())
    key = h.hexdigest()
    c = _load()
    if key in c:
        return c[key]
    with _lock:
        if spent() + est_usd > CAP:
            print(f"STOP: spent ${spent():.3f}; this request (~${est_usd:.3f}) would cross the ${CAP} cap", flush=True)
            return None
    from google import genai
    from google.genai import types
    global _client
    with _lock:
        if _client is None:
            _client = genai.Client(api_key=_key())
    lev = {"high": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH,
           "medium": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_MEDIUM,
           "low": types.PartMediaResolutionLevel.MEDIA_RESOLUTION_LOW}[resolution]
    parts = []
    for n, b in enumerate(images, 1):
        mime = "image/jpeg" if b[:2] == b"\xff\xd8" else "image/png"
        parts += [types.Part(text=f"Image {n}:"),
                  types.Part(inline_data=types.Blob(data=b, mime_type=mime), media_resolution=types.PartMediaResolution(level=lev))]
    parts.append(types.Part(text=prompt))
    cfg = dict(temperature=0.0, max_output_tokens=max_out, response_mime_type="application/json",
               response_schema=schema, thinking_config=types.ThinkingConfig(thinking_level=thinking))
    pin, pout = PRICE[model]
    for attempt in range(3):
        try:
            r = _client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                                config=types.GenerateContentConfig(**cfg))
            um = r.usage_metadata
            tin = um.prompt_token_count or 0
            tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
            usd = tin / 1e6 * pin + tout / 1e6 * pout
            with _lock:
                with open(SPEND, "a") as f:
                    f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=model, tag=tag,
                                            images=len(images), tin=tin, tout=tout, usd=usd,
                                            total=round(spent() + usd, 4))) + "\n")
            ans = json.loads(r.text)
            with _lock:
                c[key] = ans
                with open(CACHE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(dict(key=key, tag=tag, model=model, answer=ans), ensure_ascii=False) + "\n")
            return ans
        except Exception as e:
            print("  request failed:", type(e).__name__, str(e)[:200], flush=True)
            time.sleep(5 * (attempt + 1))
    return None
