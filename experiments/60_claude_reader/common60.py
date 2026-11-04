"""Experiment 60: Claude Opus 5.5 as the reader, with the SAME request experiment 43 sends Gemini 4 Argon.

Only the API plumbing differs (README "Method"): the same page JPEGs (structure.send_jpeg, 2400 px long edge,
quality 88) as base64 image blocks, each preceded by the same "Image k:" text part when there is more than one, then
the same prompt text (prompt43.make_prompt, or the exact text Gemini was sent, read back from the exam's stored
batch requests); Gemini's responseMimeType=application/json becomes one system line asking for the JSON object only;
Gemini's thinking "low" becomes output_config.effort "low" (Opus 5.5 always thinks, adaptively; effort is the only
control). The answer is saved in experiment 41/43's raw format, so rules43 -> enrich43 -> masters43 run unchanged.

Every call is logged to out/calls.jsonl (tokens, cost at list price, request / batch id; never the key).
Prices (platform.claude.com, read 2026-10-31): Opus 5.5 $4 / $20 per MTok in / out; Message Batches $2 / $10.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E43 = HERE.parent / "43_rehearsal"
sys.path.insert(0, str(E43))

MODEL = "claude-opus-5-5"
PRICE = {"standard": (4.0, 20.0), "batch": (2.0, 10.0)}     # USD per MTok (input, output); output includes thinking
CAP = 40.0                                                  # the owner's hard cap for the whole experiment
CALLS = OUT / "calls.jsonl"
LOCK = threading.Lock()
SYSTEM = ("Answer with the JSON object only: no prose before or after it, no Markdown code fence. "
          "It must parse with a strict JSON parser.")
IMG_TOKENS = 4784                                           # Opus 5.5's ceiling per image (2400 x 1697 page > it)


def client():
    import anthropic
    from dotenv import dotenv_values
    key = dotenv_values(HERE.parent.parent / ".env").get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("no ANTHROPIC_API_KEY in .env")
    return anthropic.Anthropic(api_key=key, max_retries=3, timeout=900)


# ------------------------------------------------------------------------------------------------ the pipeline

_P = None


def pipeline():
    """prompt43 (with structure as ST), set up exactly as run43.py does for the exam / gate-1 sets; page images
    from experiment 43's renders; render43's page check made read-only (a page never checked is not re-rendered,
    nothing is written into experiment 43)."""
    global _P
    if _P is None:
        import prompt43 as P
        import render43
        P.ST.PAGES = E43 / "out" / "pages"
        render43.records()
        orig = render43.check

        def check_ro(a, p, img):
            r = render43.records().get((a["stem"], p))
            if r is None:
                with LOCK, open(OUT / "render_unchecked.jsonl", "a") as f:
                    f.write(json.dumps(dict(stem=a["stem"], page=p)) + "\n")
                return dict(stem=a["stem"], page=p, kept=False, unchecked=True)
            return r
        render43.check = check_ro
        _ = orig
        _P = P
    return _P


def articles(which: str) -> dict:
    """stem -> article dict, from the sample run43.py uses for the set."""
    pipeline()
    import run43
    return {a["stem"]: a for a in run43.articles(which)}


# ------------------------------------------------------------------------------------------------ requests

def content_from(prompt: str, imgs: list[bytes]) -> list[dict]:
    """Gemini's parts, in order, as Messages API content blocks."""
    parts = []
    for k, im in enumerate(imgs, 1):
        if len(imgs) > 1:
            parts.append({"type": "text", "text": f"Image {k}:"})
        parts.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                   "data": base64.b64encode(im).decode()}})
    parts.append({"type": "text", "text": prompt})
    return parts


def content_from_gemini_parts(parts: list[dict]) -> list[dict]:
    """A stored Gemini batch request's parts (text / inlineData), unchanged, as content blocks."""
    out = []
    for p in parts:
        if "text" in p:
            out.append({"type": "text", "text": p["text"]})
        elif "inlineData" in p:
            out.append({"type": "image", "source": {"type": "base64", "media_type": p["inlineData"]["mimeType"],
                                                     "data": p["inlineData"]["data"]}})
        else:
            raise ValueError(f"unknown part {list(p)}")
    return out


