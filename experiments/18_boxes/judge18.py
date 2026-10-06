"""The judge: Gemini looks at the scanned ink of one word with one letter's selection box tinted, and says which letters
the tint covers. It is never told which method made the box.

An item: the page (300 dpi grey render of the scan, experiment 17's page_image), the word's ink box, the box being
judged (a stretch [x0, x1] of the line in scan pixels), the word's letters in reading order, and the target letter k.
The crop is the word in its line, ink untouched (experiment 17's lesson: tint the paper, never draw on the ink): the
word's paper is pale yellow, and the paper inside the box, over the word's whole height, is light blue — what a drag
selection looks like. The judge gets the word's letters numbered in reading order and one of them in brackets; it says
whether the blue band covers that letter EXACTLY, MOSTLY, PARTLY, or is on OTHER letters. RIGHT = EXACT.

Items of every method are shuffled together (order fixed by a hash, reproducible); an item's id carries no method.
Responses cached in out/judge_cache.jsonl; every request's tokens and cost appended to out/spend.jsonl; a request
that would take the total over CAP is not sent.
"""
import os, json, time, hashlib, importlib.util
from pathlib import Path
import numpy as np, cv2

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
OUT = HERE / "out"; CACHE = OUT / "judge_cache.jsonl"; SPEND = OUT / "spend.jsonl"
CAP = 10.0                                                                      # dollars, the whole experiment
_spec = importlib.util.spec_from_file_location("j17", REPO / "experiments/17_judge/judge.py")
J17 = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(J17)     # page_image, PRICE, _client (imported, not edited)
PRICE = J17.PRICE
VERSIONS = {"graded": ":b2", "blind": ":b3"}
VERSION = ":b2"          # b1 asked "which numbered letters are more than half inside": the judge miscounted positions (alef/lam of ال swapped, both models)

SCANS = None


def scan_of(doc):
    global SCANS
    if SCANS is None:
        import sys; sys.path.insert(0, str(REPO / "experiments/16_feel")); import bench
        SCANS = {d: c["scan"] for d, c in bench.SUITE.items()}
    return SCANS[doc]


def crop(gray, word_box, cell, side=1.6, target_h=110):
    """The word in its line; the word's paper pale yellow, the box's paper light blue, ink untouched; scaled so the
    word is about target_h pixels tall."""
    x0, y0, x1, y1 = word_box; h = max(20, y1 - y0); H, W = gray.shape
    cx0, cx1 = max(0, int(x0 - side * h)), min(W, int(x1 + side * h)); cy0, cy1 = max(0, int(y0 - 0.22 * h)), min(H, int(y1 + 0.22 * h))
    g = gray[cy0:cy1, cx0:cx1]; img = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR).astype(np.float32)
    paper = (g.astype(np.float32) / 255.0)[..., None]
    p = max(3, int(0.12 * h)); yy0, yy1 = max(0, y0 - cy0 - p), min(g.shape[0], y1 - cy0 + p)

    def tint(xa, xb, colour, a=0.9):
        xa, xb = max(0, int(round(xa - cx0))), min(g.shape[1], int(round(xb - cx0)))
        if xb <= xa: return
        sl = (slice(yy0, yy1), slice(xa, xb)); pp = paper[sl]
        img[sl] = img[sl] * (1 - a * pp) + np.array(colour, np.float32) * a * pp
    tint(x0 - p, x1 + p, (150, 240, 255))                                       # word: pale yellow (BGR)
    tint(cell[0], cell[1], (255, 200, 120), 0.95)                               # the box: light blue
    img = np.clip(img, 0, 255).astype(np.uint8)
    s = target_h / h
    if s > 1.05: img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    return img


def item_image(it):
    gray = J17.page_image(scan_of(it["doc"]), it["page"])
    return crop(gray, it["box"], it["cell"])


PROMPT = """You are checking where a text-selection highlight falls on a scanned Arabic printed word.

Each numbered image is a strip of one printed line. Nothing is drawn on the ink. One word stands on a PALE YELLOW background (only the paper is tinted). Inside that word, a vertical band of the paper is tinted LIGHT BLUE — the highlight. Arabic is read right to left.

For each item you are told the word and ONE letter of it, written in brackets in its place, e.g. «ال[ز]بيدى» means the letter ز, the third letter read from the right. Find that letter in the ink (count from the right edge of the word; two tall strokes side by side in «ال» are alef on the right, lam on the left). Then say how the blue band sits on THAT letter:

  "EXACT"   — the band covers the whole body of that letter and no substantial part of a neighbouring letter's body (a little connecting stroke, or a sliver at the edge, is fine);
  "MOSTLY"  — the band covers most of that letter, but clearly cuts off part of it or also takes in a substantial part of a neighbour;
  "PARTLY"  — the band covers less than half of that letter;
  "OTHER"   — the band is on a different letter (or letters), not on this one.

Judge the letter's body (its strokes, bowl, teeth, tail) — dots and connecting strokes do not decide it. Do not assume the band is right or wrong; look.

Items:
{items}

Reply with JSON only: {{"answers": [{{"n": 1, "verdict": "EXACT|MOSTLY|PARTLY|OTHER", "on": "the letter(s) the band mostly covers", "why": "a few words"}}, ...]}} with one entry per item, in order."""

SCHEMA = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "verdict": {"type": "string", "enum": ["EXACT", "MOSTLY", "PARTLY", "OTHER"]}, "on": {"type": "string"},
    "why": {"type": "string"}}, "required": ["n", "verdict", "on", "why"]}}}, "required": ["answers"]}


