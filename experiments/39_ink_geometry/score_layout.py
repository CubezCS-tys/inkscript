"""The frozen line labeller (senses.py, rules as committed in 0f0ff0a, not tuned since) on experiment 38's 44 pages,
scored against an independent referee: Gemini looks at the page with every Azure line boxed and numbered and labels
each line, without seeing our rules or labels. Per page -> out/score/<pid>.json (skipped if present), then a summary.
Gemini spend is logged in out/gemini_spend.jsonl; the whole experiment is capped at $15 (the owner has ~£20 of Gemini credit).
REFEREE=<model> picks another referee (answers in out/score_<model>/)."""
import json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import cv2, numpy as np
import os
MODEL = os.environ.get("REFEREE", "gemini-3.1-pro-preview")
HERE = Path(__file__).parent; OUT = HERE / os.environ.get("SCORE_DIR", "out/score" if MODEL == "gemini-3.1-pro-preview" else f"out/score_{MODEL}"); OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE.parent / "38_parser")); sys.path.insert(0, str(HERE))
import common
common.SPEND = HERE / "out/gemini_spend.jsonl"; common.CACHE = HERE / "out/gemini_cache.jsonl"; common.CAP = 15.0; common._cache = None
from common import gemini, jpeg
from senses import label

LABELS = ["furniture", "heading", "body", "list", "verse", "footnote", "references", "caption", "table", "equation", "other"]
OURS = {"paragraph start": "body", "body": "body", "bullet": "list", "bullet, continued": "list"}
PROMPT = """This is a scanned page from an Arabic academic journal. Every text line found by the OCR is boxed and numbered
in red (the number sits just to the right of its box). Label every numbered line with exactly one of:
- furniture: running header, page number, journal name or footer repeated on pages; not content
- heading: a title or section heading (including numbered ones like "٦ ـ ...")
- body: ordinary paragraph text (including a paragraph's first and last line)
- list: a line that belongs to a bulleted or numbered list item (the item's first line and its continuation lines)
- verse: a line of poetry (often two half-verses separated by a gap)
- footnote: a note at the foot of the page, usually below a short rule, often in smaller type
- references: a line of a bibliography, reference list or endnotes section (e.g. under "المراجع" or "الهوامش")
- caption: a caption of a figure or table
- table: a line or cell inside a table
- equation: a mathematical formula
- other: anything else (stamps, handwriting, decoration)
Judge by how the page looks, the way a careful reader would. Return JSON: {"lines": [{"n": <number>, "label": "<label>"}]}
covering every number from 1 to %d."""
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
    "n": {"type": "integer"}, "label": {"type": "string", "enum": LABELS}}, "required": ["n", "label"]}}}, "required": ["lines"]}


def numbered(gray, L):
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR); img = cv2.copyMakeBorder(img, 0, 0, 0, 200, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    for n, l in enumerate(L, 1):
        x0, y0, x1, y1 = (int(round(v)) for v in l["box"])
        cv2.rectangle(img, (x0 - 4, y0), (x1 + 4, y1), (0, 0, 230), 2)
        cv2.putText(img, str(n), (x1 + 10, int((y0 + y1) / 2) + 12), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 230), 3)
    return img


def one(pid):
    f = OUT / f"{pid}.json"
    if f.exists(): return json.loads(f.read_text())
    try:
        gray, L = label(pid)
    except Exception as e:
        r = dict(pid=pid, error=f"labeller failed: {type(e).__name__}: {e}"); f.write_text(json.dumps(r)); return r
    img = numbered(gray, L); cv2.imwrite(str(OUT / f"{pid}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    ans, usd = gemini(PROMPT % len(L), [jpeg(img, max_side=2600, quality=88)], f"layout-referee {pid}",
                      model=MODEL, max_out=12000, schema=SCHEMA, thinking="low", est_in=3000)
    if not ans: return dict(pid=pid, error="no referee answer")         # not saved: a rerun retries it
    ref = {a["n"]: a["label"] for a in ans["lines"]}
    rows = [dict(n=n, id=l["id"], text=l["text"], box=l["box"], ours=l["label"], ours_m=OURS.get(l["label"], l["label"]),
                 ref=ref.get(n), why=l["why"]) for n, l in enumerate(L, 1)]
    r = dict(pid=pid, lines=rows, usd=usd); f.write_text(json.dumps(r, ensure_ascii=False, indent=1)); return r


if __name__ == "__main__":
    P = [p["page_id"] for p in json.load(open(HERE.parent / "38_parser/out/pages.json"))["pages"]]
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(one, P):
            if "error" in r: print(r["pid"], r["error"], flush=True)
            else:
                ok = sum(x["ours_m"] == x["ref"] for x in r["lines"]); print(r["pid"], f"{ok}/{len(r['lines'])} agree", flush=True)
    print("spent", round(common.spent(), 3))
