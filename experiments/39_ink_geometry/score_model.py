"""How much does a small model add? dots.mocr's own block types (experiment 36's run, already paid for) given to each
Azure line (the block covering most of the line), scored against the same Gemini referee as the rules, plus simple
combinations of the two. Reads out/score/*.json; writes out/score_model.json. No spend."""
import json, glob, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "38_parser")); from common import dots_blocks, inter, area
MAP = {"Text": "body", "Title": "heading", "Section-header": "heading", "List-item": "list", "Footnote": "footnote",
       "Page-header": "furniture", "Page-footer": "furniture", "Caption": "caption", "Table": "table", "Formula": "equation",
       "Picture": "other"}
SCOPE = {"body", "heading", "footnote", "furniture", "list", "verse"}
ALL = SCOPE | {"caption", "table", "equation"}
P = {p["page_id"]: p["primary"] for p in json.load(open(HERE.parent / "38_parser/out/pages.json"))["pages"]}
GROUP = {"body": "plain text", "footnotes": "plain text", "latin": "plain text", "vowelled": "plain text", "quran": "plain text",
         "magazine": "columns", "decorative": "decorative", "table": "tables", "equation": "equations"}
cats = Counter(); rows = []
for f in sorted(glob.glob(str(HERE / "out/score/*.json"))):
    r = json.load(open(f)); B = dots_blocks(r["pid"])
    for b in B: cats[b["cat"]] += 1
    for x in r["lines"]:
        best = max(B, key=lambda b: inter(b["box"], x["box"]), default=None)
        cov = inter(best["box"], x["box"]) / max(1, area(x["box"])) if best else 0
        x["dots"] = MAP.get(best["cat"], "other") if best and cov > 0.3 else "none"
        # one combination: the model names the block, the rules add what the model has no word for (verse) and
        # footnotes the model called plain text when the rules found the rule above / the matching number
        x["combo"] = "verse" if x["ours_m"] == "verse" and x["dots"] == "body" else x["dots"]
        rows.append(dict(pid=r["pid"], group=GROUP[P[r["pid"]]], ref=x["ref"], rules=x["ours_m"], dots=x["dots"], combo=x["combo"]))
print("dots categories:", dict(cats))
out = {}
for name, scope in (("lines the rules handle", SCOPE), ("all labelled lines", ALL)):
    R = [x for x in rows if x["ref"] in scope]
    res = {m: round(sum(x[m] == x["ref"] for x in R) / len(R), 3) for m in ("rules", "dots", "combo")}
    print(f"{name} ({len(R)}):", res); out[name] = dict(n=len(R), **res)
    for g in sorted({x["group"] for x in R}):
        G = [x for x in R if x["group"] == g]
        res = {m: round(sum(x[m] == x["ref"] for x in G) / len(G), 2) for m in ("rules", "dots", "combo")}
        print(f"   {g:12} ({len(G)}):", res); out[f"{name} / {g}"] = dict(n=len(G), **res)
R = [x for x in rows if x["ref"] in ALL]
for lab in sorted(ALL):
    T = [x for x in R if x["ref"] == lab]
    rec = {m: round(sum(x[m] == lab for x in T) / max(1, len(T)), 2) for m in ("rules", "dots")}
    prec = {m: round(sum(x[m] == lab and x["ref"] == lab for x in R) / max(1, sum(x[m] == lab for x in R)), 2) for m in ("rules", "dots")}
    print(f"   {lab:10} n={len(T):4} found rules {rec['rules']:.0%} dots {rec['dots']:.0%} | right when said: rules {prec['rules']:.0%} dots {prec['dots']:.0%}")
    out[f"label {lab}"] = dict(n=len(T), found=rec, right_when_said=prec)
print("dots disagreements:", Counter((x["ref"], x["dots"]) for x in R if x["ref"] != x["dots"]).most_common(12))
json.dump(out, open(HERE / "out/score_model.json", "w"), indent=1)
