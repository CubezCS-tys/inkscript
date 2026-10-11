"""The owner's page for experiment 34: out/report.html (opens from disk; pictures beside it in out/report_files/).

    PYTHONPATH=src python make_report.py

A contact sheet of the chosen pages grouped by kind and by decade (each thumbnail links to the full page), the
correction mode's screenshots (out/shots/, taken in Chromium), the estimated hours (out/estimate.json), the
smoke-test scores (out/score_*.json) and how to start.
"""
from __future__ import annotations

import html
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")
GOLD = OUT / "gold"
RF = OUT / "report_files"
KIND_NAMES = dict(body="plain body text", footnotes="footnotes", quran="Quran quotations", vowelled="vowelled text",
                  table="tables", equation="equations", latin="mixed Latin", headings="headings and first pages",
                  handwriting="handwriting", decorative="decorative lettering", magazine="magazines (newspaper-like layout)")
ORDER = ["body", "footnotes", "headings", "quran", "vowelled", "latin", "table", "equation", "magazine",
         "handwriting", "decorative"]
SHOTS = [("r1_start.png", "Start (the real set): progress, hours left, the pages by kind; “Continue” opens the first page not done."),
         ("r2_vowelled.png", "A vowelled page (1980): the line large, Azure's draft in the field; yellow where the readers differ (here vowel marks and a word)."),
         ("r3_quran_old.png", "An old print (before 1960) with Quran quotations, at the next line where the readers differ (Alt+N)."),
         ("r4_table.png", "A 1968 table drafted by Gemini as a grid beside its crop: check and fix cell by cell."),
         ("r5_magazine.png", "A magazine page: blocks with their column and order; click blocks to make an article."),
         ("1_start.png", "Start: progress, hours left, pages by kind; “Continue” opens the first page not done."),
         ("2_line.png", "One line: the scan's line large, the draft under it in a big right-to-left field. Enter = correct, next."),
         ("3_disagreement.png", "Where the two readers differ, the word is yellow; the second reading is one key away (Alt+2)."),
         ("4_added_line.png", "A line Azure missed: draw its box on the page, type it."),
         ("5_table.png", "Tables: the crop beside an editable grid (add/merge rows and cells)."),
         ("6_equation.png", "Equations: the crop and its LaTeX."),
         ("7_articles.png", "Blocks and articles: each block keeps its place and column; click blocks to group an article."),
         ("8_order.png", "Reading order: the lines numbered on the page; move one earlier or later.")]


def thumb(pid: str, w: int = 230) -> str:
    RF.mkdir(parents=True, exist_ok=True)
    f = RF / "thumbs" / f"{pid}.jpg"
    if not f.exists():
        f.parent.mkdir(exist_ok=True)
        img = cv2.imread(str(GOLD / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE)
        h = int(img.shape[0] * w / img.shape[1])
        cv2.imwrite(str(f), cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 70])
    return f"report_files/thumbs/{pid}.jpg"


