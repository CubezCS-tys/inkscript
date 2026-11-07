"""Experiment 83: one picture for the owner -> out/look/v3_scored.html (render: experiment 77's shot77.py -> PNG).

Left: letters and words wrong (punctuation and spacing excluded) on the owner's 20 held-out pages, Azure / v1 / v3
(/ v4 when scored).  Right: how often v1 and Azure read a new line the same way, by decade (those became labels).
    python3 fig83.py [results83.json] [agree_v3.json] [GPU_SPENT]
    52_journal_gate1/out/pwvenv/bin/python 77_scratch_reader/shot77.py out/look/v3_scored.html out/look/v3_scored.png 1100
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
res = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "out/results83.json").read_text())
agr = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else HERE / "out/host/agree_v3.json").read_text())
Y, L = res["sets"]["yardstick"], res["sets"]["lab_docs12"]
readers = [r for r in ("azure", "v1", "v3", "v4") if r in Y]
names = {"azure": "Azure", "v1": "our v1", "v3": "our v3", "v4": "our v4"}
sub = {"azure": "", "v1": "0.5M lines", "v3": "2.5M lines", "v4": "2.5M + relabel"}
col = {"azure": "#8a8984", "v1": "#2a78d6", "v3": "#eb6834", "v4": "#1baf7a"}


def bars(title, S, metric, w=300, h=230):
    v = [S[r][metric] for r in readers]
    top = max(v) * 1.25
    bw, gap, x0, base = 50, 28, 20, h - 50
    out = [f'<svg width="{w}" height="{h}"><text x="0" y="16" class="t">{title}</text>']
    for i, (r, x) in enumerate(zip(readers, v)):
        bx = x0 + i * (bw + gap)
        bh = (base - 30) * x / top
        out.append(f'<rect x="{bx}" y="{base - bh:.1f}" width="{bw}" height="{bh:.1f}" rx="4" fill="{col[r]}"/>')
        out.append(f'<text x="{bx + bw / 2}" y="{base - bh - 6:.1f}" class="v" text-anchor="middle">{x:.2f}</text>')
        out.append(f'<text x="{bx + bw / 2}" y="{base + 16}" class="l" text-anchor="middle">{names[r]}</text>')
        out.append(f'<text x="{bx + bw / 2}" y="{base + 30}" class="s" text-anchor="middle">{sub[r]}</text>')
    out.append(f'<line x1="10" x2="{w - 10}" y1="{base}" y2="{base}" stroke="#c9c8c2"/></svg>')
    return "".join(out)


dec = sorted((int(k.split(":")[1]), v["agree_pct"]) for k, v in agr.items()
             if k.startswith("decade:") and k != "decade:None")
w, h, base = 460, 230, 180
ag = [f'<svg width="{w}" height="{h}"><text x="0" y="16" class="t">new lines where v1 = Azure (trained on), %</text>']
for i, (d, p) in enumerate(dec):
    bx = 10 + i * 40
    bh = 140 * p / 100
    ag.append(f'<rect x="{bx}" y="{base - bh:.1f}" width="30" height="{bh:.1f}" rx="4" fill="#4a3aa7"/>')
    ag.append(f'<text x="{bx + 15}" y="{base - bh - 5:.1f}" class="v2" text-anchor="middle">{p:.0f}</text>')
    ag.append(f'<text x="{bx + 15}" y="{base + 15}" class="s" text-anchor="middle">{d}s</text>')
ag.append(f'<line x1="5" x2="{w - 10}" y1="{base}" y2="{base}" stroke="#c9c8c2"/></svg>')

html = f"""<!doctype html><meta charset="utf-8"><title>Experiment 83</title>
<style>
body{{background:#fcfcfb;color:#0b0b0b;font:14px system-ui,sans-serif;margin:24px}}
h1{{font-size:19px;font-weight:600;margin:0 0 4px}} p{{color:#52514e;margin:0 0 14px}}
.row{{display:flex;gap:26px;flex-wrap:wrap}} .t{{font-size:13px;font-weight:600;fill:#0b0b0b}}
.v{{font-size:13px;fill:#0b0b0b}} .v2{{font-size:11px;fill:#0b0b0b}} .l{{font-size:12px;fill:#0b0b0b}}
.s{{font-size:10px;fill:#52514e}} .note{{color:#52514e;font-size:12px;margin-top:8px}}
</style>
<h1>Our own line reader with 5&times; more training lines (experiment 83)</h1>
<p>Held-out pages only: the owner's 20 checked pages (1937&ndash;2006) and lab documents 1&ndash;2. Punctuation and
spacing not counted; the same Azure line boxes for every reader.</p>
<div class="row">{bars("owner's 20 pages: letters wrong, %", Y, "letters")}{bars("owner's 20 pages: words wrong, %", Y, "words")}
{bars("lab docs 1&ndash;2: letters wrong, %", L, "letters")}{"".join(ag)}</div>
<div class="note">New lines: 7,763 documents from 3,529 journals (2.4M lines, 63% before 2000), read by v1; a line was
trained on only where v1 and Azure agree exactly. No Gemini, no owner time. GPU so far: ${float(sys.argv[3]) if len(sys.argv) > 3 else 0:.2f}.</div>
"""
out = HERE / "out/look/v3_scored.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html, encoding="utf-8")
print(out)
