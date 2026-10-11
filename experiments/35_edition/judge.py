"""Experiment 35: a vision judge compares the original scan page with the rebuilt layout-faithful page.

    PYTHONPATH=src .venv/bin/python experiments/35_edition/judge.py                 # estimate only
    PYTHONPATH=src .venv/bin/python experiments/35_edition/judge.py --go            # judge (cached; capped)

Gemini (gemini-3.1-pro-preview, the confirming judge of experiment 27) is shown two pictures of one page: the
scan, and the page rebuilt from the master files (a new typeset page whose blocks sit where ALTO says they were).
It counts the blocks of each, says whether the same blocks are there in the same places and order, lists what is
missing or extra, checks the headings (size, weight, place) and scores placement, typography and the whole.

Planted faults calibrate it: on a few sampled pages a rebuild is made with one fault put in on purpose (a block
dropped, two blocks' texts swapped, a heading set as body text); a judge that does not see those is no judge.

Every answer is cached by model + page + a hash of both pictures (a rebuilt page that changes is judged again),
every request's tokens and cost go to out/judge_spend.jsonl, and a request that would take the logged total over
the cap ($5 for the whole experiment) is not sent.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from pathlib import Path

from inkscript.enrich.judge import PRICE, _key

OUT = Path("/home/yassine/inkscript/experiments/35_edition/out")
MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")
MODEL = "gemini-3.1-pro-preview"
CAP = 5.0
VERSION = "j1"

PROMPT = """You are checking a re-typeset edition of a printed Arabic journal page.

Image 1 is the ORIGINAL: a scan of the printed page.
Image 2 is the REBUILD: the same page typeset anew, in a clean font, from the OCR text and the block positions read off the scan. The rebuild is supposed to have the same blocks of text (title, author lines, headings, paragraphs, footnotes, table cells, running heads, page numbers) in the same places, the same reading order and the same relative sizes. It is NOT supposed to copy the original typeface, the scan's noise, rules/lines, decorations, logos or pictures (those are not text) — do not count missing pictures, ornaments or ruling lines as faults, but do mention them in "notes".

Compare them block by block and answer:
- blocks_original / blocks_rebuilt: how many text blocks you count on each (a paragraph, a heading, a footnote, a running head, a page number, a table cell group or a table = one block each; be consistent between the two).
- same_blocks: "yes" (every text block of the original has its counterpart), "mostly" (one or two small ones differ), "no".
- missing: text blocks of the original that are absent from the rebuild (describe each briefly: what it is and where, quote its first words).
- extra: text blocks of the rebuild that are not on the original.
- same_order: does the rebuild keep the original's arrangement and reading order (columns, right to left, top to bottom)? "yes" / "mostly" / "no", and moved: blocks that sit in a clearly different place or order.
- headings: "right" / "partly" / "wrong" — titles and section headings stand out in the rebuild as they do in the original (bigger or bolder, same place); heading_issues: list.
- text_issues: visible problems in the rebuild's text: overflowing or overlapping text, text far too small or too large for its place, wrong direction (left-to-right Arabic), broken letters, lines that clearly differ in wording from the original (quote them).
- placement (1-5): how closely block positions and sizes follow the original (5 = the same page layout).
- typography (1-5): how clean and readable the rebuild is as a typeset page (5 = a well-set printed page).
- overall (1-5): would a reader accept the rebuild as a faithful new edition of this page?
- summary: one or two sentences.
- notes: anything else (pictures, rules, ornaments, stamps not reproduced).

