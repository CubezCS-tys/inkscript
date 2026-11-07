"""Experiment 81, step 4: blind Gemini judging of a sample of held-out lines (paid; cap $20 for the experiment).

    python judge81.py crops                 judge crops (96 px from 300-dpi renders, as experiment 77's gem77.py)
    python judge81.py run [LIMIT] [T]       two calls a line (T threads, default 4); every answer cached and costed
    python judge81.py spent

The sample (out/judge/sample.jsonl) is written by agree81.py.  For each line Gemini (gemini-3.8-flash, thinking low,
experiment 71/77's production Flash) is asked twice, in one conversation:
  1. BLIND: the line image only -> its own transcription (no candidate shown);
  2. after it has committed that reading (its answer is in the conversation), the distinct candidate readings of the
     line (Azure, Argon, our readers, the fusions), lettered in random order, with no names -> which candidates match
     the image exactly (letters, dots, hamza, ى/ي, ة/ه, marks as printed, digits, word spaces; punctuation ignored),
     or none (then its corrected reading), or unreadable.
Price $0.75 / $3.75 per M tokens in / out (thinking billed as output).  Every request appends to out/judge/spend.jsonl;
no request is sent once the total reaches STOP_AT.  The key is read by inkscript.enrich.judge._key, never printed.
"""
from __future__ import annotations

import hashlib
import json
import random
import string
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
J = OUT / "judge"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E.parent / "src"))

SPEND, CACHE = J / "spend.jsonl", J / "answers.jsonl"
MODEL = "gemini-3.8-flash"
PIN, POUT = 0.75, 3.75
CAP = 20.0
STOP_AT = float(__import__("os").environ.get("STOP_AT", "19.4"))
_lock = threading.Lock()

BLIND = """The image shows ONE printed line cut from a scanned journal page, mostly Arabic (it may contain Latin words,
digits or punctuation). Edges of the neighbouring lines may show at the top or bottom: ignore them.

Transcribe the line exactly as printed: every letter with its dots, hamza forms, ى versus ي, ة versus ه, vowel marks
only where printed, digits as printed (Arabic-Indic or Latin), and the spaces between words. Do not modernise old
spellings and do not correct misprints. Write the text in its normal logical (reading) order.

Answer with JSON: "reading" (the transcription), "legible" (false if the line cannot be read with confidence: cut
off, blurred, not a text line)."""

VERDICT = """Now compare these candidate transcriptions of the same line with the image, character by character:
{cands}

What counts: letters, dots, hamza forms, ى versus ي, ة versus ه, vowel marks where printed, digits, and the spaces
between words. Ignore punctuation marks entirely (commas, full stops, brackets, quotes, dashes, colons) and spaces
next to them. Old spellings and misprints must be kept as printed.

Answer with JSON:
- "right": the letters of every candidate that matches the printed line exactly under these rules (may be empty);
- "verdict": "match" if at least one candidate is right, "none" if every candidate is wrong, "unreadable" if the
  image cannot be read with confidence;
- "reading": the correct transcription of the whole line (when the verdict is "match", copy a right candidate);
- "note": a few words on the differences."""

S1 = {"type": "object", "properties": {"reading": {"type": "string"}, "legible": {"type": "boolean"}},
      "required": ["reading", "legible"]}
S2 = {"type": "object", "properties": {"right": {"type": "array", "items": {"type": "string"}},
                                       "verdict": {"type": "string", "enum": ["match", "none", "unreadable"]},
                                       "reading": {"type": "string"}, "note": {"type": "string"}},
      "required": ["right", "verdict", "reading", "note"]}


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in SPEND.read_text().splitlines() if l.strip())


def crops():
    import cv2
    import pypdfium2 as pdfium
    from common77 import azure_pages, cut_line, nonempty_lines, render_page
    cv2.setNumThreads(1)
    S = [json.loads(l) for f in ("sample", "calib", "pilot", "nuqta_extra") if (J / f"{f}.jsonl").exists()
         for l in open(J / f"{f}.jsonl", encoding="utf-8")]
    pages = {(p["stem"], p["page"]): p for p in map(json.loads, open(OUT / "pages81.jsonl", encoding="utf-8"))}
    by = defaultdict(list)
    for s in S:
        by[(s["stem"], s["page"])].append((s["i"], s["key"]))
    (J / "crops").mkdir(parents=True, exist_ok=True)
    for (stem, p), items in sorted(by.items()):
        if all((J / "crops" / f"{k}.png").exists() for _, k in items):
            continue
        m = pages[(stem, p)]
        doc = pdfium.PdfDocument(m["pdf"])
        pg = azure_pages(m["azure"])[p - 1]
        img = render_page(doc, p - 1, dpi=300)
        doc.close()
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        L = {ln["i"]: ln for ln in nonempty_lines(pg)}
        for i, k in items:
            c, _ = cut_line(img, L[i]["poly"], sx, sy, H=96, test=True)
            if c is not None:
                cv2.imwrite(str(J / "crops" / f"{k}.png"), c)
    print("crops:", len(list((J / "crops").glob("*.png"))))


