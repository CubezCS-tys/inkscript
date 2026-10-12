"""Experiment 36: a Gemini judge for tables and equations (prepared; run only after the owner approves the cost).

    PYTHONPATH=<worktree>/src /home/yassine/inkscript/.venv/bin/python judge.py estimate [--readers a,b]
    ... judge.py run --limit 3 [--readers a,b] [--kind table|equation]    # a 3-call test
    ... judge.py run [--readers a,b]                                        # everything (needs the owner's go-ahead)

One request per table or equation of a yardstick page (the gold file's regions, boxes in the pack's pixels): the scan
crop (box + 3% margin, JPEG) and every reader's version of that object, anonymised as A, B, C... in a shuffled order
fixed by a seed (a model must not know whose version it reads). Readers' objects are matched to the page's by box
overlap (IoU >= 0.2), else by order. The answer, per candidate: structure right? (rows/columns/merged cells, or
the formula's layout), wrong / missing / extra cells (or symbols), a 1-5 grade and a short note.

Discipline (experiment 34's gem.py, with this experiment's limits): every answer cached by a hash of model + prompt +
image (out/gemini_cache.jsonl: a rerun pays nothing); every call's tokens and cost appended to out/gemini_spend.jsonl
at list price rounded up (enrich/judge.py PRICE); no call sent that would take this experiment's logged total over
CAP = $3; max_output_tokens capped; a truncated answer (MAX_TOKENS, or JSON that does not parse) is logged and kept
as a failure, never retried. gem.py itself is not imported because it retries on any failure, truncation included.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import cv2

from inkscript.enrich.judge import PRICE, _key

OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")
GOLD = Path("/home/yassine/inkscript/experiments/34_yardstick/out/gold")
CACHE, SPEND = OUT / "gemini_cache.jsonl", OUT / "gemini_spend.jsonl"
CAP = 3.0
MODEL = "gemini-3.1-pro-preview"
MAX_OUT = {"table": 6000, "equation": 3000}       # answer + thinking (thinking level low)
MAN = {p["page_id"]: p for p in json.load(open(OUT / "pack" / "manifest.json"))["pages"]}

PROMPT = {
    "table": """Image 1 is a crop of a scanned Arabic journal page holding one table. Below are {n} transcriptions of
that table as HTML, labelled {labels}, made by different OCR systems. Judge each one against the image only.
For each candidate report:
- structure_ok: true if its rows, columns and merged cells (rowspan/colspan) match the printed table;
- cells_wrong: number of cells whose text differs from the print (a wrong digit, letter, vowel mark or word counts);
- cells_missing: printed cells it leaves out; cells_extra: cells it has that the print does not (invented text);
- grade: 1 (unusable) to 5 (exact);
- note: at most 15 words on the worst problem.
Count Arabic-Indic and Western digits as the same digit; judge the text as printed, not a translation.
{cands}""",
    "equation": """Image 1 is a crop of a scanned Arabic journal page holding one displayed formula (Arabic words may
appear inside it). Below are {n} transcriptions of it as LaTeX, labelled {labels}, made by different OCR systems.
Judge each one against the image only, as the formula would render.
For each candidate report:
- structure_ok: true if fractions, sub/superscripts, roots, sums, matrices and the order of terms match the print;
- cells_wrong: number of symbols, digits or words that differ from the print;
- cells_missing: printed symbols/terms it leaves out; cells_extra: symbols/terms it adds that are not printed;
- grade: 1 (unusable) to 5 (exact);
- note: at most 15 words on the worst problem.
Count Arabic-Indic and Western digits as the same digit.
{cands}""",
}
SCHEMA = {"type": "object", "properties": {"verdicts": {"type": "array", "items": {
    "type": "object", "properties": {
        "label": {"type": "string"}, "structure_ok": {"type": "boolean"}, "cells_wrong": {"type": "integer"},
        "cells_missing": {"type": "integer"}, "cells_extra": {"type": "integer"}, "grade": {"type": "integer"},
        "note": {"type": "string"}},
    "required": ["label", "structure_ok", "cells_wrong", "cells_missing", "cells_extra", "grade", "note"]}}},
    "required": ["verdicts"]}


def spent() -> float:
    if not SPEND.exists():
        return 0.0
    return sum(json.loads(l)["usd"] for l in SPEND.read_text().splitlines() if l.strip())


def _cache() -> dict:
    c = {}
    if CACHE.exists():
        for l in CACHE.read_text(encoding="utf-8").splitlines():
            if l.strip():
                d = json.loads(l)
                c[d["key"]] = d["answer"]
    return c


def _iou(a, b) -> float:
    if not a or not b:
        return 0.0
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - ix * iy
    return ix * iy / u if u > 0 else 0.0


def items(readers: list[str], kinds=("table", "equation")) -> list[dict]:
    """Every gold-file table/equation with each reader's matched version."""
    out = []
    for pid, p in sorted(MAN.items()):
        if p["kind"] != "yardstick" or not (GOLD / f"{pid}.json").exists():
            continue
        g = json.loads((GOLD / f"{pid}.json").read_text(encoding="utf-8"))
        for kind, key, field in (("table", "tables", "html"), ("equation", "equations", "latex")):
            if kind not in kinds:
                continue
            objs = g.get(key, [])
            for k, o in enumerate(objs):
                cands = {}
                for r in readers:
                    f = OUT / "pred" / r / f"{pid}.json"
                    if not f.exists():
                        continue
                    po = json.loads(f.read_text(encoding="utf-8")).get(key, [])
                    best = max(po, key=lambda x: _iou(x.get("box"), o.get("box")), default=None)
                    if best is not None and _iou(best.get("box"), o.get("box")) < 0.2:
                        best = po[k] if k < len(po) and not po[k].get("box") else None
                    cands[r] = (best or {}).get(field, "")
                out.append(dict(page_id=pid, kind=kind, id=o.get("id", f"{kind}{k}"), box=o["box"], cands=cands,
                                split=p["split"]))
    return out


