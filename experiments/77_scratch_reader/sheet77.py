"""A sheet of judged line crops (Azure / v1 / Gemini's verdict) as HTML, rendered to PNG by shot77.py."""
import base64
import html
import json
import random

from common77 import OUT

J = OUT / "judge"
S = {json.loads(l)["key"]: json.loads(l) for l in open(J / "sample.jsonl", encoding="utf-8")}
A = [json.loads(l) for l in open(J / "answers.jsonl", encoding="utf-8")]
rng = random.Random(5)
pick = []
for w, n in (("v1", 4), ("azure", 3), ("neither", 2), ("unreadable", 1)):
    c = [a for a in A if a["winner"] == w and len(S[a["key"]]["azure"]) < 90]
    pick += rng.sample(c, min(n, len(c)))
e = html.escape
rows = []
lab = {"v1": "v1 right", "azure": "Azure right", "neither": "both wrong", "unreadable": "unreadable"}
for a in pick:
    s = S[a["key"]]
    b64 = base64.b64encode((J / "crops" / f"{a['key']}.png").read_bytes()).decode()
    g = f'<div class=r><span class=k>Gemini:</span> <span class=ar>{e(a["reading"])}</span></div>' if a["reading"] else ""
    rows.append(f'<div class=card><div class=v>{lab[a["winner"]]}</div><img src="data:image/png;base64,{b64}">'
                f'<div class=r><span class=k>Azure:</span> <span class=ar>{e(s["azure"])}</span></div>'
                f'<div class=r><span class=k>v1:</span> <span class=ar>{e(s["v1"])}</span></div>{g}</div>')
page = f"""<!doctype html><meta charset="utf-8"><style>
body{{background:#fbfaf7;color:#222;font:14px system-ui;padding:16px;width:960px}}
.card{{border-bottom:1px solid #ddd;padding:8px 0}}img{{max-width:100%;display:block;margin:4px 0}}
.v{{font-weight:600;color:#2a6f97}}.k{{color:#666;display:inline-block;width:56px}}
.ar{{font-family:'Noto Naskh Arabic','Scheherazade New',serif;font-size:19px;unicode-bidi:plaintext}}
.r{{direction:ltr}}</style>
<h2>Exp 77: where our v1 and Azure disagree, Gemini looks at the line</h2>
<p>Real lines from training pages (never test pages). Gemini saw the image and both readings in random order.</p>
{''.join(rows)}"""
(OUT / "look/judge_sheet.html").write_text(page, encoding="utf-8")
print(OUT / "look/judge_sheet.html")
