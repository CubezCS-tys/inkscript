"""Experiment 77: a local HTML page of the results with real crops (out/report77.html; private data, never published).

    python report77.py
Reads out/results77.json, out/confusions77.json, out/judge/*, out/test/*, out/pred/*.
"""
from __future__ import annotations

import base64
import html
import json
import tarfile
from collections import Counter
from pathlib import Path

from common77 import OUT

T = tarfile.open(OUT / "test/test-0-000.tar")
NAMES = set(T.getnames())


def img(key: str, judge: bool = False) -> str:
    if judge:
        f = OUT / "judge/crops" / f"{key}.png"
        if not f.exists():
            return ""
        b, mime = f.read_bytes(), "image/png"
    else:
        if key + ".jpg" not in NAMES:
            return ""
        b, mime = T.extractfile(key + ".jpg").read(), "image/jpeg"
    return f'<img src="data:{mime};base64,{base64.b64encode(b).decode()}">'


def esc(s):
    return html.escape(s or "")


def table(R: dict, title: str) -> str:
    rows = sorted(R.items(), key=lambda kv: kv[1]["letters"] if kv[1]["letters"] is not None else 999)
    h = [f"<h3>{esc(title)}</h3><table><tr><th>reader</th><th>letters wrong %</th><th>words wrong % (order-free)</th>"
         "<th>≈ words wrong</th><th>letters % with punctuation</th><th>words % with punctuation</th>"
         "<th>space before punctuation (reader / truth)</th></tr>"]
    for n, v in rows:
        h.append(f"<tr><td>{esc(n)}</td><td>{v['letters']:.2f}</td><td>{v['words']:.2f}</td><td>{v['word_errors_approx']}</td>"
                 f"<td>{v['letters_punct']:.2f}</td><td>{v['words_punct']:.2f}</td>"
                 f"<td>{v['space_before_punct']['reader']} / {v['space_before_punct']['truth']}</td></tr>")
    return "".join(h) + "</table>"


def main():
    res = json.loads((OUT / "results77.json").read_text(encoding="utf-8"))
    conf = json.loads((OUT / "confusions77.json").read_text(encoding="utf-8"))
    parts = ["""<!doctype html><html lang="en"><meta charset="utf-8"><title>Scratch reader</title>
<style>:root{--bg:#fbfaf7;--fg:#222;--mut:#666;--line:#ddd}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:auto;padding:16px}
table{border-collapse:collapse;margin:8px 0 20px}td,th{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left}
.ar{direction:rtl;font-family:'Scheherazade New','Noto Naskh Arabic',serif;font-size:20px}
img{max-width:100%;border:1px solid var(--line)}.mut{color:var(--mut)}</style>
<h1>Experiment 77: our own line reader, from scratch</h1>
<p class="mut">Private Mandumah pages: local file only. Segmentation = Azure's line boxes for every reader
(this tests reading, not layout).</p>"""]
    names = {"yardstick": "Owner's 20 checked pages (yardstick)", "lab_docs12": "Lab documents 1 + 2 (rev1)",
             "lab_doc1": "Lab document 1", "lab_doc2": "Lab document 2", "doc3_vs_argon": "Document 3: disagreement with Argon (no truth)"}
    for s in ("yardstick", "lab_docs12", "lab_doc1", "lab_doc2", "doc3_vs_argon"):
        if s in res["sets"]:
            parts.append(table(res["sets"][s], names[s]))
    for model in [m for m in conf if m.endswith(":letters") and not m.startswith("azure")][:1] + ["azure:letters"]:
        parts.append(f"<h2>Most common confusions: {esc(model)} (yardstick lines, as printed)</h2>")
        for c in conf[model][:10]:
            ex = c["example"]
            parts.append(f"<p><b>{esc(c['pair'])}</b> × {c['count']}<br>{img(ex['key'])}<br>"
                         f"<span class=ar>truth: {esc(ex['truth'])}</span><br><span class=ar>{esc(model)}: {esc(ex['reader'])}</span></p>")
    jf = OUT / "judge/answers.jsonl"
    if jf.exists():
        A = [json.loads(l) for l in open(jf, encoding="utf-8")]
        S = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "judge/sample.jsonl", encoding="utf-8")}
        parts.append(f"<h2>Gemini's verdicts on v1-vs-Azure disputes</h2><p>{dict(Counter(a['winner'] for a in A))}</p>")
        for w in ("v1", "azure", "neither", "unreadable"):
            ex = [a for a in A if a["winner"] == w][:4]
            for a in ex:
                s = S[a["key"]]
                parts.append(f"<p><b>{w}</b> {img(a['key'], True)}<br><span class=ar>Azure: {esc(s['azure'])}</span><br>"
                             f"<span class=ar>v1: {esc(s['v1'])}</span><br><span class=ar>Gemini: {esc(a.get('reading'))}</span>"
                             f"<br><span class=mut>{esc(a.get('note'))}</span></p>")
    (OUT / "report77.html").write_text("\n".join(parts), encoding="utf-8")
    print(OUT / "report77.html")


if __name__ == "__main__":
    main()
