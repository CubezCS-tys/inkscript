"""The judge: Gemini looks at the ink of one word in its line and picks between two readings, blind.

An item is: a page image (300 dpi grey render of the scan, the pixels the pipeline itself works on), the word's
box, optionally the disputed piece's box, and two candidate readings. The crop is the word in its line (a strip a
few line-heights wide either side), the word marked (see MARK below), the disputed piece spanned by a blue bar. The candidates go
out as A and B in an order fixed by a hash of the item id (so a rerun is the same question), and the judge is never
told where either came from. It may answer A, B, NEITHER (and write what the word says) or UNSURE.

Several items go in one request (each its own image, numbered); temperature 0, JSON out. Every response is cached
in out/judge_cache.jsonl by (model, item id), and every request's tokens and estimated cost are appended to
out/spend.jsonl; `judge()` refuses to send a request that would take the running total over CAP.
"""
import os, io, json, time, hashlib, random, re
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"; CACHE = OUT / "judge_cache.jsonl"; SPEND = OUT / "spend.jsonl"; CROPS = OUT / "crops"
CAP = 20.0                                                             # dollars, the whole experiment (owner, 2026-10-06)

# Prices per million tokens (in, out incl. thinking). List prices as best known on 2026-10-06; Pro at its <=200k
# tier. Deliberately rounded UP so the logged spend is an upper bound.
PRICE = {"gemini-3.1-pro-preview": (2.0, 12.0), "gemini-pro-latest": (2.0, 12.0), "gemini-2.5-pro": (1.25, 10.0),
         "gemini-3.8-flash": (1.0, 5.0), "gemini-flash-latest": (1.0, 5.0), "gemini-3.7-flash": (0.75, 3.75)}

TASHKEEL = re.compile("[ً-ْٰـ]")


def plain(s):
    """Readings are compared and shown without short-vowel marks or kashida (the feeler reads letters only)."""
    return TASHKEEL.sub("", s).strip()


_pages = {}


def page_image(scan, pn):
    key = (str(scan), pn)
    if key not in _pages:
        import fitz
        if len(_pages) > 3: _pages.clear()                              # a few pages at a time: memory
        doc = fitz.open(str(scan)); pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY)
        _pages[key] = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()
    return _pages[key]


MARK = "tint"            # v3 (2026-10-06): the word's paper tinted pale yellow, the piece by a bar in a margin below; nothing on the ink.
# v1 ("box") drew a red box round the word and a blue bar just under the piece: the box edge hid an unattached alef, and the
# bar under a lone alef read as a hamza below. v2 ("bars") put a red bar in a margin above the strip: the judge then read the
# word of the line ABOVE, which touched the bar. Both are kept in out/v1, out/v2.
VERSION = ":v3"          # appended to every cache id, so earlier answers (kept in the cache) are never reused for these crops


def crop(gray, word_box, piece_box=None, side=3.5):
    """The word's own line, at scan resolution, ink untouched: a strip only as tall as the word (its dots included) plus a
    little, so the lines above and below barely show. Inside the word's box the PAPER (light pixels) is tinted pale yellow;
    the disputed piece, when there is one, is spanned by a BLUE bar in a white margin below the strip."""
    x0, y0, x1, y1 = word_box; h = max(20, y1 - y0); H, W = gray.shape
    cx0, cx1 = max(0, int(x0 - side * h)), min(W, int(x1 + side * h)); cy0, cy1 = max(0, int(y0 - 0.18 * h)), min(H, int(y1 + 0.18 * h))
    g = gray[cy0:cy1, cx0:cx1]; img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR).astype(np.float32)
    p = max(3, int(0.1 * h)); ys, xs = slice(max(0, y0 - cy0 - p), y1 - cy0 + p), slice(max(0, x0 - cx0 - p), x1 - cx0 + p)
    paper = (g[ys, xs].astype(np.float32) / 255.0)[..., None]             # 1 on white paper, 0 on black ink
    tint = np.array([150, 240, 255], np.float32)                             # BGR pale yellow
    img[ys, xs] = img[ys, xs] * (1 - paper) + (img[ys, xs] * (1 - 0.9 * paper) + tint * 0.9 * paper) * paper
    img = np.clip(img, 0, 255).astype(np.uint8); w = img.shape[1]
    if piece_box is None: return img
    m = max(14, int(0.3 * h)); bot = np.full((m, w, 3), 255, np.uint8); a, _, b, _ = piece_box
    cv2.rectangle(bot, (a - cx0, m // 3), (b - cx0, m // 3 + max(4, m // 4)), (220, 110, 0), -1)
    return np.vstack([img, np.full((2, w, 3), 170, np.uint8), bot])


def png(img):
    ok, b = cv2.imencode(".png", img); return b.tobytes()


PROMPT = """You are checking an OCR transcription of a scanned Arabic printed page, word by word. You are the judge: look at the ink.

For each numbered image: a strip of one printed line. Nothing is drawn on the ink itself. One word stands on a PALE YELLOW background (only the paper is tinted, the ink is untouched; the tint may fall slightly short of the word's first or last letter — judge the whole word). Read only that word. {blue}Two candidate readings of the yellow word are given, A and B. They are different; at most one can be exactly right. Decide from the printed ink — count the dots, look for a hamza, check ة against ه and ى against ي, count the teeth and letters — not from which word is more common or more likely in context. Ignore short-vowel marks (harakat) and kashida.

Answer for each item:
  "A" or "B"   — that reading matches the ink exactly (letters, dots, hamza);
  "NEITHER"    — both are wrong; then write in "text" what the yellow word actually says;
  "UNSURE"     — the ink itself cannot settle it (broken, blotted, too faint).

Items:
{items}

Reply with JSON only: {{"answers": [{{"n": 1, "verdict": "A|B|NEITHER|UNSURE", "text": "", "why": "a few words"}}, ...]}} with one entry per item, in order."""

BLUE = "If a BLUE bar is drawn in the margin BELOW the strip, it spans the part of the yellow word where the two readings differ. "

SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["A", "B", "NEITHER", "UNSURE"]},
    "text": {"type": "string"}, "why": {"type": "string"}}, "required": ["n", "verdict", "text", "why"]}}}, "required": ["answers"]}


