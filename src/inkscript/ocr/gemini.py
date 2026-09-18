"""Gemini as a transcription instrument: the strict prompt, per-page calls,
and the cached front-page read."""
from __future__ import annotations
import json, os, time
from pathlib import Path

UNREADABLE = "[[UNREADABLE]]"


GEMINI_MODEL = "gemini-3.7-flash"


# $0.75/M in, $3.75/M out (list, through 2026-12-31). A page costs ~2240 vision
# tokens at ultra_high plus ~350 of prompt, and returns ~2000 for dense Arabic.
# Output dominates input roughly 4:1, which is the whole argument for running at
# ultra_high: the resolution upgrade from the 560-token PDF default is ~$1.26 per
# 1,000 pages. Buying less resolution saves nothing worth having.
GEMINI_IN_PER_M, GEMINI_OUT_PER_M = 0.75, 3.75


# The prompt IS the engine configuration here. Azure and Mistral do what they do;
# a language model does what it is told, and its untold default is to be helpful —
# which for transcription means silently improving the text. Every "do not" below
# is a specific way that helpfulness corrupts a scholarly corpus.
STRICT_PROMPT = f"""You are a transcription instrument, not an editor.

Reproduce every character printed on this page image, in natural reading order
(right-to-left for Arabic; finish a column before starting the next).

REPRODUCE EXACTLY:
  * Tashkeel/harakat exactly where printed, and nowhere else. Do not add marks
    the page does not show. Do not drop marks it does.
  * Honorifics in the form printed. If the page shows the single glyph ﷺ, output
    ﷺ. If it spells out صلى الله عليه وسلم, output the words. Never convert one
    form into the other.
  * The original spelling, including anything that looks like an error. Do not
    modernise orthography; do not normalise hamza, alif maqsura or ta marbuta.
  * Numerals in the script printed (٤ stays ٤, 4 stays 4).
  * Line and paragraph breaks as they fall on the page.

DO NOT translate, summarise, explain, comment, correct grammar or spelling, skip
repeated or boilerplate text, or add markdown/headings/formatting that is not
printed on the page.

If a region is genuinely illegible, output exactly {UNREADABLE} in its place and
carry on. An honest gap is worth more than a plausible guess — a guess here is
indistinguishable from the real text downstream, and corrupts the archive
silently.

Output the transcription and nothing else."""


# Control arm. This is what you get if you do not think about the prompt, and it
# exists to measure what the paragraphs above are actually worth.
NAIVE_PROMPT = "Extract the text from this page."


JSON_PROMPT = (STRICT_PROMPT.replace("Output the transcription and nothing else.", "")
               + "Return the page as a list of blocks in reading order.")


JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string",
                             "enum": ["title", "heading", "paragraph", "footnote",
                                      "table", "caption", "other"]},
                    "text": {"type": "string"},
                },
                "required": ["type", "text"],
            },
        }
    },
    "required": ["blocks"],
}


ARMS = {"strict": STRICT_PROMPT, "naive": NAIVE_PROMPT, "json": JSON_PROMPT}


def page_images(pdf: Path, fallback_dpi: int = 300,
                limit: int = 0) -> list[tuple[bytes, str, int, int]]:
    """One image per page of the shared PDF — the same pixels Azure and Mistral got.

    These pages are single full-page scans, so the embedded image IS the page.
    Lifting that XObject out verbatim means Gemini sees the original bytes with
    no resample step at all; rendering instead would put our own interpolation
    between the scan and the model and then blame the model for the difference.

    Falls back to rasterising only when a page is not a single clean image.
    `limit` stops after that many pages, so a front-page read of a 90-page
    document does not rasterise the other 89.
    """
    import fitz
    doc = fitz.open(pdf)
    out: list[tuple[bytes, str, int, int]] = []
    for i in range(min(doc.page_count, limit) if limit else doc.page_count):
        pg = doc[i]
        blob = None
        imgs = pg.get_images(full=True)
        if len(imgs) == 1:
            info = doc.extract_image(imgs[0][0])
            ext = (info.get("ext") or "").lower()
            if ext in ("png", "jpeg", "jpg") and info.get("image"):
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"
                blob = (info["image"], mime, info["width"], info["height"])
        if blob is None:
            pix = pg.get_pixmap(dpi=fallback_dpi)
            blob = (pix.tobytes("png"), "image/png", pix.width, pix.height)
        if pg.rotation and blob[1] != "":
            # The embedded scan is stored sideways and the page's /Rotate turns
            # it upright for the viewer; Gemini must see it upright too. (A
            # sideways cover page came back empty.)
            import cv2, numpy as np
            img = cv2.imdecode(np.frombuffer(blob[0], np.uint8), cv2.IMREAD_UNCHANGED)
            k = {90: -1, 180: 2, 270: 1}[pg.rotation % 360]
            img = np.ascontiguousarray(np.rot90(img, k))
            ok, png = cv2.imencode(".png", img)
            blob = (png.tobytes(), "image/png", img.shape[1], img.shape[0])
        out.append(blob)
    doc.close()
    return out


