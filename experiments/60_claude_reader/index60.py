"""Experiment 60: out/side/index.html, the front page of the side-by-sides, with the headline numbers read from the
score files (no calls)."""
import json

from common60 import OUT
from side60 import CSS

T1, T2 = OUT / "t1", OUT / "t2"
pg = json.loads((T1 / "page_scores.json").read_text())["totals"]
me = json.loads((T1 / "meta_scores.json").read_text())["totals"]
ci = json.loads((T1 / "cite_scores.json").read_text())["totals"]
au = json.loads((T1 / "audit.json").read_text())["totals"]
cmp2 = json.loads((T2 / "compare.json").read_text())["totals"]
calls = [json.loads(s) for s in (OUT / "calls.jsonl").read_text().splitlines() if s.strip()]
spent = sum(c.get("usd", 0) for c in calls)


def row(label, a, c, note=""):
    return f"<tr><td>{label}</td><td class='a'>{a}</td><td class='c'>{c}</td><td class='m'>{note}</td></tr>"


t1 = "".join([
    row("pages right / minor / serious (60)", f"{pg['argon_first'].get('right',0)} / {pg['argon_first'].get('minor',0)} / {pg['argon_first'].get('serious',0)}",
        f"{pg['claude'].get('right',0)} / {pg['claude'].get('minor',0)} / {pg['claude'].get('serious',0)}",
        "Argon's first answer through today's code; after the judge: 43 / 17 / 0"),
    row("wrong words, 10 word pages (1,532 words)", "0", "21 (1.4%)", "Claude keeps Azure's misreadings"),
    row("metadata fully right (30)", me["argon_fully_right"], me["claude_fully_right"], "titles and missing co-authors"),
    row("citations fully right (69 of the 80)", ci["argon_fully_right"], ci["claude_fully_right"],
        f"Claude parsed no work for {ci['claude_not_parsed']} of them (mostly footnotes)"),
    row("Azure fixes proposed (same 124 chunks)", au["argon"]["fixes"], au["claude"]["fixes"], ""),
    row("missed text (e.g. unread table cells)", au["argon"]["missed"], au["claude"]["missed"], ""),
    row("lines left out / used twice / invented ids", f"{au['argon']['left_out']} / {au['argon']['twice']} / {au['argon']['unknown']}",
        f"{au['claude']['left_out']} / {au['claude']['twice']} / {au['claude']['unknown']}", "of 36,820 lines"),
])
has = lambda w, f: cmp2.get(f"has:{w}:{f}", 0)  # noqa: E731
t2 = "".join(row(f"references with {f} (424 works)", has("argon", f), has("claude", f))
             for f in ("title", "authors", "editors", "translators", "edition", "cited", "cal"))
CSS2 = CSS.replace("</style>", "table.s{border-collapse:collapse;width:100%;margin:8px 0 18px}table.s td,table.s th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}.wrap{overflow-x:auto}</style>")
doc = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Claude vs Argon</title>{CSS2}</head><body>
<h1>Claude Opus 5.5 as the reader, against Gemini 4 Argon</h1>
<p class='m'>Experiment 60, 2026-10-31. The same requests Gemini was sent (page images, Azure's numbered lines, prompt v3.3 / v3.5b),
answered by Claude Opus 5.5 (effort low, Message Batches) and built with the same rules, enrichment and masters code.
Spent ${spent:.2f} of the $40 cap.</p>
<h2>Test 1: the proof pack (exam, prompt v3.3)</h2><div class='wrap'><table class='s'><tr><th></th><th class='a'>Argon</th><th class='c'>Claude</th><th></th></tr>{t1}</table></div>
<p><a href='t1.html'>Every page where the two differ: scan line | Argon | Claude, with the verdicts</a> (44 pages).</p>
<h2>Test 2: gate 1 (journal 0130, prompt v3.5b, 12 articles)</h2><div class='wrap'><table class='s'><tr><th></th><th class='a'>Argon</th><th class='c'>Claude</th><th></th></tr>{t2}</table></div>
<p>Document types 12 of 12 the same; corresponding authors none in either. <a href='t2.html'>Six random pages where the text differs</a> ·
<a href='t2_tables.html'>tables and figures that differ</a>.</p>
</body></html>"""
(OUT / "side" / "index.html").write_text(doc, encoding="utf-8")
print(OUT / "side" / "index.html")