_client = None


def _gen(contents, schema, types, key=""):
    cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=6000, response_mime_type="application/json",
                                      response_schema=schema, thinking_config=types.ThinkingConfig(thinking_level="low"))
    t0 = time.time()
    r = _client.models.generate_content(model=MODEL, contents=contents, config=cfg)
    um = r.usage_metadata
    tin = um.prompt_token_count or 0
    tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
    with _lock:                       # every call is logged at once, also one whose answer fails to parse
        with open(SPEND, "a") as f:
            f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), key=key, tin=tin, tout=tout,
                                    usd=round(tin / 1e6 * PIN + tout / 1e6 * POUT, 6), secs=round(time.time() - t0, 2))) + "\n")
    if not r.text:
        raise ValueError("empty answer")
    return r, tin, tout, time.time() - t0


def ask(s: dict) -> dict | None:
    global _client
    from google import genai
    from google.genai import types
    from inkscript.enrich.judge import _key
    png = (J / "crops" / f"{s['key']}.png").read_bytes()
    with _lock:
        if spent() >= STOP_AT:
            return None
        if _client is None:
            _client = genai.Client(api_key=_key())
    img = types.Part(inline_data=types.Blob(data=png, mime_type="image/png"))
    letters = string.ascii_uppercase
    cl = "\n".join(f"{letters[j]}: {c}" for j, c in enumerate(s["shown"]))
    for attempt in range(3):
        try:
            c1 = [types.Content(role="user", parts=[img, types.Part(text=BLIND)])]
            r1, ti1, to1, t1 = _gen(c1, S1, types, s["key"])
            a1 = json.loads(r1.text)
            c2 = c1 + [types.Content(role="model", parts=[types.Part(text=r1.text)]),
                       types.Content(role="user", parts=[types.Part(text=VERDICT.format(cands=cl))])]
            r2, ti2, to2, t2 = _gen(c2, S2, types, s["key"])
            a2 = json.loads(r2.text)
            usd = (ti1 + ti2) / 1e6 * PIN + (to1 + to2) / 1e6 * POUT
            right = sorted({x.strip().upper()[:1] for x in a2.get("right", []) if x.strip()})
            rec = dict(key=s["key"], blind=a1.get("reading", ""), legible=a1.get("legible"), verdict=a2.get("verdict"),
                       right=right, right_idx=[letters.index(x) for x in right if x in letters[:len(s["shown"])]],
                       reading=a2.get("reading", ""), note=a2.get("note", ""), usd=round(usd, 6))
            with _lock:
                with open(CACHE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            return rec
        except Exception as e:  # noqa: BLE001
            print("  request failed:", type(e).__name__, str(e)[:160], flush=True)
            time.sleep(5 * (attempt + 1))
    return None


def run(limit: int | None, threads: int = 4, which: str = "sample"):
    global CACHE
    if which == "pilot":
        CACHE = J / "answers_pilot.jsonl"
    if which == "v3extra":
        CACHE = J / "answers_v3.jsonl"
    S = [json.loads(l) for l in open(J / f"{which}.jsonl", encoding="utf-8")]
    done = {json.loads(l)["key"] for l in open(CACHE, encoding="utf-8")} if CACHE.exists() else set()
    todo = [s for s in S if s["key"] not in done and (J / "crops" / f"{s['key']}.png").exists()]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} to ask; spent so far ${spent():.3f}", flush=True)
    n = 0
    with ThreadPoolExecutor(threads) as ex:
        for r in ex.map(ask, todo):
            n += 1
            if r is None and spent() >= STOP_AT:
                print("STOP: spend limit reached", flush=True)
                break
            if n % 100 == 0:
                print(f"{n} answered, ${spent():.3f}", flush=True)
    rows = [json.loads(l) for l in open(CACHE, encoding="utf-8")]
    print(f"answers {len(rows)}; spent ${spent():.3f}; mean ${spent() / max(1, len(rows)):.5f}/line;",
          Counter(r["verdict"] for r in rows))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "crops":
        crops()
    elif c == "run":
        run(int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "0" else None,
            int(sys.argv[3]) if len(sys.argv) > 3 else 4, sys.argv[4] if len(sys.argv) > 4 else "sample")
    elif c == "spent":
        print(f"${spent():.4f}")
