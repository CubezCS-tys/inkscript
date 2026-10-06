"""The ink judge: Gemini looks at one printed word on the scan and picks between two readings, blind (experiment 17's
method, used by experiment 27 to accept corrections).

    j = Judge(model, cache, spend_log, cap)
    verdicts = j.judge(items)        # items: {id, scan, page, box, r1, r2}; -> {id: {verdict: r1|r2|neither|unsure, ...}}

The crop is experiment 17's third marking (the only one without artefacts): the word's own line at 300 dpi from the
scan, a strip only as tall as the word, the paper (not the ink) behind the word tinted pale yellow, nothing drawn on
the ink. The two readings go out as A and B in an order fixed by a hash of the item id (blind, balanced,
reproducible); the judge is never told which is the OCR's and which the proposal's. It answers A, B, NEITHER (and
writes what the ink says) or UNSURE. Temperature 0, JSON schema, thinking "low", six crops per request.

Every answer is cached (jsonl, by model and item id: a rerun pays nothing), every request's tokens and cost are
appended to the spend log, a request that would take the logged total over the cap is not sent, and a failed
request is tried three times, then skipped.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import numpy as np

# Prices per million tokens (in, out incl. thinking), list prices as known on 2026-10-06, rounded UP so the logged
# spend is an upper bound (experiment 17).
PRICE = {"gemini-3.1-pro-preview": (2.0, 12.0), "gemini-pro-latest": (2.0, 12.0), "gemini-2.5-pro": (1.25, 10.0),
         "gemini-3.8-flash": (1.0, 5.0), "gemini-flash-latest": (1.0, 5.0), "gemini-3.7-flash": (0.75, 3.75)}
DEFAULT_MODEL = "gemini-3.1-pro-preview"
VERSION = ":c1"            # appended to every cache id: a change of crop or prompt must not reuse old answers

TASHKEEL = re.compile("[ً-ٰٟۖ-ۭـ]")


def plain(s: str) -> str:
    """Readings are shown without short vowels, Quranic marks or kashida (the judge compares letters)."""
    return TASHKEEL.sub("", s).strip()


class Pages:
    """300-dpi grey renders of scan pages, a few at a time (memory)."""

    def __init__(self, keep: int = 3):
        self.keep, self.cache = keep, {}

    def get(self, scan, page: int) -> np.ndarray:
        k = (str(scan), page)
        if k not in self.cache:
            import pymupdf
            if len(self.cache) >= self.keep:
                self.cache.pop(next(iter(self.cache)))
            d = pymupdf.open(str(scan))
            pix = d[page - 1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
            self.cache[k] = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()
            d.close()
        return self.cache[k]


def crop(gray: np.ndarray, box, side: float = 3.5) -> np.ndarray:
    """Experiment 17's v3 crop: the word's line, ink untouched, the paper behind the word tinted pale yellow."""
    import cv2
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    h = max(20, y1 - y0)
    H, W = gray.shape
    cx0, cx1 = max(0, int(x0 - side * h)), min(W, int(x1 + side * h))
    cy0, cy1 = max(0, int(y0 - 0.18 * h)), min(H, int(y1 + 0.18 * h))
    g = gray[cy0:cy1, cx0:cx1]
    img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR).astype(np.float32)
    p = max(3, int(0.1 * h))
    ys, xs = slice(max(0, y0 - cy0 - p), max(0, y1 - cy0 + p)), slice(max(0, x0 - cx0 - p), max(0, x1 - cx0 + p))
    paper = (g[ys, xs].astype(np.float32) / 255.0)[..., None]
    tint = np.array([150, 240, 255], np.float32)
    img[ys, xs] = img[ys, xs] * (1 - paper) + (img[ys, xs] * (1 - 0.9 * paper) + tint * 0.9 * paper) * paper
    return np.clip(img, 0, 255).astype(np.uint8)


def png(img) -> bytes:
    import cv2
    return cv2.imencode(".png", img)[1].tobytes()


PROMPT = """You are checking an OCR transcription of a scanned Arabic printed page, word by word. You are the judge: look at the ink.