def main() -> int:
    sel = json.loads((OUT / "selection.json").read_text())
    est = json.loads((OUT / "estimate.json").read_text()) if (OUT / "estimate.json").exists() else {}
    prog = {}
    try:
        from inkscript.gold.format import progress
        prog = progress(GOLD)
    except Exception:
        pass
    spend = 0.0
    if (OUT / "spend.jsonl").exists():
        spend = sum(json.loads(l)["usd"] for l in (OUT / "spend.jsonl").read_text().splitlines() if l.strip())
    flagged = {}
    for s in sel:
        f = GOLD / f"{s['page_id']}.json"
        if f.exists():
            g = json.loads(f.read_text())
            flagged[s["page_id"]] = (len(g["lines"]), sum(1 for ln in g["lines"] if ln.get("disagree")),
                                     len(g.get("tables", [])), len(g.get("equations", [])))
    by_kind = defaultdict(list)
    for s in sel:
        by_kind[s["primary"]].append(s)
    decades = sorted({s["decade"] for s in sel}, key=lambda d: (d != "pre-1960", d))
    docs = len({s["stem"] for s in sel})
    split = Counter(s["split"] for s in sel)
    cnt_dec = Counter(s["decade"] for s in sel)
    tags = Counter(t for s in sel for t in s["kinds"])

    def card(s):
        n, d, t, e = flagged.get(s["page_id"], (0, 0, 0, 0))
        extra = [k for k in s["kinds"] if k != s["primary"]]
        return (f'<a class="card{" dev" if s["split"] == "dev" else ""}" href="gold/{html.escape(s["page_id"])}.jpg" '
                f'title="{html.escape(s["journal"])} {s["year"]}"><img loading="lazy" src="{thumb(s["page_id"])}">'
                f'<span class="cap"><b>{html.escape(s["stem"])}</b> p{s["page"]} · {s["year"] or "?"}<br>'
                f'{n} lines · <span class="dis">{d} to check</span>{f" · {t} table" if t else ""}{f" · {e} eq." if e else ""}'
                f'{"<br><i>" + ", ".join(extra) + "</i>" if extra else ""}{" · <u>dev</u>" if s["split"] == "dev" else ""}</span></a>')

    sheet = []
    for k in ORDER:
        rows = by_kind.get(k)
        if not rows:
            continue
        sheet.append(f'<h3>{KIND_NAMES.get(k, k)} <small>{len(rows)} pages</small></h3>')
        for d in decades:
            rs = [s for s in rows if s["decade"] == d]
            if rs:
                sheet.append(f'<div class="dec"><span class="dl">{d}</span><div class="row">' +
                             "".join(card(s) for s in sorted(rs, key=lambda s: s["year"])) + "</div></div>")
    shots = []
    for f, cap in SHOTS:
        src = OUT / "shots" / f
        if src.exists():
            RF.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, RF / f)
            shots.append(f'<figure><img src="report_files/{f}"><figcaption>{html.escape(cap)}</figcaption></figure>')
    hours = est.get("hours", {})
    dr = est.get("dryrun") or {}
    dry = ""
    if dr:
        v = dr.get("verdicts", {})
        dry = (f"<p><b>Dry run</b> (the agent, not you, on {dr.get('lines')} random disagreements from the dev pages, "
               f"judged on the ink): Azure right {v.get('azure', 0)}, the second reading right {v.get('gemini', 0)}, "
               f"neither (typing needed) {v.get('neither', 0)}, not text (one key) {v.get('delete', 0)}, unclear "
               f"{v.get('unclear', 0)}. Most disagreements are one key. Many are فى/في: old prints write فى and Azure "
               f"keeps it; the second reader modernises it, so <b>keep Azure there</b>.</p>")
    smoke = ""
    sm = OUT / "score_gemini_vs_draft.json"
    if sm.exists():
        a = json.loads(sm.read_text())["summary"]["all"]
        smoke = (f"<p>Plumbing only: the scorer run on the drafts as if they were gold. Azure against its own draft: 0 errors "
                 f"(as it must). The second reading against Azure's draft (not against the truth): characters differ "
                 f"{100 * a['faithful.cer']:.1f}% as printed, {100 * a['folded.cer']:.1f}% with vowels and letter forms folded; "
                 f"{a['dropped_per_1000_lines']:.0f} lines in 1,000 it left empty. These are <b>not</b> accuracies: "
                 f"the real numbers come once you have corrected the pages.</p>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>The yardstick</title><style>
:root{{--bg:#f7f5f0;--fg:#1e1e1e;--mut:#6b6b6b;--card:#fff;--line:#ddd6c8;--acc:#1f6f5c;--dis:#a86a00}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#17181a;--fg:#e8e6e1;--mut:#9a9a9a;--card:#222326;--line:#3a3a3a;--acc:#5fc3a8;--dis:#e0a640}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,Segoe UI,sans-serif;margin:0 auto;max-width:1300px;padding:16px}}
h1{{font-size:28px;margin:8px 0}} h2{{margin-top:36px;border-bottom:1px solid var(--line)}} h3 small{{color:var(--mut);font-weight:400}}
.big{{display:flex;flex-wrap:wrap;gap:12px}} .big div{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;min-width:150px}}
.big b{{display:block;font-size:24px}} .dec{{display:flex;gap:8px;margin:6px 0}} .dl{{width:70px;flex:none;color:var(--mut);padding-top:4px}}
.row{{display:flex;flex-wrap:wrap;gap:8px}} .card{{display:block;width:150px;background:var(--card);border:1px solid var(--line);border-radius:6px;overflow:hidden;color:inherit;text-decoration:none;font-size:11px}}
.card.dev{{border-style:dashed}} .card img{{width:150px;display:block}} .cap{{display:block;padding:4px 6px}} .dis{{color:var(--dis)}}
figure{{margin:0 0 24px}} figure img{{max-width:100%;border:1px solid var(--line);border-radius:6px}} figcaption{{color:var(--mut)}}
code,pre{{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:2px 6px}} pre{{padding:10px;overflow:auto}}
table{{border-collapse:collapse}} td,th{{border:1px solid var(--line);padding:4px 8px;text-align:right}}
</style></head><body>
<h1>The yardstick: 200 pages to check by hand</h1>
<p>Every reader (Azure, Gemini, open models, our own) will be scored on these pages. The pages are drafted from Azure's
reading; a second, blind reading (Gemini) marks the words where the two disagree. You correct; you do not type.</p>
<div class="big"><div><b>{len(sel)}</b>pages</div><div><b>{docs}</b>documents</div><div><b>{len({s["stem"][:4] for s in sel})}</b>journals</div>
<div><b>{split.get("test", 0)} / {split.get("dev", 0)}</b>held-out test / dev pages</div>
<div><b>{prog.get("lines", 0):,}</b>lines</div><div><b>{sum(v[1] for v in flagged.values()):,}</b>lines where readers differ</div>
<div><b>{hours.get("expected", "?")} h</b>estimated correcting ({hours.get("low", "?")}–{hours.get("high", "?")} h)</div>
<div><b>${spend:.2f}</b>Gemini spent (cap $15)</div></div>

<h2>How to start</h2>
<pre>cd /home/yassine/inkscript
.venv/bin/inkscript view --gold experiments/34_yardstick/out/gold</pre>
<p>Then open <b><a href="http://localhost:8766/">http://localhost:8766/</a></b> in Chrome on Windows and press <b>Continue</b>.
Every Enter saves; close the browser any time and Continue picks up at the first line not done. If Windows cannot reach
it, stop it (Ctrl+C) and start it again with <code>--host 0.0.0.0</code>.</p>
<p><b>Keys:</b> Enter = correct, next · Alt+2 = take the second reading · Alt+1 = back to Azure's · Esc = undo this line ·
Alt+N = next line where readers differ · Ctrl+Del = not text (a speck) · Alt+U = unsure · Alt+K = line kind ·
Alt+↓/↑ = move without accepting · Ctrl+S = save. The rule: <b>exactly as printed</b> (vowel marks and hamza as printed, no kashida).</p>

<h2>Correction mode</h2>
{"".join(shots) or "<p>(screenshots missing)</p>"}

<h2>Estimated time</h2>
{est.get("html", "<p>(no estimate yet)</p>")}
{dry}

<h2>Smoke test of the scorer</h2>
{smoke}

<h2>The pages, by kind and decade</h2>
<p>Primary kind = the rarest thing on the page; other kinds it also holds are in italics. Dashed cards are the
<b>dev</b> pages (journals we may tune on); all others are the <b>held-out test</b> (never tuned on). Click a page to see it.
Decades: {", ".join(f"{d} {cnt_dec[d]}" for d in decades)}. Pages holding each kind: {", ".join(f"{KIND_NAMES.get(k, k)} {v}" for k, v in tags.most_common())}.</p>
{"".join(sheet)}
</body></html>"""
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print("wrote", OUT / "report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