def order(item_id, r1, r2):
    """A/B order from the item id: blind, balanced, reproducible. Returns (A, B, which_is_r1)."""
    flip = int(hashlib.md5(item_id.encode()).hexdigest(), 16) % 2 == 1
    return (r2, r1, "B") if flip else (r1, r2, "A")


def spent():
    return sum(json.loads(l)["usd"] for l in open(SPEND)) if SPEND.exists() else 0.0


def cached(model):
    out = {}
    if CACHE.exists():
        for l in open(CACHE):
            d = json.loads(l)
            if d["model"] == model: out[d["id"]] = d
    return out


def _client():
    from google import genai
    if "GEMINI_API_KEY" not in os.environ:
        for l in open(HERE.parents[1] / ".env"):
            if l.startswith("GEMINI_API_KEY="): os.environ["GEMINI_API_KEY"] = l.split("=", 1)[1].strip().strip('"')
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def judge(items, model, batch=6, resolution="high", thinking="low", tag=""):
    """items: dicts with id, img (BGR array), r1, r2 (r1 = the reading we track, e.g. Azure's or the gold), blue (bool).
    Returns {id: dict(verdict in r1|r2|neither|unsure, text, why, A, B)}. Cached; spend-capped."""
    from google.genai import types
    done = cached(model); todo = [it for it in items if it["id"] + VERSION not in done]
    client = _client() if todo else None; pin, pout = PRICE[model]
    lev = getattr(types.PartMediaResolutionLevel, f"MEDIA_RESOLUTION_{resolution.upper()}")
    est_in = None; est_out = None
    for s in range(0, len(todo), batch):
        chunk = todo[s:s + batch]; parts = []; lines = []; meta = []
        for n, it in enumerate(chunk, 1):
            A, B, r1_is = order(it["id"], plain(it["r1"]), plain(it["r2"]))
            parts += [types.Part(text=f"Image {n}:"), types.Part(inline_data=types.Blob(data=png(it["img"]), mime_type="image/png"),
                                                               media_resolution=types.PartMediaResolution(level=lev))]
            lines.append(f"  {n}. A = {A}    B = {B}"); meta.append((A, B, r1_is))
        blue = any(it.get("blue") for it in chunk)
        parts.append(types.Part(text=PROMPT.format(blue=BLUE if blue else "", items="\n".join(lines))))
        # estimate before sending: from the last request's per-item tokens, else a generous guess
        ei = (est_in or 1400) * len(chunk); eo = (est_out or 900) * len(chunk)
        est = ei / 1e6 * pin + eo / 1e6 * pout
        if spent() + est > CAP:
            print(f"STOP: spent ${spent():.3f}, this request ~${est:.3f} would cross the ${CAP} cap", flush=True); break
        cfg = dict(temperature=0.0, max_output_tokens=8192, response_mime_type="application/json", response_schema=SCHEMA)
        if thinking: cfg["thinking_config"] = types.ThinkingConfig(thinking_level=thinking)
        res = None
        for attempt in range(3):                                       # bounded: three tries, then skip the chunk
            try:
                r = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                                   config=types.GenerateContentConfig(**cfg))
                um = r.usage_metadata; tin = um.prompt_token_count or 0
                tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
                usd = tin / 1e6 * pin + tout / 1e6 * pout
                with open(SPEND, "a") as f:
                    f.write(json.dumps(dict(when=time.strftime("%H:%M:%S"), model=model, tag=tag, items=len(chunk), tin=tin, tout=tout, usd=usd)) + "\n")
                est_in, est_out = tin / len(chunk), tout / len(chunk)
                res = json.loads(r.text)["answers"]; break
            except Exception as e:
                print("  request failed:", type(e).__name__, str(e)[:200], flush=True); time.sleep(5 * (attempt + 1))
        print(f"  {model} {tag} {s + len(chunk)}/{len(todo)}  total ${spent():.3f}", flush=True)
        if res is None: continue
        by_n = {a.get("n"): a for a in res}
        with open(CACHE, "a") as f:
            for n, (it, (A, B, r1_is)) in enumerate(zip(chunk, meta), 1):
                a = by_n.get(n)
                if a is None: continue
                v = a["verdict"]
                verdict = {"NEITHER": "neither", "UNSURE": "unsure"}.get(v) or ("r1" if v == r1_is else "r2")
                d = dict(model=model, id=it["id"] + VERSION, verdict=verdict, raw=v, text=a.get("text", ""), why=a.get("why", ""), A=A, B=B, tag=tag)
                f.write(json.dumps(d, ensure_ascii=False) + "\n"); done[it["id"] + VERSION] = d
    return {it["id"]: done[it["id"] + VERSION] for it in items if it["id"] + VERSION in done}