For each numbered image: a strip of one printed line. Nothing is drawn on the ink itself. One word stands on a PALE YELLOW background (only the paper is tinted, the ink is untouched; the tint may fall slightly short of the word's first or last letter — judge the whole word). Read only that word. Two candidate readings of the yellow word are given, A and B. They are different; at most one can be exactly right. Decide from the printed ink — count the dots, look for a hamza, check ة against ه and ى against ي, count the teeth and letters — not from which word is more common or more likely in context. The text may be vowelled Quranic script: ignore short-vowel marks (harakat), shadda, sukun, kashida and small Quranic signs; a small alef written above a letter counts as that alef. If A and B differ only by spaces, choose the one whose words are the words printed.

Answer for each item:
  "A" or "B"   — that reading matches the ink exactly (letters, dots, hamza);
  "NEITHER"    — both are wrong; then write in "text" what the yellow word actually says;
  "UNSURE"     — the ink itself cannot settle it (broken, blotted, too faint).

Items:
{items}

Reply with JSON only: {{"answers": [{{"n": 1, "verdict": "A|B|NEITHER|UNSURE", "text": "", "why": "a few words"}}, ...]}} with one entry per item, in order."""

SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["A", "B", "NEITHER", "UNSURE"]},
    "text": {"type": "string"}, "why": {"type": "string"}}, "required": ["n", "verdict", "text", "why"]}}},
    "required": ["answers"]}


def order(item_id: str, r1: str, r2: str) -> tuple[str, str, str]:
    """A/B from a hash of the item id. Returns (A, B, which letter r1 is)."""
    flip = int(hashlib.md5(item_id.encode()).hexdigest(), 16) % 2 == 1
    return (r2, r1, "B") if flip else (r1, r2, "A")


def _key() -> str | None:
    """GEMINI_API_KEY from the environment, else the first .env up from the package (a git worktree sits inside
    the main checkout, whose .env holds the key)."""
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    for d in Path(__file__).resolve().parents:
        f = d / ".env"
        if f.exists():
            for line in f.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


class Judge:
    def __init__(self, model: str = DEFAULT_MODEL, cache: Path | None = None, spend_log: Path | None = None,
                 cap: float = 1.0, batch: int = 6, tag: str = ""):
        if model not in PRICE:
            raise SystemExit(f"no price known for {model}; known: {', '.join(PRICE)}")
        self.model, self.cache, self.spend_log, self.cap, self.batch, self.tag = model, cache, spend_log, cap, batch, tag
        self.pages = Pages()
        self.stopped = False
        self.this_run = 0.0

    def spent(self) -> float:
        if not self.spend_log or not Path(self.spend_log).exists():
            return 0.0
        return sum(json.loads(line)["usd"] for line in Path(self.spend_log).read_text().splitlines() if line.strip())

    def cached(self) -> dict:
        out = {}
        if self.cache and Path(self.cache).exists():
            for line in Path(self.cache).read_text(encoding="utf-8").splitlines():
                if line.strip():
                    d = json.loads(line)
                    if d["model"] == self.model:
                        out[d["id"]] = d
        return out

    def estimate(self, n: int) -> float:
        """Cost of judging n new items: experiment 17 measured about 1,140 tokens in and 55 out per item (six crops
        a request); rounded up to 1,500 and 300."""
        pin, pout = PRICE[self.model]
        return n * (1500 / 1e6 * pin + 300 / 1e6 * pout)

    def judge(self, items: list[dict]) -> dict:
        from google.genai import types
        done = self.cached()
        todo = [it for it in items if it["id"] + VERSION not in done]
        if todo:
            from google import genai
            key = _key()
            if not key:
                raise SystemExit("GEMINI_API_KEY not set (environment or .env)")
            client = genai.Client(api_key=key)
        pin, pout = PRICE[self.model]
        lev = types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
        est_in, est_out = 1500.0, 300.0
        for s in range(0, len(todo), self.batch):
            chunk = todo[s:s + self.batch]
            parts, lines, meta = [], [], []
            for n, it in enumerate(chunk, 1):
                A, B, r1_is = order(it["id"], plain(it["r1"]), plain(it["r2"]))
                img = it.get("img")
                if img is None:
                    img = crop(self.pages.get(it["scan"], it["page"]), it["box"])
                parts += [types.Part(text=f"Image {n}:"),
                          types.Part(inline_data=types.Blob(data=png(img), mime_type="image/png"),
                                     media_resolution=types.PartMediaResolution(level=lev))]
                lines.append(f"  {n}. A = {A}    B = {B}")
                meta.append((A, B, r1_is))
            parts.append(types.Part(text=PROMPT.format(items="\n".join(lines))))
            est = len(chunk) * (est_in / 1e6 * pin + est_out / 1e6 * pout)
            if self.spent() + est > self.cap:
                print(f"STOP: spent ${self.spent():.3f}, this request ~${est:.3f} would cross the ${self.cap} cap",
                      flush=True)
                self.stopped = True
                break
            cfg = dict(temperature=0.0, max_output_tokens=8192, response_mime_type="application/json",
                       response_schema=SCHEMA, thinking_config=types.ThinkingConfig(thinking_level="low"))
            res = None
            for attempt in range(3):                       # bounded: three tries, then the chunk is skipped
                try:
                    r = client.models.generate_content(model=self.model,
                                                       contents=[types.Content(role="user", parts=parts)],
                                                       config=types.GenerateContentConfig(**cfg))
                    um = r.usage_metadata
                    tin = um.prompt_token_count or 0
                    tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
                    usd = tin / 1e6 * pin + tout / 1e6 * pout
                    self.this_run += usd
                    if self.spend_log:
                        with open(self.spend_log, "a") as f:
                            f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=self.model,
                                                    tag=self.tag, items=len(chunk), tin=tin, tout=tout, usd=usd,
                                                    total=round(self.spent() + usd, 4))) + "\n")
                    est_in, est_out = max(est_in, tin / len(chunk)), max(est_out, tout / len(chunk))
                    res = json.loads(r.text)["answers"]
                    break
                except Exception as e:
                    print("  request failed:", type(e).__name__, str(e)[:200], flush=True)
                    time.sleep(5 * (attempt + 1))
            print(f"  {self.model} {self.tag} {s + len(chunk)}/{len(todo)}  total ${self.spent():.3f}", flush=True)
            if res is None:
                continue
            by_n = {a.get("n"): a for a in res}
            for n, (it, (A, B, r1_is)) in enumerate(zip(chunk, meta), 1):
                a = by_n.get(n)
                if a is None:
                    continue
                v = a["verdict"]
                verdict = {"NEITHER": "neither", "UNSURE": "unsure"}.get(v) or ("r1" if v == r1_is else "r2")
                d = dict(model=self.model, id=it["id"] + VERSION, verdict=verdict, raw=v, text=a.get("text", ""),
                         why=a.get("why", ""), A=A, B=B, tag=self.tag, when=time.strftime("%Y-%m-%d %H:%M:%S"))
                done[d["id"]] = d
                if self.cache:
                    with open(self.cache, "a", encoding="utf-8") as f:
                        f.write(json.dumps(d, ensure_ascii=False) + "\n")
        return {it["id"]: done[it["id"] + VERSION] for it in items if it["id"] + VERSION in done}
