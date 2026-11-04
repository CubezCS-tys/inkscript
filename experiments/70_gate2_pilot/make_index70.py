"""Experiment 70 (copied from experiment 52): index of a gate-1 run folder: python3 make_index70.py <run dir> (out/j0165 or out/j0165_final); one row per article, hardest first (copied from the exam's make_index.py)."""
import html, json, re, sys
from pathlib import Path
X = Path(__file__).resolve().parent / "out"
HERE = Path(sys.argv[1]).resolve()
FINAL = HERE.name.endswith("_final")
arts = {a["stem"]: a for a in json.loads((X / "sample70.json").read_text())["articles"]}
F = json.loads((HERE / "flags.json").read_text())["articles"]
S = json.loads((HERE / "summary.json").read_text())["articles"]
def title(s):
    f = HERE / "masters" / f"{s}.jats.xml"
    if not f.exists():
        return "(no master)"
    m = re.search(r"<article-title[^>]*>(.*?)</article-title>", f.read_text(encoding="utf-8"), re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else s
def key(s):
    f = F.get(s, {})
    return (-f.get("high", 0), -f.get("medium", 0), -f.get("low", 0))
rows = []
for s in sorted(arts, key=key):
    a, f, x = arts[s], F.get(s, {}), S.get(s, {})
    tags = ", ".join(a.get("flags") or []) + (f" · {a.get('lang')}" if a.get("lang") not in (None, "ar") else "")
    kinds = ", ".join(f"{k} {v}" for k, v in sorted((f.get("kinds") or {}).items(), key=lambda kv: -kv[1]))
    link = f'<a href="mirror/{s}.html">{html.escape(s)}</a>' if (HERE / "views" / "mirror" / f"{s}.html").exists() else html.escape(s)
    rows.append(f"<tr><td>{link}</td><td dir=auto>{html.escape(title(s))}</td><td>{a.get('year','')}</td>"
                f"<td dir=auto>{html.escape(a.get('journal') or '')}</td><td>{a.get('n','')}</td><td>{html.escape(tags)}</td>"
                f"<td class=h>{f.get('high',0)}</td><td>{f.get('medium',0)}</td><td>{f.get('low',0)}</td><td class=k>{html.escape(kinds)}</td></tr>")
DESC = ("Gate 2 pilot (experiment 70): one journal, مجلة الطفولة والتنمية (0165), 2010-2025, the scan route (2016-2019, 2021, 2023-2025). Prompt v3.6, Argon, thinking low, Batch; today's rules + the letter fix (ی/ک). " +
        ("Then the judge (Argon, judge v2, two keys: confidence >= 0.85 and the code check) on every flagged page + 50 random unflagged; its two-key edits applied." if FINAL else "The run's answers through every current code rule, no judge patches.") + " Built 2026-11-02.")
LINKS = ('Run before the judge: <a href="../j0165/index.html">j0165</a>.' if FINAL else 'Final (with the judge): <a href="../j0165_final/index.html">j0165_final</a>.')
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{"Gate 1, final" if FINAL else "Gate 1, run"}</title><style>
:root{{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e2dc;--hi:#c62828}}
@media (prefers-color-scheme:dark){{:root{{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--line:#3a3a37;--hi:#ef5350}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%}} td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:start;vertical-align:top}}
td.h{{color:var(--hi);font-weight:600}} td.k{{color:var(--muted);font-size:12px}} a{{color:inherit}}
</style></head><body><h1>Gate 1: مجلة الطفولة العربية · {"final" if FINAL else "run"}</h1>
<p>{DESC}</p>
<p>{len(arts)} articles, hardest first (flags high, then medium, then low). Each id opens the Layout view (scan beside ours).
{LINKS}</p>
<div class=wrap><table><thead><tr><th>article</th><th>title</th><th>year</th><th>journal</th><th>pages</th><th>layout</th><th>high</th><th>med</th><th>low</th><th>flag kinds</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></body></html>"""
(HERE / "views" / "index.html").write_text(page, encoding="utf-8")
print(HERE / "views" / "index.html", len(rows))