def crop(pid: str, box) -> bytes:
    im = cv2.imread(str(GOLD / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE)
    H, W = im.shape
    m = 0.03 * max(W, H)
    x0, y0 = max(0, int(box[0] - m)), max(0, int(box[1] - m))
    x1, y1 = min(W, int(box[2] + m)), min(H, int(box[3] + m))
    ok, buf = cv2.imencode(".jpg", im[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def build(it: dict, seed: int = 36):
    rs = sorted(it["cands"])
    random.Random(f"{seed}:{it['page_id']}:{it['id']}").shuffle(rs)
    labels = [chr(65 + i) for i in range(len(rs))]
    tag = "HTML" if it["kind"] == "table" else "LaTeX"
    cands = "\n\n".join(f"Candidate {l} ({tag}):\n{it['cands'][r] or '(nothing: this system gave no ' + it['kind'] + ')'}"
                        for l, r in zip(labels, rs))
    prompt = PROMPT[it["kind"]].format(n=len(rs), labels=", ".join(labels), cands=cands)
    return prompt, dict(zip(labels, rs))


def estimate_usd(prompt: str, kind: str) -> tuple[float, float]:
    pin, pout = PRICE[MODEL]
    tin = 1120 + len(prompt) / 2.5          # a high-resolution image ~1,120 tokens; Arabic/HTML ~2.5 chars a token
    tout = {"table": 2500, "equation": 1200}[kind]      # expected answer + low thinking (the cap is MAX_OUT)
    return tin / 1e6 * pin + tout / 1e6 * pout, (tin / 1e6 * pin + MAX_OUT[kind] / 1e6 * pout)


def call(prompt: str, image: bytes, kind: str, tag: str):
    key = hashlib.sha256((MODEL + "\0" + prompt + "\0high").encode() + hashlib.sha256(image).digest()).hexdigest()
    c = _cache()
    if key in c:
        return c[key], 0.0
    _, worst = estimate_usd(prompt, kind)
    if spent() + worst > CAP:
        print(f"STOP: spent ${spent():.3f}; this call (up to ${worst:.3f}) could cross the ${CAP} cap", flush=True)
        return None, 0.0
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=_key())
    parts = [types.Part(text="Image 1:"),
             types.Part(inline_data=types.Blob(data=image, mime_type="image/jpeg"),
                        media_resolution=types.PartMediaResolution(level=types.PartMediaResolutionLevel.MEDIA_RESOLUTION_HIGH)),
             types.Part(text=prompt)]
    cfg = types.GenerateContentConfig(temperature=0.0, max_output_tokens=MAX_OUT[kind], response_mime_type="application/json",
                                      response_schema=SCHEMA, thinking_config=types.ThinkingConfig(thinking_level="low"))
    try:
        r = client.models.generate_content(model=MODEL, contents=[types.Content(role="user", parts=parts)], config=cfg)
    except Exception as e:          # nothing came back, nothing was billed for an answer: report, do not retry
        print("  request failed:", type(e).__name__, str(e)[:200], flush=True)
        return None, 0.0
    um = r.usage_metadata
    pin, pout = PRICE[MODEL]
    tin = um.prompt_token_count or 0
    tout = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
    usd = tin / 1e6 * pin + tout / 1e6 * pout
    fin = str(r.candidates[0].finish_reason) if r.candidates else "none"
    with open(SPEND, "a") as f:
        f.write(json.dumps(dict(when=time.strftime("%Y-%m-%d %H:%M:%S"), model=MODEL, tag=tag, kind=kind, tin=tin,
                                tout=tout, usd=usd, finish=fin, total=round(spent() + usd, 4))) + "\n")
    try:
        ans = json.loads(r.text)
    except Exception:
        print(f"  truncated or unparsable answer ({fin}): kept as a failure, not retried", flush=True)
        return None, usd
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(key=key, tag=tag, model=MODEL, answer=ans), ensure_ascii=False) + "\n")
    return ans, usd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=("estimate", "run"))
    ap.add_argument("--readers", default="")
    ap.add_argument("--kind", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--simulate", type=int, default=0, help="estimate only: N readers each as long as the draft")
    a = ap.parse_args()
    readers = [r for r in a.readers.split(",") if r] or sorted(
        d.name for d in (OUT / "pred").iterdir() if d.is_dir() and not d.name.endswith(".kl")
        and d.name not in ("azure", "kraken", "synth_azure"))
    its = items(readers, (a.kind,) if a.kind else ("table", "equation"))
    if a.simulate:      # before the VLMs land: every candidate as long as the gold file's draft of the object
        for it in its:
            g = json.loads((GOLD / f"{it['page_id']}.json").read_text(encoding="utf-8"))
            o = next(x for x in g["tables" if it["kind"] == "table" else "equations"] if x.get("id", "") == it["id"])
            d = o.get("html") or o.get("draft_html") or o.get("latex") or o.get("draft_latex") or ""
            it["cands"] = {f"r{i}": d for i in range(a.simulate)}
    if a.what == "estimate":
        tot = worst = 0.0
        by = {}
        for it in its:
            p, _ = build(it)
            e, w = estimate_usd(p, it["kind"])
            tot += e; worst += w
            by.setdefault(it["kind"], [0, 0.0]); by[it["kind"]][0] += 1; by[it["kind"]][1] += e
        print(json.dumps(dict(readers=readers, items=len(its), by_kind=by, expected_usd=round(tot, 2),
                              worst_case_usd=round(worst, 2), spent_so_far=round(spent(), 3), cap=CAP), indent=1))
        return
    res_f = OUT / "judge.jsonl"
    n = 0
    for it in its:
        if a.limit and n >= a.limit:
            break
        prompt, labmap = build(it)
        ans, usd = call(prompt, crop(it["page_id"], it["box"]), it["kind"], f"{it['page_id']}:{it['id']}")
        n += 1
        row = dict(page_id=it["page_id"], id=it["id"], kind=it["kind"], split=it["split"], labels=labmap, usd=usd,
                   verdicts={labmap.get(v["label"], v["label"]): v for v in (ans or {}).get("verdicts", [])} if ans else None)
        with open(res_f, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(it["page_id"], it["id"], f"${usd:.4f}", "ok" if ans else "FAILED", flush=True)
    print(f"spent in total ${spent():.3f} of ${CAP}")


if __name__ == "__main__":
    main()
