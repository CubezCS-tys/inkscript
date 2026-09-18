"""A second reading for numbers only.

A wrong digit in a date is the error that hurts most and shows least, so
every word containing a digit gets read again from its own ink by Gemini,
several crops per request, and a disagreement with the OCR goes on the
review list. Nothing is corrected automatically: two readings that differ
mean a person looks; two that agree mean the number is very likely right.
"""
from __future__ import annotations
import base64, io, json, re, time
from pathlib import Path
import fitz, numpy as np, cv2

from ..pdf.type3 import Frame, DPI
from ..text import norm

PROMPT = """Each image below is a small crop from a scanned Arabic journal page and contains a number, possibly with brackets, punctuation or a word attached.
Transcribe EXACTLY the characters printed in each crop, in reading order, nothing else: keep brackets and punctuation as printed, digits as printed (Arabic-Indic or Western), no spaces added or removed.
Answer with a JSON array of strings, one per crop, in the same order as the crops. If a crop is unreadable, use "".
"""


def crop_png(page, box, rot, W, H, pad=8):
    f = Frame(rot, W, H)
    (x0, y0), (x1, y1) = f.to_page(box[0], box[1]), f.to_page(box[2], box[3])
    r = fitz.Rect(min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad) * (72 / DPI)
    pix = page.get_pixmap(dpi=300, clip=r & page.rect, colorspace=fitz.csGRAY)
    if not rot:
        return pix.tobytes("png")
    # a sideways page: turn the crop upright, as the layout did, or the
    # digits are read in the wrong order
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    img = np.ascontiguousarray(np.rot90(img, 1 if rot == 90 else -1))
    ok, png = cv2.imencode(".png", img)
    return png.tobytes()


def reread_numbers(client, model, pdf: Path, review_json: Path, batch: int = 12, limit: int = 0) -> dict:
    from google.genai import types
    r = json.loads(Path(review_json).read_text(encoding="utf-8"))
    nums = r["numbers"][:limit] if limit else r["numbers"]
    doc = fitz.open(pdf); dims = {}
    def pagedims(pn):
        if pn not in dims:
            pix = doc[pn - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY); dims[pn] = (pix.w, pix.h)
        return dims[pn]
    results = []; usage = dict(requests=0, tokens_in=0, tokens_out=0)
    for i in range(0, len(nums), batch):
        chunk = nums[i:i + batch]
        parts = []
        for k, n in enumerate(chunk):
            W, H = pagedims(n["page"])
            parts.append(types.Part(text=f"crop {k + 1}:"))
            parts.append(types.Part(inline_data=types.Blob(data=crop_png(doc[n["page"] - 1], n["box"], n.get("rot", 0), W, H), mime_type="image/png")))
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
        # The answer is a JSON array, sometimes inside a ``` fence or with
        # prose around it; a batch that cannot be parsed is "unread", never
        # a disagreement (five of six documents came back 0% agreed because
        # every batch failed to parse and every number counted as wrong).
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
        for k, n in enumerate(chunk):
            if got is None or k >= len(got) or not isinstance(got[k], str):
                results.append(dict(page=n["page"], box=n["box"], ocr=n["text"], gemini=None, agree=None)); continue
            g = got[k]
            # Judge the digits; brackets and commas at the edge of a crop come
            # and go with the padding and are not what this reading is for.
            digits = lambda t: re.sub(r"[^0-9٠-٩۰-۹]", "", t).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
            same = digits(g) == digits(n["text"]) and digits(g) != ""
            results.append(dict(page=n["page"], box=n["box"], ocr=n["text"], gemini=g, agree=same))
    n_agree = sum(1 for x in results if x["agree"]); unread = sum(1 for x in results if x["agree"] is None)
    return dict(doc=pdf.stem, numbers=len(results), agree=n_agree, unread=unread,
                disagree=[x for x in results if x["agree"] is False], usage=usage)