def max_out(n_pages: int) -> int:
    """Experiment 41/43's output allowance (3000 a page + 6000, Batch's 32768 ceiling) plus 8000 for thinking,
    which Claude bills as output and counts inside max_tokens (Gemini's thinking 'low' reported none)."""
    return min(32768, 3000 * n_pages + 6000) + 8000


def params(content: list[dict], n_pages: int, effort: str = "low") -> dict:
    return dict(model=MODEL, max_tokens=max_out(n_pages), system=SYSTEM,
                output_config={"effort": effort},
                messages=[{"role": "user", "content": content}])


def est_in(content: list[dict]) -> int:
    """Input tokens, estimated before a call (calibrated on the pilot: README "Pilot")."""
    n_img = sum(1 for c in content if c["type"] == "image")
    chars = sum(len(c["text"]) for c in content if c["type"] == "text")
    return IMG_TOKENS * n_img + int(chars / CHARS_PER_TOKEN) + 300


CHARS_PER_TOKEN = 1.6          # conservative until the pilot measures it


# ------------------------------------------------------------------------------------------------ answers

def parse_answer(text: str):
    t = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", t, re.S)
    if m:
        t = m.group(1)
    try:
        return json.loads(t), ("fenced" if m else "clean")
    except Exception:
        pass
    i, j = t.find("{"), t.rfind("}")           # prose around the object: recorded as such, never repaired further
    if i >= 0 and j > i:
        try:
            return json.loads(t[i:j + 1]), "prose_around"
        except Exception:
            return None, "invalid"
    return None, "invalid"


def usage_of(msg) -> dict:
    u = msg.usage
    return dict(tin=u.input_tokens or 0, tout=u.output_tokens or 0,
                cache_read=getattr(u, "cache_read_input_tokens", 0) or 0,
                cache_write=getattr(u, "cache_creation_input_tokens", 0) or 0)


def usd_of(u: dict, mode: str) -> float:
    pin, pout = PRICE[mode]
    return ((u["tin"] + u["cache_write"] * 1.25 + u["cache_read"] * 0.1) * pin + u["tout"] * pout) / 1e6


def spent() -> float:
    if not CALLS.exists():
        return 0.0
    return sum(json.loads(s).get("usd", 0) for s in CALLS.read_text().splitlines() if s.strip())


def log_call(**row):
    with LOCK:
        CALLS.parent.mkdir(parents=True, exist_ok=True)
        row = dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=MODEL, **row)
        row["total"] = round(spent() + row.get("usd", 0), 4)
        with open(CALLS, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def save_answer(rf: Path, stem: str, x: int, y: int, msg, mode: str, prompt_version: str, effort: str,
                extra: dict | None = None) -> dict:
    """The raw record (experiment 41's format); an unusable answer goes to <name>.failed.json + the text."""
    u = usage_of(msg)
    usd = usd_of(u, mode)
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    ans, how = (None, "max_tokens") if msg.stop_reason == "max_tokens" else parse_answer(text)
    rec = dict(stem=stem, first=x, last=y, pages=y - x + 1, usd=round(usd, 6), mode=mode, prompt=prompt_version,
               thinking=f"effort {effort}", finish=msg.stop_reason, tin=u["tin"], tout=u["tout"], think=None,
               model=MODEL, parse=how, msg_id=msg.id, **(extra or {}))
    rf.parent.mkdir(parents=True, exist_ok=True)
    if ans is None:
        (rf.parent / (rf.stem + ".failed.txt")).write_text(text, encoding="utf-8")
        jdump(rf.parent / (rf.stem + ".failed.json"), dict(rec, failed=True))
    else:
        jdump(rf, dict(rec, answer=ans if isinstance(ans, dict) else {"pages": ans}))
    return dict(rec, usd=usd, ok=ans is not None)


def jdump(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))
