"""A second reading for contradictions.

`check` lists words whose ink signature matches another word's while their
texts differ (`substitution`): one of the readings is wrong. Each such
occurrence is read again from its own crop by Gemini. When Gemini agrees
with the reading the OCR gave that occurrence, it stands; when Gemini gives
one of the OTHER readings of the same ink, that is two independent readings
agreeing against one, and a correction is proposed (`<stem>.proposed.json`,
the format `inkscript correct --file` takes); anything else stays on the
review list. Nothing is applied here.
"""
from __future__ import annotations
import json, re, time
from pathlib import Path
import fitz

from ..pdf.type3 import DPI
from ..text import norm, fold_digits
from .numbers import crop_png


def core(t: str) -> str:
    """Letters and digits only, digits folded: a crop's padding brings the
    neighbouring comma or stop along ('، لا' for 'لا'), which is not what
    this reading is for."""
    return re.sub(r"[^\w]", "", fold_digits(norm(t)), flags=re.UNICODE).replace("_", "")

PROMPT = """Each image below is a small crop from a scanned Arabic journal page containing one printed word (or a short token).
Transcribe EXACTLY the characters printed in each crop, nothing else: the word as printed, with its vowel marks if printed, no explanation.
Answer with a JSON array of strings, one per crop, in the same order as the crops. If a crop is unreadable, use "".
"""


def reread_contradictions(client, model, pdf: Path, review_json: Path, batch: int = 12) -> dict:
    from google.genai import types
    r = json.loads(Path(review_json).read_text(encoding="utf-8"))
    items = [(c, sp) for c in r["conflicts"] if c["kind"] == "substitution" for sp in c["suspects"]]
    doc = fitz.open(pdf); dims = {}
    def pagedims(pn):
        if pn not in dims:
            pix = doc[pn - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY); dims[pn] = (pix.w, pix.h)
        return dims[pn]
    results = []; usage = dict(requests=0, tokens_in=0, tokens_out=0)
    for i in range(0, len(items), batch):
        chunk = items[i:i + batch]; parts = []
        for k, (c, sp) in enumerate(chunk):
            W, H = pagedims(sp["page"])
            parts.append(types.Part(text=f"crop {k + 1}:"))
            parts.append(types.Part(inline_data=types.Blob(data=crop_png(doc[sp["page"] - 1], sp["box"], sp.get("rot", 0), W, H), mime_type="image/png")))
        parts.append(types.Part(text=PROMPT))
        text = "[]"
        for attempt in range(3):
            try:
                resp = client.models.generate_content(model=model, contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(temperature=0.0, response_mime_type="application/json",
                                                       thinking_config=types.ThinkingConfig(thinking_level="low")))
                um = getattr(resp, "usage_metadata", None)
                if um:
                    usage["tokens_in"] += um.prompt_token_count or 0; usage["tokens_out"] += (um.candidates_token_count or 0)
                usage["requests"] += 1; text = resp.text or "[]"; break
            except Exception:
                time.sleep(2 * (attempt + 1))
        got = None
        try:
            got = json.loads(text)
        except Exception:
            m = re.search(r"\[.*\]", text, re.S)
            if m:
                try: got = json.loads(m.group(0))
                except Exception: got = None
        if not isinstance(got, list):
            got = None
        for k, (c, sp) in enumerate(chunk):
            g = got[k] if got is not None and k < len(got) and isinstance(got[k], str) else None
            others = [t for t in c["readings"] if core(t) != core(sp["text"])]
            if g is None or not g.strip():
                verdict = "unread"
            elif core(g) == core(sp["text"]) and (core(g) or norm(g).strip() == norm(sp["text"]).strip()):   # a dash is a dash
                verdict = "confirmed"
            elif not core(g):
                verdict = "review"
            elif core(g) == core(sp["text"]):
                verdict = "confirmed"
            elif any(core(g) == core(t) for t in others):
                verdict = "proposed"                      # two readings against one
            else:
                verdict = "review"
            results.append(dict(page=sp["page"], box=sp["box"], ocr=sp["text"], others=others, gemini=g, verdict=verdict, sig=c["sig"]))
    counts = {v: sum(1 for x in results if x["verdict"] == v) for v in ("confirmed", "proposed", "review", "unread")}
    counts["proposed_n"] = counts.pop("proposed")
    proposed = [dict(page=x["page"], box=x["box"], text=x["gemini"], was=x["ocr"]) for x in results if x["verdict"] == "proposed"]
    return dict(doc=pdf.stem, occurrences=len(results), **counts, results=results, proposed=proposed, usage=usage)