Reply with JSON only."""

SCHEMA = {"type": "object", "properties": {
    "blocks_original": {"type": "integer"}, "blocks_rebuilt": {"type": "integer"},
    "same_blocks": {"type": "string", "enum": ["yes", "mostly", "no"]},
    "missing": {"type": "array", "items": {"type": "string"}},
    "extra": {"type": "array", "items": {"type": "string"}},
    "same_order": {"type": "string", "enum": ["yes", "mostly", "no"]},
    "moved": {"type": "array", "items": {"type": "string"}},
    "headings": {"type": "string", "enum": ["right", "partly", "wrong"]},
    "heading_issues": {"type": "array", "items": {"type": "string"}},
    "text_issues": {"type": "array", "items": {"type": "string"}},
    "placement": {"type": "integer"}, "typography": {"type": "integer"}, "overall": {"type": "integer"},
    "summary": {"type": "string"}, "notes": {"type": "string"}},
    "required": ["blocks_original", "blocks_rebuilt", "same_blocks", "missing", "extra", "same_order", "moved",
                 "headings", "heading_issues", "text_issues", "placement", "typography", "overall", "summary",
                 "notes"]}

# measured on the first requests and rounded up (two page images at high resolution + the prompt; thinking low)
EST_IN, EST_OUT = 3500, 1500


def render(pdf: Path, page: int, height: int = 1600) -> bytes:
    """One page as a JPEG about `height` pixels tall (enough to read body text; Gemini scales to its own tiles)."""
    import pymupdf
    with pymupdf.open(str(pdf)) as d:
        p = d[page - 1]
        z = height / p.rect.height
        pix = p.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False)
        return pix.tobytes("jpeg", jpg_quality=85)


def spent(log: Path) -> float:
    if not log.exists():
        return 0.0
    return sum(json.loads(x)["usd"] for x in log.read_text().splitlines() if x.strip())


def cached(cache: Path) -> dict:
    out = {}
    if cache.exists():
        for line in cache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                out[d["key"]] = d
    return out


def ask(client, img1: bytes, img2: bytes):
    from google.genai import types
    lev = types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH
    parts = [types.Part(text="Image 1 (ORIGINAL scan):"),
             types.Part(inline_data=types.Blob(data=img1, mime_type="image/jpeg"),
                        media_resolution=types.PartMediaResolution(level=lev)),
             types.Part(text="Image 2 (REBUILD):"),
             types.Part(inline_data=types.Blob(data=img2, mime_type="image/jpeg"),
                        media_resolution=types.PartMediaResolution(level=lev)),
             types.Part(text=PROMPT)]
    cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=8192, response_mime_type="application/json",
                                      response_schema=SCHEMA,
                                      thinking_config=types.ThinkingConfig(thinking_level="low"))
    r = client.models.generate_content(model=MODEL, contents=[types.Content(role="user", parts=parts)], config=cfg)
    um = r.usage_metadata
    tin = um.prompt_token_count or 0
    tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
    return json.loads(r.text), tin, tout


def items_from(sample: Path, editions: Path, planted: Path | None) -> list[dict]:
    """Each item: the scan page and the rebuilt page (pdf, page). Planted faults are separate rebuilt PDFs."""
    s = json.loads(sample.read_text())
    items = []
    for p in s["pages"]:
        lay = Path(p.get("editions") or editions) / p["id"] / f"{p['id']}.layout.pdf"
        scan = MERGED / f"{p['id']}.pdf"
        if p.get("scan"):
            scan = Path(p["scan"])
        items.append(dict(key=f"{p['id']}#p{p['page']}", id=p["id"], page=p["page"], stratum=p["stratum"],
                          scan=str(scan), rebuild=str(lay), rebuild_page=p["page"]))
    if planted and planted.exists():
        for p in json.loads(planted.read_text()):
            items.append(dict(key=f"{p['id']}#p{p['page']}#{p['fault']}", id=p["id"], page=p["page"],
                              stratum="planted:" + p["fault"], fault=p["fault"], fault_detail=p.get("detail", ""),
                              scan=p["scan"], rebuild=p["rebuild"], rebuild_page=p.get("rebuild_page", 1)))
    return items


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default=str(OUT / "sample.json"))
    ap.add_argument("--editions", default=str(OUT / "editions"))
    ap.add_argument("--planted", default=str(OUT / "planted" / "planted.json"))
    ap.add_argument("--go", action="store_true", help="send the requests (otherwise: estimate only)")
    ap.add_argument("--cap", type=float, default=CAP)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    cache, log = OUT / "judge_cache.jsonl", OUT / "judge_spend.jsonl"
    items = items_from(Path(a.sample), Path(a.editions), Path(a.planted))
    if a.limit:
        items = items[:a.limit]
    done = cached(cache)
    todo, ready = [], []
    for it in items:
        if not Path(it["rebuild"]).exists() or not Path(it["scan"]).exists():
            print("missing:", it["key"], it["rebuild"] if not Path(it["rebuild"]).exists() else it["scan"])
            continue
        i1, i2 = render(Path(it["scan"]), it["page"]), render(Path(it["rebuild"]), it["rebuild_page"])
        h = hashlib.sha256(i1 + i2).hexdigest()[:16]
        it["ckey"] = f"{MODEL}|{VERSION}|{it['key']}|{h}"
        (todo if it["ckey"] not in done else ready).append((it, i1, i2))
    pin, pout = PRICE[MODEL]
    per = EST_IN / 1e6 * pin + EST_OUT / 1e6 * pout
    print(f"{len(items)} items, {len(ready)} cached, {len(todo)} to ask; estimate ${len(todo) * per:.2f} "
          f"(${per:.4f} each); spent so far ${spent(log):.3f}, cap ${a.cap}")
    if a.go and todo:
        from google import genai
        key = _key()
        if not key:
            sys.exit("GEMINI_API_KEY not set")
        client = genai.Client(api_key=key)
        for it, i1, i2 in todo:
            if spent(log) + per > a.cap:
                print(f"STOP: spent ${spent(log):.3f}; the next request would cross the ${a.cap} cap")
                break
            res = None
            for attempt in range(3):
                try:
                    res, tin, tout = ask(client, i1, i2)
                    usd = tin / 1e6 * pin + tout / 1e6 * pout
                    with open(log, "a") as f:
                        f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=MODEL, key=it["key"],
                                                tin=tin, tout=tout, usd=usd)) + "\n")
                    break
                except Exception as e:                          # bounded: three tries, then skipped
                    print("  failed:", type(e).__name__, str(e)[:200])
                    time.sleep(5 * (attempt + 1))
            if res is None:
                continue
            d = dict(key=it["ckey"], item=it["key"], model=MODEL, when=time.strftime("%Y-%m-%d %H:%M:%S"),
                     answer=res)
            with open(cache, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
            done[it["ckey"]] = d
            print(f"  {it['key']}: overall {res.get('overall')} blocks {res.get('blocks_original')}/"
                  f"{res.get('blocks_rebuilt')} missing {len(res.get('missing', []))}  total ${spent(log):.3f}")
    rows = []
    for it, _, _ in ready + todo:
        d = done.get(it["ckey"])
        if d:
            rows.append(dict({k: v for k, v in it.items() if k != "ckey"}, **d["answer"]))
    (OUT / "judge.json").write_text(json.dumps(dict(model=MODEL, spent=spent(log), rows=rows), ensure_ascii=False,
                                               indent=1))
    print(f"{len(rows)} verdicts -> {OUT / 'judge.json'}; spent ${spent(log):.3f}")


if __name__ == "__main__":
    main()
