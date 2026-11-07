"""Training curve page (SVG) for a run's train_log.jsonl -> HTML (rendered to PNG by shot77.py)."""
import json
import sys

log, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
L = [json.loads(l) for l in open(log)]
tr = [d for d in L if "loss" in d]
dv = [d["dev"] for d in L if "dev" in d]
W, H, P = 860, 300, 50


def poly(xs, ys, xmax, ymax, col):
    pts = " ".join(f"{P + x / xmax * (W - 2 * P):.1f},{H - P - y / ymax * (H - 2 * P):.1f}" for x, y in zip(xs, ys))
    return f'<polyline fill="none" stroke="{col}" stroke-width="2.5" points="{pts}"/>'


ep_len = max(d["step"] for d in dv) / len(dv)
xs = [d["step"] / ep_len for d in dv]
cer = [100 * d["cer"] for d in dv]
ymax = max(cer) * 1.1
svg = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" font-family="system-ui" font-size="13">']
for k in range(0, 6):
    y = ymax * k / 5
    yy = H - P - y / ymax * (H - 2 * P)
    svg.append(f'<line x1="{P}" x2="{W-P}" y1="{yy}" y2="{yy}" stroke="#e5e2da"/><text x="8" y="{yy+4}" fill="#555">{y:.2f}%</text>')
for e in range(0, len(dv) + 1, 2):
    xx = P + e / len(dv) * (W - 2 * P)
    svg.append(f'<text x="{xx-4}" y="{H-P+18}" fill="#555">{e}</text>')
svg.append(poly(xs, cer, len(dv), ymax, "#2a6f97"))
for x, c in zip(xs, cer):
    svg.append(f'<circle cx="{P + x / len(dv) * (W - 2 * P)}" cy="{H - P - c / ymax * (H - 2 * P)}" r="3.5" fill="#2a6f97"/>')
svg.append(f'<text x="{W/2-40}" y="{H-8}" fill="#555">epoch</text></svg>')
last = dv[-1]
html = f"""<!doctype html><meta charset="utf-8"><style>body{{background:#fbfaf7;color:#222;font:15px system-ui;padding:18px;width:880px}}
h2{{margin:0 0 6px}}p{{margin:4px 0 10px;color:#444}}</style>
<h2>{title}</h2>
<p>Character difference from Azure on 8,195 held-in lines (articles never trained on), after each epoch.
Azure itself is wrong on about 0.6% of characters, so this cannot reach 0.</p>
{''.join(svg)}
<p>Last epoch: {100*last['cer']:.2f}% of characters, {100*last['line_err']:.1f}% of lines differ from Azure.
{len(dv)} epochs, {last['t']/60:.0f} minutes on one RTX 5090.</p>"""
open(out, "w").write(html)
print(out)