def gemini_text(client, model: str, images: list, arm: str, resolution: str,
                max_out: int, thinking: bool) -> tuple[str, dict]:
    """Transcribe page by page. Returns (text, usage).

    One request per page, deliberately:
      * a failure costs one page, not a document
      * output length stays far from the cap, which is where looping starts
      * no cross-page bleed — page 4 cannot borrow phrasing from page 3

    The cost is real: a word hyphenated across a page break cannot be rejoined.
    That is the right trade for a test whose purpose is measuring per-page
    fidelity, and worth revisiting for production.
    """
    from google.genai import types

    level = getattr(types.PartMediaResolutionLevel,
                    f"MEDIA_RESOLUTION_{resolution.upper()}")
    prompt = ARMS[arm]
    cfg = dict(
        temperature=0.0,          # transcription has one right answer; do not sample
        max_output_tokens=max_out,
    )
    if arm == "json":
        cfg["response_mime_type"] = "application/json"
        cfg["response_schema"] = JSON_SCHEMA
    if not thinking:
        # Transcription is perception, not reasoning. Thinking tokens are billed
        # as output — the expensive side — so this is off unless asked for.
        cfg["thinking_config"] = types.ThinkingConfig(thinking_level="low")

    pages, usage = [], {"in": 0, "out": 0, "requests": 0, "errors": 0}
    for idx, (data, mime, w, h) in enumerate(images, 1):
        part = types.Part(
            inline_data=types.Blob(data=data, mime_type=mime),
            media_resolution=types.PartMediaResolution(level=level),
        )
        # Image first, instruction last: Google's own guidance for single-page reads.
        contents = [types.Content(role="user", parts=[part, types.Part(text=prompt)])]
        text = ""
        for attempt in range(3):
            try:
                r = client.models.generate_content(
                    model=model, contents=contents,
                    config=types.GenerateContentConfig(**cfg))
                um = getattr(r, "usage_metadata", None)
                if um:
                    usage["in"] += um.prompt_token_count or 0
                    usage["out"] += (um.candidates_token_count or 0) + (
                        getattr(um, "thoughts_token_count", 0) or 0)
                usage["requests"] += 1
                text = (r.text or "").strip()
                break
            except Exception as e:
                if attempt == 2:
                    usage["errors"] += 1
                    text = f"{UNREADABLE} <!-- page {idx}: {type(e).__name__}: {e} -->"
                else:
                    time.sleep(2 * (attempt + 1))
        if arm == "json" and text:
            try:
                text = "\n\n".join(b.get("text", "")
                                   for b in json.loads(text).get("blocks", []))
            except Exception:
                pass          # keep the raw string; a parse failure is itself a result
        pages.append(text)
    return "\n\n".join(pages), usage


def gemini_page1(client, scan: Path, cache: Path, model: str) -> tuple[str | None, dict]:
    """Page 1 through Gemini, or the cached read. None means the call failed."""
    if cache.exists() and len(cache.read_text(encoding="utf-8").strip()) >= 20:
        return cache.read_text(encoding="utf-8"), {"in": 0, "out": 0, "cached": True}
    images = page_images(scan, limit=1)
    text, usage = gemini_text(client, model, images, "strict", "ultra_high", 8192, False)
    # An empty answer is usually transient (a retry reads the page), sometimes
    # the recitation filter; try again, the last time at a lower resolution.
    for res in ("ultra_high", "high"):
        if not usage["errors"] and len(text.strip()) >= 20:
            break
        time.sleep(3)
        text, u2 = gemini_text(client, model, images, "strict", res, 8192, False)
        for k in ("in", "out", "requests", "errors"):
            usage[k] = usage.get(k, 0) + u2.get(k, 0)
    if usage["errors"] or len(text.strip()) < 20:
        return None, usage        # never cache a failure or an empty answer, or it is never retried
    cache.write_text(text, encoding="utf-8")
    return text, usage


def client():
    """A google-genai client from GEMINI_API_KEY (loaded by inkscript.config)."""
    from google import genai
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY not set — put it in .env at the repo root")
    return genai.Client(api_key=key)
