"""Experiment 58: Indra against Azure + Gemini on the 3,404 pages, split by script (Arabic / Latin) and decade.
No truth here: text = how far Indra's words are from Azure's (folded word bags, 1 - F1; Azure itself is ~1.2-1.8%
wrong on truth pages); layout = coarse role agreement and footnote recall vs Gemini, as in score58_layout.py.

    /home/appuser/inkscript/.venv/bin/python bylang58.py   -> out/bylang.json
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
from inkscript.gold.text import folded
HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from hybrid58 import ok, G2C, I2C  # noqa: E402
arts = {a["stem"]: a for a in json.loads((E / "43_rehearsal/sample43b.json").read_text())["articles"]}
AR = re.compile("[؀-ۿ]")
LA = re.compile("[A-Za-zÀ-ɏ]")
agg = defaultdict(Counter)
for line in open(OUT / "layout_lines.jsonl", encoding="utf-8"):
    pg = json.loads(line)
    txt = " ".join(l["t"] for l in pg["lines"])
    ar, la = len(AR.findall(txt)), len(LA.findall(txt))
    if ar + la < 50:
        continue
    script = "Arabic" if ar > 0.7 * (ar + la) else "Latin" if la > 0.7 * (ar + la) else "mixed"
    dec = arts[pg["id"].rsplit("_p", 1)[0]].get("decade") or "?"
    ind = json.loads((OUT / "indra/lay300" / f"{pg['id']}.json").read_text())
    a = Counter(folded(txt).split())
    b = Counter(folded(" ".join(l["text"] for l in ind["lines"])).split())
    m = sum((a & b).values())
    for key in (("script", script), ("decade", dec), ("all", "all")):
        c = agg[key]
        c["pages"] += 1
        c["w_err"] += sum(a.values()) + sum(b.values()) - 2 * m
        c["w_n"] += sum(a.values()) + sum(b.values())
        for l in pg["lines"]:
            if l["g"] == "noise":
                continue
            c["lines"] += 1
            c["agree"] += ok(l["g"], l["lab"])
            if G2C.get(l["g"]) == "footnote":
                c["fn"] += 1
                c["fn_hit"] += I2C.get(l["lab"]) == "footnote"
            if G2C.get(l["g"]) == "heading":
                c["hd"] += 1
                c["hd_hit"] += I2C.get(l["lab"]) == "heading"
res = {}
for (k, v), c in sorted(agg.items()):
    res[f"{k}={v}"] = dict(pages=c["pages"], indra_vs_azure_words=round(c["w_err"] / max(c["w_n"], 1), 4),
                           role_agree=round(c["agree"] / max(c["lines"], 1), 4),
                           footnote_recall=round(c["fn_hit"] / max(c["fn"], 1), 3) if c["fn"] else None,
                           heading_recall=round(c["hd_hit"] / max(c["hd"], 1), 3) if c["hd"] else None)
(OUT / "bylang.json").write_text(json.dumps(res, indent=1))
for k, v in res.items():
    print(f"{k:16s} {v}")
