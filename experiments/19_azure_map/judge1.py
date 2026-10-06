"""The single-reading judge: Gemini looks at the ink of one word in its line and says whether a given reading is
exactly what is printed; if not, what the ink says.

Unlike experiment 17's A/B judge there is no rival reading: the judge sees Azure's reading only (it is not told
whose it is). That is what the archive needs (any error, not one look-alike), and also the harder test: a judge shown
one reading can be anchored by it. Calibration (calibrate1.py) measures exactly that: false alarms on words the owner
marked right, misses on the same words with one mark changed.

The crop is experiment 17's v3 marking (17_judge/judge.py `crop`): the word's own line at 300 dpi, the paper behind
the word tinted pale yellow, nothing drawn on the ink.

Several crops per request; temperature 0; JSON schema; every answer cached (out/judge_cache.jsonl, by model and item
id); every request's tokens and cost appended to out/spend.jsonl; a request whose estimate would take the running total
over CAP is not sent; three tries per request, then the chunk is skipped.
"""
import os, json, time, re
from pathlib import Path
import cv2

HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
CACHE = OUT / "judge_cache.jsonl"; SPEND = OUT / "spend.jsonl"
CAP = 12.0                                                     # dollars, the whole experiment
PRICE = {"gemini-3.1-pro-preview": (2.0, 12.0), "gemini-3.8-flash": (1.0, 5.0)}   # per M tokens in/out, rounded up (as exp. 17)
VERSION = ":s1"

PROMPT = """You are proof-reading an OCR transcription of scanned printed pages, word by word. You are the judge: look at the ink.

For each numbered image: a strip of one printed line (most are Arabic; some words may be digits or Latin script; some prints are old, small or faint). Nothing is drawn on the ink. One word stands on a PALE YELLOW background (only the paper is tinted; the tint may fall slightly short of the word's first or last letter — judge the whole word, including a letter that sits just outside the tint if it clearly belongs to it). Read only that word.

Each item gives the OCR's reading of the yellow word. Decide from the printed ink whether that reading is EXACTLY what is printed: the same letters in the same order, the same dots (count them), the same hamza (or none), ة against ه, ى against ي, the same digits, the same Latin letters, and the same punctuation attached to the word. Do not correct the print: if the print itself has a misspelling or an unusual spelling, the right reading copies it. Do not judge from which word is more likely in context — judge from the ink.

Verdict for each item:
  "RIGHT"   — the reading matches the ink exactly (ignoring short-vowel marks and kashida).
  "WRONG"   — it does not; write in "text" exactly what the yellow word says in the ink.
  "BOX"     — the yellow area does not hold one word: it cuts a word in part, or spans parts of two or more words, or holds no text; write in "text" what the yellow area holds.
  "UNSURE"  — the ink itself cannot settle it (broken, blotted, too faint).
Also "harakat": if the reading carries short-vowel marks (fatha, kasra, damma, tanwin, shadda, sukun), say "SAME" if the printed marks agree with them, "DIFFER" if not; "NONE" if the reading has none.

Items:
{items}

Reply with JSON only: {{"answers": [{{"n": 1, "verdict": "RIGHT|WRONG|BOX|UNSURE", "text": "", "harakat": "SAME|DIFFER|NONE", "why": "a few words"}}, ...]}} with one entry per item, in order."""

SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["RIGHT", "WRONG", "BOX", "UNSURE"]},
    "text": {"type": "string"}, "harakat": {"type": "string", "enum": ["SAME", "DIFFER", "NONE"]}, "why": {"type": "string"}},
    "required": ["n", "verdict", "text", "harakat", "why"]}}}, "required": ["answers"]}


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


def png(img):
    ok, b = cv2.imencode(".png", img); return b.tobytes()


def estimate(n_items, model, per_in=1200, per_out=250):
    pin, pout = PRICE[model]; return n_items * (per_in / 1e6 * pin + per_out / 1e6 * pout)


def judge(items, model, batch=8, thinking="low", tag="", limit_usd=None):
    """items: dicts with id, img (BGR array), reading. Returns {id: dict(verdict right|wrong|box|unsure, text, harakat, why)}."""
    from google.genai import types
    done = cached(model); todo = [it for it in items if it["id"] + VERSION not in done]
    client = _client() if todo else None; pin, pout = PRICE[model]
    lev = types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
    est_in = est_out = None; start = spent()
    for s in range(0, len(todo), batch):
        chunk = todo[s:s + batch]; parts = []; lines = []
        for n, it in enumerate(chunk, 1):
            parts += [types.Part(text=f"Image {n}:"), types.Part(inline_data=types.Blob(data=png(it["img"]), mime_type="image/png"),
                                                               media_resolution=types.PartMediaResolution(level=lev))]
            lines.append(f"  {n}. OCR reading: {it['reading']}")
        parts.append(types.Part(text=PROMPT.format(items="\n".join(lines))))
        est = (est_in or 1500) * len(chunk) / 1e6 * pin + (est_out or 900) * len(chunk) / 1e6 * pout
        if spent() + est > CAP or (limit_usd is not None and spent() - start + est > limit_usd):
            print(f"STOP: spent ${spent():.3f}; this request ~${est:.3f} would cross the cap", flush=True); break
        cfg = dict(temperature=0.0, max_output_tokens=8192, response_mime_type="application/json", response_schema=SCHEMA)
        if thinking: cfg["thinking_config"] = types.ThinkingConfig(thinking_level=thinking)
        res = None
        for attempt in range(3):
            try:
                r = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                                   config=types.GenerateContentConfig(**cfg))
                um = r.usage_metadata; tin = um.prompt_token_count or 0
                tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
                usd = tin / 1e6 * pin + tout / 1e6 * pout
                with open(SPEND, "a") as f:
                    f.write(json.dumps(dict(when=time.strftime("%H:%M:%S"), model=model, tag=tag, items=len(chunk), tin=tin, tout=tout, usd=usd, total=spent() + usd)) + "\n")
                est_in, est_out = tin / len(chunk), tout / len(chunk)
                res = json.loads(r.text)["answers"]; break
            except Exception as e:
                print("  request failed:", type(e).__name__, str(e)[:200], flush=True); time.sleep(5 * (attempt + 1))
        print(f"  {model} {tag} {s + len(chunk)}/{len(todo)}  total ${spent():.3f}", flush=True)
        if res is None: continue
        by_n = {a.get("n"): a for a in res}
        with open(CACHE, "a") as f:
            for n, it in enumerate(chunk, 1):
                a = by_n.get(n)
                if a is None: continue
                d = dict(model=model, id=it["id"] + VERSION, verdict=a["verdict"].lower(), text=a.get("text", ""),
                         harakat=a.get("harakat", ""), why=a.get("why", ""), reading=it["reading"], tag=tag)
                f.write(json.dumps(d, ensure_ascii=False) + "\n"); done[it["id"] + VERSION] = d
    return {it["id"]: done[it["id"] + VERSION] for it in items if it["id"] + VERSION in done}