PROMPT_BLIND = """You are checking where a text-selection highlight falls on a scanned Arabic printed word.

Each numbered image is a strip of one printed line. Nothing is drawn on the ink. One word stands on a PALE YELLOW background (only the paper is tinted). Inside that word, a vertical band of the paper is tinted LIGHT BLUE — the highlight. Arabic is read right to left. The word's text is given for each item.

For each item, rewrite the word putting in square brackets every letter whose body (its strokes, bowl, teeth, tail — not dots, not a connecting stroke) is MORE THAN HALF inside the blue band. Example: if the band sits on the ز of الزبيدى, write «ال[ز]بيدى». In «ال», alef is the right-hand tall stroke, lam the left-hand one. If no letter is more than half inside, write the word with no brackets.
Then say "clean": true if the band covers the bracketed letter(s) whole and takes in no substantial part of any other letter's body (a sliver at the edge is fine); false otherwise.

Items:
{items}

Reply with JSON only: {{"answers": [{{"n": 1, "marked": "the word with brackets", "clean": true, "why": "a few words"}}, ...]}} with one entry per item, in order."""

SCHEMA_BLIND = {"type": "object", "properties": {"answers": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "marked": {"type": "string"}, "clean": {"type": "boolean"}, "why": {"type": "string"}},
    "required": ["n", "marked", "clean", "why"]}}}, "required": ["answers"]}


def marked_letters(marked, letters):
    """1-based positions of the bracketed letters, or None if the judge's word does not match the letters."""
    out, i, inb = [], 0, False
    for c in marked.replace(" ", ""):
        if c == "[": inb = True
        elif c == "]": inb = False
        elif "\u0621" <= c <= "\u064a" and c != "\u0640":                  # tatweel is not a letter (the judge writes «[يـ]»)
            i += 1
            if inb: out.append(i)
    return out if i == len(letters) else None


def bracketed(letters, k):
    return "".join(f"[{c}]" if i == k else c for i, c in enumerate(letters, 1))


def spent():
    return sum(json.loads(l)["usd"] for l in open(SPEND)) if SPEND.exists() else 0.0


def cached(model):
    out = {}
    if CACHE.exists():
        for l in open(CACHE):
            d = json.loads(l)
            if d["model"] == model: out[d["id"]] = d
    return out


def shuffled(items):
    return sorted(items, key=lambda it: hashlib.md5(it["id"].encode()).hexdigest())


def judge(items, model, batch=8, resolution="high", thinking="low", tag="", max_usd=None, mode="graded"):
    """items: dicts with id, doc, page, box, cell, letters (reading order), k (1-based target). Returns {id: answer}."""
    from google.genai import types
    VERSION = VERSIONS[mode]
    done = cached(model); todo = shuffled([it for it in items if it["id"] + VERSION not in done])
    client = J17._client() if todo else None; pin, pout = PRICE[model]
    lev = getattr(types.PartMediaResolutionLevel, f"MEDIA_RESOLUTION_{resolution.upper()}")
    est_in = est_out = None; start = spent()
    for s in range(0, len(todo), batch):
        chunk = todo[s:s + batch]; parts = []; lines = []
        for n, it in enumerate(chunk, 1):
            parts += [types.Part(text=f"Image {n}:"), types.Part(inline_data=types.Blob(data=J17.png(item_image(it)), mime_type="image/png"),
                                                               media_resolution=types.PartMediaResolution(level=lev))]
            if mode == "blind": lines.append(f"  {n}. word «{''.join(it['letters'])}»"); continue
            lines.append(f"  {n}. word «{''.join(it['letters'])}», the letter: «{bracketed(it['letters'], it['k'])}» ({it['letters'][it['k'] - 1]}, letter {it['k']} of {len(it['letters'])} from the right)")
        parts.append(types.Part(text=(PROMPT_BLIND if mode == "blind" else PROMPT).format(items="\n".join(lines))))
        ei = (est_in or 1500) * len(chunk); eo = (est_out or 400) * len(chunk); est = ei / 1e6 * pin + eo / 1e6 * pout
        now = spent()
        if now + est > CAP or (max_usd is not None and now - start + est > max_usd):
            print(f"STOP: spent ${now:.3f}, this request ~${est:.3f} would cross the cap", flush=True); break
        cfg = dict(temperature=0.0, max_output_tokens=8192, response_mime_type="application/json", response_schema=SCHEMA_BLIND if mode == "blind" else SCHEMA)
        if thinking: cfg["thinking_config"] = types.ThinkingConfig(thinking_level=thinking)
        res = None
        for attempt in range(3):                                                 # bounded
            try:
                r = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                                                   config=types.GenerateContentConfig(**cfg))
                um = r.usage_metadata; tin = um.prompt_token_count or 0
                tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
                usd = tin / 1e6 * pin + tout / 1e6 * pout
                with open(SPEND, "a") as f:
                    f.write(json.dumps(dict(when=time.strftime("%H:%M:%S"), model=model, tag=tag, items=len(chunk), tin=tin, tout=tout,
                                            usd=usd, total=now + usd)) + "\n")
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
                if mode == "blind":
                    pos = marked_letters(a.get("marked", ""), it["letters"])
                    d = dict(model=model, id=it["id"] + VERSION, marked=a.get("marked", ""), pos=pos, clean=bool(a.get("clean")), why=a.get("why", ""), tag=tag)
                else:
                    d = dict(model=model, id=it["id"] + VERSION, verdict=a.get("verdict"), on=a.get("on", ""), why=a.get("why", ""), tag=tag)
                f.write(json.dumps(d, ensure_ascii=False) + "\n"); done[it["id"] + VERSION] = d
    return {it["id"]: done[it["id"] + VERSION] for it in items if it["id"] + VERSION in done}


def right(ans, k=None, lenient=False):
    if "pos" in ans: return ans["pos"] == [k] and (lenient or ans["clean"])
    return ans["verdict"] == "EXACT" or (lenient and ans["verdict"] == "MOSTLY")
