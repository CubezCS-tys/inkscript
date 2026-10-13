"""The fine-tuned layout model on the 44 test pages, against the Pro referee (out/score_test, the same label set the
model was trained on), next to dots.mocr and the rules on the same lines. Each Azure line takes the class of the
predicted box that covers most of it (at least 40% of the line); none -> "none".
Reads out/gpu/predictions.json; writes out/score_yolo.json."""
import json, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "38_parser"))
from score_layout import LABELS
MAP = {"Text": "body", "Title": "heading", "Section-header": "heading", "List-item": "list", "Footnote": "footnote",
       "Page-header": "furniture", "Page-footer": "furniture", "Caption": "caption", "Table": "table", "Formula": "equation",
       "Picture": "other"}                                                           # as in score_model.py
P = {p["page_id"]: p["primary"] for p in json.load(open(HERE.parent / "38_parser/out/pages.json"))["pages"]}
GROUP = {"body": "plain text", "footnotes": "plain text", "latin": "plain text", "vowelled": "plain text", "quran": "plain text",
         "magazine": "columns", "decorative": "decorative", "table": "tables", "equation": "equations"}
from common import dots_blocks, inter, area, page_image

pred = json.load(open(HERE / "out/gpu/predictions.json"))
rows = []
for f in sorted((HERE / "out/score_test").glob("*.json")):
    r = json.load(open(f)); pid = r["pid"]; p = pred.get(pid)
    if not p: print("no prediction for", pid); continue
    H, W = page_image(pid).shape[:2]; B = [([b[0] * W, b[1] * H, b[2] * W, b[3] * H], LABELS[c], s) for b, c, s in zip(p["boxes"], p["cls"], p["conf"])]
    D = dots_blocks(pid)
    for x in r["lines"]:
        a = max(1, area(x["box"]))
        cand = [(inter(b, x["box"]) / a * s, c) for b, c, s in B if inter(b, x["box"]) / a >= 0.4]
        yolo = max(cand)[1] if cand else "none"
        bd = max(D, key=lambda b: inter(b["box"], x["box"]), default=None)
        dots = MAP.get(bd["cat"], "other") if bd and inter(bd["box"], x["box"]) / a > 0.3 else "none"
        rows.append(dict(pid=pid, group=GROUP[P[pid]], ref=x["ref"], rules=x["ours_m"], dots=dots, model=yolo, text=x["text"], box=x["box"]))
M = ("rules", "dots", "model"); out = {}
R = [x for x in rows if x["ref"] not in (None, "other")]
out["all"] = dict(n=len(R), **{m: round(sum(x[m] == x["ref"] for x in R) / len(R), 3) for m in M})
print("all lines", out["all"])
for g in sorted({x["group"] for x in R}):
    G = [x for x in R if x["group"] == g]; out[g] = dict(n=len(G), **{m: round(sum(x[m] == x["ref"] for x in G) / len(G), 3) for m in M}); print(f"  {g:12}", out[g])
for lab in LABELS:
    T = [x for x in R if x["ref"] == lab]
    if not T: continue
    out["label " + lab] = dict(n=len(T), **{m: round(sum(x[m] == lab for x in T) / len(T), 3) for m in M},
                               **{m + "_right_when_said": round(sum(x[m] == lab and x["ref"] == lab for x in R) / max(1, sum(x[m] == lab for x in R)), 3) for m in M})
    print(f"  {lab:10}", out["label " + lab])
print("model's misses", Counter((x["ref"], x["model"]) for x in R if x["ref"] != x["model"]).most_common(12))
json.dump(dict(scores=out, rows=rows), open(HERE / "out/score_yolo.json", "w"), ensure_ascii=False)
