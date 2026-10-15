"""Approach A: word-level differences between a variant's text and the owner's gold, punctuation-only ones left out.
    python A_golddiff.py VARIANT  -> out/A_oneshot/<VARIANT>/golddiff.txt"""
import json, difflib, sys, re
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from score import blocks_of
from common import sample
P = re.compile(r'[^\w؀-ۿ]|[ـ،؛؟۔]')
v = sys.argv[1]
out = []
for p in sample()["pages"]:
    if p["truth"] != "gold":
        continue
    pid = p["page_id"]
    g = json.load(open(p["truth_file"]))
    order = {i: k for k, i in enumerate(g["order"])} if isinstance(g["order"], list) and g["order"] and isinstance(g["order"][0], str) else {}
    lines = sorted(g["lines"], key=lambda l: order.get(l["id"], 999))
    gw = " ".join(l["text"] for l in lines).split()
    pw = " ".join(x["text"] for x in blocks_of((HERE / f"out/A_oneshot/{v}/{pid}.html").read_text())).split()
    cl = lambda ws: [P.sub("", w) for w in ws if P.sub("", w)]
    gw, pw = cl(gw), cl(pw)
    sm = difflib.SequenceMatcher(None, gw, pw, autojunk=False)
    out.append(f"== {pid} ({len(gw)} gold words)")
    for op, a1, a2, b1, b2 in sm.get_opcodes():
        if op != "equal" and (a2 - a1) + (b2 - b1) < 12:
            out.append(f"  {op:7} gold: {' '.join(gw[a1:a2])}  |  gemini: {' '.join(pw[b1:b2])}")
(HERE / f"out/A_oneshot/{v}/golddiff.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))
