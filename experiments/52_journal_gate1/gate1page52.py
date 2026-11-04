"""Experiment 52: the owner's page, out/gate1.html (one static file: inline CSS + SVG, no CDN, no fonts fetched).
Reads the result files in out/; no calls, no database writes.

    .venv/bin/python experiments/52_journal_gate1/gate1page52.py
"""
from __future__ import annotations

import html
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
O = HERE / "out"
E = html.escape
VIEW = "/articles/{}"   # the article in the Desk (the page is served at :8004/gate1/); the Desk links on to the scan view


def jl(p):
    return json.loads((O / p).read_text(encoding="utf-8"))


J, R6, S6 = jl("bridges_j0130.json"), jl("bridges_r600.json"), jl("bridges_r600_same_size126.json")
CAT, INS = jl("catalogue/results.json"), jl("catalogue/inside.json")
DJ, D6 = jl("detect_j0130.json"), jl("detect_r600.json")
FL = jl("fields_j0130_final.json")
JS = jl("j0130/judge_summary.json")
LOOK = jl("look10_verdicts.json")
ARTS = {a["stem"]: a for a in jl("sample52_all.json")["articles"]}
RUN = {a["stem"] for a in jl("sample52.json")["articles"]}
SPEND = jl("spend.json")
A600 = dict(type_works=dict(book=2483, journal_article=1418, turath=282, other=292, chapter=225, thesis=225, website=179,
                            conference_paper=165, report=134, legal=44, news=31),
            held=0.029, arabic_held=0.308)


def pct(x, d=0):
    return f"{100 * x:.{d}f}%"


def view(stem, text=None):
    return f'<a href="{VIEW.format(stem)}" target="_blank" rel="noopener">{E(text or stem)}</a>'


# ------------------------------------------------------------------ the network: citations inside the journal
def network() -> str:
    links = INS["linked"]
    nodes = {}
    for s in RUN:
        a = ARTS[s]
        nodes[s] = dict(id=s, year=int(a["year"]), title=a.get("title") or "", run=True)
    for x in links:
        t = x["target_stem"] or f"rec{x['target_c999']}"
        if t not in nodes:
            nodes[t] = dict(id=t, year=int(x["target_year"]), title=x["target_title"], run=x["target_stem"] in RUN)
    cited = Counter((x["target_stem"] or f"rec{x['target_c999']}") for x in links)
    citing = Counter(x["citing_stem"] for x in links)
    years = list(range(1994, 2026))
    W, H, L, Rr, base = 1100, 440, 40, 24, 330
    xs = lambda y: L + (y - years[0]) * (W - L - Rr) / (len(years) - 1)      # noqa: E731
    by_year = defaultdict(list)
    for n in sorted(nodes.values(), key=lambda n: (-(cited[n["id"]] + citing[n["id"]]), n["id"])):
        by_year[n["year"]].append(n)
    pos = {}
    for y, ns in by_year.items():
        for i, n in enumerate(ns):
            pos[n["id"]] = (xs(y) + ((i % 3) - 1) * 9, base + 14 + (i // 3) * 9)
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Citations inside the journal, on a timeline" class="net">']
    for y in years:
        if y % 5 == 0 or y == 2025:
            out.append(f'<line x1="{xs(y):.1f}" y1="{base - 2}" x2="{xs(y):.1f}" y2="{base + 4}" class="tick"/>'
                       f'<text x="{xs(y):.1f}" y="{base + 100}" class="yl">{y}</text>')
    out.append(f'<line x1="{L}" y1="{base}" x2="{W - Rr}" y2="{base}" class="axis"/>')
    for lo, hi in ((2005, 2008), (2017, 2019), (2023, 2025)):
        out.append(f'<rect x="{xs(lo) - 8:.1f}" y="{base + 6}" width="{xs(hi) - xs(lo) + 16:.1f}" height="82" rx="6" class="band"/>')
    for x in links:
        t = x["target_stem"] or f"rec{x['target_c999']}"
        (x1, y1), (x2, y2) = pos[x["citing_stem"]], pos[t]
        h = min(base - 20, 30 + abs(x1 - x2) * 0.55)
        cls = "arc self" if x.get("self") else "arc"
        tip = f"{x['citing_stem']} ({ARTS[x['citing_stem']]['year']}) cites {t} ({x['target_year']}): {x['target_title']}"
        out.append(f'<path d="M{x1:.1f},{y1 - 4:.1f} C{x1:.1f},{y1 - h:.1f} {x2:.1f},{y2 - h:.1f} {x2:.1f},{y2 - 4:.1f}" '
                   f'class="{cls}"><title>{E(tip)}</title></path>')
    for n in nodes.values():
        x, y = pos[n["id"]]
        k = cited[n["id"]]
        r = 3 + 2.2 * math.sqrt(k) if k else 3
        cls = "node run" if n["run"] and n["id"] in RUN else ("node bucket" if n["id"] in ARTS else "node other")
        if citing[n["id"]] or k:
            cls += " linked"
        tip = f"{n['id']} ({n['year']}) {n['title']} — cited by {k} article(s) of the journal; cites {citing[n['id']]}"
        inner = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" class="{cls}"><title>{E(tip)}</title></circle>'
        out.append(f'<a href="{VIEW.format(n["id"])}" target="_blank">{inner}</a>' if n["id"] in RUN else inner)
    out.append(f'<text x="{L}" y="18" class="cap">each arc: one article (right) citing an earlier article of the same '
               f'journal (left) · hover for titles · dashed: the citing author cites their own earlier article</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ pieces
def tile(n, label, sub="", cls=""):
    return f'<div class="card kpi {cls}"><div class="n">{n}</div><div class="l">{label}</div><div class="s">{sub}</div></div>'


def cmp_row(label, j, r, rs="", note=""):
    return (f"<tr><td>{label}</td><td class=num><b>{j}</b></td><td class=num>{r}</td><td class=num>{rs}</td>"
            f"<td class=note>{note}</td></tr>")


def bar_pair(label, a, b, amax):
    wa, wb = 100 * a / amax, 100 * b / amax
    return (f'<div class="bp"><div class="bpl">{E(label)}</div><div class="bpb">'
            f'<div class="b j" style="width:{wa:.1f}%" title="journal {pct(a, 1)}"></div>'
            f'<div class="b r" style="width:{wb:.1f}%" title="random 600 {pct(b, 1)}"></div></div>'
            f'<div class="bpn">{pct(a)} · {pct(b)}</div></div>')


def main():
    P, I, Rf = J["people"], J["institutions"], J["references"]
    P6, I6, Rf6 = R6["people"], R6["institutions"], R6["references"]
    M = S6["mean"]
    ij = CAT["inside_journal"]
    held = CAT["held"]["share_mentions_accept"]
    # type mix
    tw = CAT["type_works"]
    tot_j, tot_6 = sum(tw.values()), sum(A600["type_works"].values())
    kinds = ["journal_article", "book", "thesis", "turath", "chapter", "conference_paper", "website", "report", "other"]
    names = dict(journal_article="journal articles", book="books", thesis="theses", turath="classical (turath)",
                 chapter="book chapters", conference_paper="conference papers", website="websites", report="reports",
                 other="other")
    amax = max(max(tw.get(k, 0) / tot_j, A600["type_works"].get(k, 0) / tot_6) for k in kinds)
    bars = "".join(bar_pair(names[k], tw.get(k, 0) / tot_j, A600["type_works"].get(k, 0) / tot_6, amax) for k in kinds)
    # tables
    comp = "".join([
        cmp_row("Authors with 2+ articles", f"{P['persons_2plus_articles']} of {P['persons']}", f"{P6['persons_2plus_articles']} of {P6['persons']}",
                f"{M['people.persons_2plus_articles']:.1f}", "the same person writing again in the set"),
        cmp_row("Byline authors with an authority id", pct(P["share_with_authority"]), pct(P6["share_with_authority"]),
                pct(M["people.share_with_authority"]), "Mandumah's authority file names them"),
        cmp_row("Repeat co-author pairs", P["repeated_pairs"], P6["repeated_pairs"], f"{M['people.repeated_pairs']:.0f}", ""),
        cmp_row("Institutions in 2+ articles", f"{I['institutions_2plus_articles']} of {I['distinct_institutions']}",
                f"{I6['institutions_2plus_articles']} of {I6['distinct_institutions']}", f"{M['institutions.institutions_2plus_articles']:.1f}", ""),
        cmp_row("Affiliations at a repeat institution", pct(I["share_affiliations_inst_2plus_articles"]),
                pct(I6["share_affiliations_inst_2plus_articles"]), pct(M["institutions.share_affiliations_inst_2plus_articles"]), ""),
        cmp_row("References (no Quran)", f"{Rf['mentions_no_quran']:,} ({Rf['per_article']} an article)",
                f"{Rf6['mentions_no_quran']:,} ({Rf6['per_article']})", f"{M['references.mentions_no_quran']:,.0f}", ""),
        cmp_row("Cited works shared by 2+ articles", Rf["shared_2plus_articles"], Rf6["shared_2plus_articles"],
                f"{M['references.shared_2plus_articles']:.1f}", "an undercount: same-work pairs the linker missed sit in the Desk's queue"),
        cmp_row("Largest group joined by shared references", f"{Rf['coupling_largest']} articles", f"{Rf6['coupling_largest']}",
                f"{M['references.coupling_largest']:.1f}", "bibliographic coupling"),
        cmp_row("References landing on a work Mandumah holds", pct(held, 1), "2.9%", "", "probe A's matcher, unchanged"),
        cmp_row("… of Arabic article / thesis / conference references", pct(CAT["arabic_script_catalogue_types"]["share"]),
                "31%", "", ""),
        cmp_row("Correction tasks per article", f"{DJ['per_article']:.2f}", f"{D6['per_article']:.2f}", "",
                f"per 100 references: {100 * DJ['tasks_touching_set'] / Rf['mentions_no_quran']:.1f} vs {100 * D6['tasks_touching_set'] / Rf6['mentions_no_quran']:.1f}"),
    ])
    top = "".join(f"<tr><td class=num>{t['articles']}</td><td dir=auto>{E(t['title'])}</td><td dir=auto>{E(', '.join(t['authors'][:2]))}</td>"
                  f"<td>{E(str(t['year'] or ''))}</td><td>{', '.join(view(s, s[5:]) for s in t['stems'][:6])}</td></tr>"
                  for t in Rf["top_cited"][:12])
    people = "".join(f"<tr><td dir=auto>{E(t['name'] or '')}</td><td class=num>{t['articles']}</td></tr>" for t in P["top_persons"][:8])
    insts = "".join(f"<tr><td dir=auto>{E(t['name'] or '')}</td><td class=num>{t['articles']}</td></tr>" for t in I["top"][:8])
    ok = [x for x in INS["linked"] if x["via"] == "probe A"]          # the one link47 link names another journal (wrong)
    ex = [x for x in ok if x["target_stem"] in RUN][:4] + [x for x in ok if x["target_stem"] and x["target_stem"] not in RUN][:2]
    examples = "".join(
        f'<div class="card ex"><div class="exh">{view(x["citing_stem"])} ({ARTS[x["citing_stem"]]["year"]}) cites '
        f'{view(x["target_stem"]) if x["target_stem"] in RUN else E(x["target_stem"])} ({x["target_year"]})</div>'
        f'<div class="exb" dir="rtl">{E(x["printed"][:260])}</div></div>' for x in ex)
    dt = ", ".join(f"{k} {v}" for k, v in FL["document_types"].items())
    c = FL["counts"]
    v35 = (f"<li><b>Document types</b>: {E(dt)}.</li>"
           f"<li><b>Editors</b> in {c.get('refs_with_editor', 0)} references and <b>translators</b> in {c.get('refs_with_translator', 0)}; "
           f"<b>editions</b> in {c.get('refs_with_edition', 0)}; a thesis's degree in {c.get('refs_with_degree', 0)}; access dates in {c.get('refs_with_access_date', 0)}.</li>"
           f"<li><b>Corresponding authors</b>: 0 (the model marked none; this journal's bylines rarely print the mark).</li>"
           f"<li><b>Table notes</b>: {c.get('table_table-note', 0)} notes and {c.get('table_source', 0)} «المصدر» lines tied to their tables.</li>")
    look = "".join(f"<li>{view(v['page'].split(':')[0], v['page'])}: <b>{v['verdict']}</b> — {E(v['note'])}</li>" for v in LOOK["verdicts"])
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gate 1: one journal</title>
<style>
:root {{ --bg:#f3f4f6; --card:#fff; --line:#e5e7eb; --ink:#111827; --ink2:#374151; --muted:#6b7280; --accent:#4f46e5;
  --accent-l:#eef2ff; --r6:#9ca3af; --good:#059669; --warn:#b45309; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:14px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }}
header {{ background:var(--card); border-bottom:1px solid var(--line); }}
.wrap {{ max-width:1180px; margin:0 auto; padding:0 16px; }}
header .wrap {{ padding-top:18px; padding-bottom:16px; }}
.crumb {{ color:var(--accent); font-weight:600; font-size:12px; letter-spacing:.04em; text-transform:uppercase; }}
h1 {{ font-size:22px; margin:4px 0; }} h2 {{ font-size:15px; margin:0 0 8px; }}
.sub {{ color:var(--muted); margin:0; max-width:860px; }}
main .wrap {{ padding-top:18px; padding-bottom:60px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:12px; margin-bottom:16px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.kpi .n {{ font-size:28px; font-weight:700; line-height:1.1; color:var(--accent); }}
.kpi .l {{ font-size:12.5px; color:var(--ink2); margin-top:2px; }} .kpi .s {{ font-size:12px; color:var(--muted); }}
.kpi.grey .n {{ color:var(--ink2); }}
.answer {{ border-left:4px solid var(--good); }}
.sec {{ margin-bottom:16px; }}
.two {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px; }}
@media (max-width:860px) {{ .two {{ grid-template-columns:1fr; }} }}
table {{ border-collapse:collapse; width:100%; }} .tw {{ overflow-x:auto; }}
th, td {{ text-align:start; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ font-size:12px; color:var(--muted); font-weight:600; }}
td.num {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }} td.note {{ color:var(--muted); font-size:12.5px; }}
a {{ color:var(--accent); text-decoration:none; }} a:hover {{ text-decoration:underline; }}
.net {{ width:100%; height:auto; display:block; }}
.net .axis {{ stroke:#9ca3af; stroke-width:1; }} .net .tick {{ stroke:#9ca3af; }}
.net .yl {{ font-size:11px; fill:var(--muted); text-anchor:middle; }} .net .cap {{ font-size:12px; fill:var(--muted); }}
.net .band {{ fill:var(--accent-l); }}
.net .arc {{ fill:none; stroke:var(--accent); stroke-width:1.6; opacity:.55; }} .net .arc:hover {{ opacity:1; stroke-width:3; }}
.net .arc.self {{ stroke-dasharray:4 3; }}
.net .node {{ stroke:#fff; stroke-width:1.5; }} .net .node.run {{ fill:#c7d2fe; }} .net .node.run.linked {{ fill:var(--accent); }}
.net .node.bucket {{ fill:#d1d5db; }} .net .node.bucket.linked, .net .node.other.linked {{ fill:#6b7280; }} .net .node.other {{ fill:#d1d5db; }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; font-size:12px; color:var(--muted); margin-top:6px; }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:5px; vertical-align:-1px; }}
.bp {{ display:grid; grid-template-columns:150px 1fr 90px; gap:8px; align-items:center; margin:5px 0; }}
.bpl {{ font-size:12.5px; color:var(--ink2); }} .bpn {{ font-size:12px; color:var(--muted); text-align:right; }}
.bpb {{ display:flex; flex-direction:column; gap:2px; }} .b {{ height:8px; border-radius:0 4px 4px 0; min-width:2px; }}
.b.j {{ background:var(--accent); }} .b.r {{ background:var(--r6); }}
.ex .exh {{ font-size:12.5px; color:var(--ink2); margin-bottom:4px; }} .ex .exb {{ font-size:13.5px; }}
.exs {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:12px; }}
ul {{ margin:0; padding-left:20px; }} li {{ margin:0 0 5px; }}
.muted {{ color:var(--muted); font-size:12.5px; }}
</style></head><body>
<header><div class="wrap"><div class="crumb">Education Citation Index · gate 1 · experiment 52 · 2026-10-22</div>
<h1>One journal, read whole: <span dir="rtl">مجلة الطفولة العربية</span></h1>
<p class="sub">All {len(RUN)} articles of 2010–2025 that Mandumah's bucket holds (2017–2019 and 2023–2025: {sum(ARTS[s]['n'] for s in RUN):,} pages),
read with prompt v3.5b, judged, linked. Every number is set beside the random 600 of experiment 48 —
and beside random sets of the same size drawn from the 600 (20 draws of {S6['n']}).</p></div></header>
<main><div class="wrap">
<div class="card answer sec"><h2>The answer</h2>
<p>Yes: inside one journal the bridges are <b>dense</b>, many times denser than in a random set of the same size. Authors write again
(16 people wrote 50 of the bylines), institutions repeat (three quarters of affiliations are at an institution seen twice),
84 cited works are shared, and the journal cites itself: <b>{ij['links']} references in {ij['citing_articles']} of the {len(RUN)} articles
point at {ij['cited_records']} earlier articles of the same journal</b>. A sixth of all references land on a work Mandumah holds (2.9% in the random 600).
Thin: repeat co-authorship (1 pair), citations between the articles of this very run ({ij['links_to_run']} links: the bucket's
gaps cut the years that would cite each other), and corresponding authors (none marked).
<b>Gate 2 (about 10 education journals) is justified</b>: the bridges between journals are what gate 1 cannot see.</p></div>
<div class="cards">
{tile(ij['links'], 'citations inside the journal', f"from {ij['citing_articles']} articles to {ij['cited_records']} of its articles (11 are self-citations)")}
{tile(pct(held, 1), 'references landing on a held work', 'random 600: 2.9%')}
{tile(Rf['shared_2plus_articles'], 'cited works shared by 2+ articles', f"same-size random sets: {M['references.shared_2plus_articles']:.0f}")}
{tile(Rf['coupling_largest'], 'articles in the largest coupled group', f"same-size random sets: {M['references.coupling_largest']:.0f}")}
{tile(P['persons_2plus_articles'], 'authors with 2+ articles', f"same-size random sets: {M['people.persons_2plus_articles']:.1f}")}
{tile(f"${SPEND['total']:.2f}", 'Gemini spend of the $32 cap', f"run ${SPEND['run']:.2f} · judge ${SPEND['judge']:.2f} · retries ${SPEND['retries']:.2f}", 'grey')}
</div>
<div class="card sec"><h2>The journal citing itself</h2>{network()}
<div class="legend"><span><span class="dot" style="background:var(--accent)"></span>article of this run, linked</span>
<span><span class="dot" style="background:#c7d2fe"></span>article of this run, no link</span>
<span><span class="dot" style="background:#6b7280"></span>earlier article of the journal, outside the run (1994–2016)</span>
<span>shaded: the years the bucket holds</span><span>bigger: cited more often</span></div>
<p class="muted">Links are probe A's catalogue matches ({ij['mentions']} references; one of them names another journal and is wrong, by reading).
A further {CAT['names_the_journal']['mentions'] - CAT['names_the_journal']['linked_inside']} references name the journal but found no catalogue record.</p></div>
<div class="card sec"><h2>Bridge by bridge</h2><div class="tw"><table>
<thead><tr><th>bridge</th><th>journal ({len(RUN)})</th><th>random 600</th><th>random sets of {S6['n']} (mean)</th><th></th></tr></thead>
<tbody>{comp}</tbody></table></div></div>
<div class="two">
<div class="card"><h2>What is cited: share of cited works</h2>
<div class="legend" style="margin:0 0 6px"><span><span class="dot" style="background:var(--accent)"></span>journal</span>
<span><span class="dot" style="background:var(--r6)"></span>random 600</span></div>{bars}
<p class="muted">Journal articles become the largest kind (49% against 26%); classical works almost vanish (0.4% against 5%).
That is why so much more lands on Mandumah's holdings.</p></div>
<div class="card"><h2>Who and where</h2><div class="two" style="margin:0">
<div><table><thead><tr><th>author</th><th>articles</th></tr></thead><tbody>{people}</tbody></table></div>
<div><table><thead><tr><th>institution</th><th>articles</th></tr></thead><tbody>{insts}</tbody></table></div></div></div>
</div>
<div class="card sec"><h2>The most-cited works</h2><div class="tw"><table>
<thead><tr><th>articles</th><th>work</th><th>author</th><th>year</th><th>citing (open beside the scan)</th></tr></thead>
<tbody>{top}</tbody></table></div>
<p class="muted">«مجلة الطفولة العربية» as a cited work is four references that name only the journal, joined by name: the kind of card the Desk's
"work joined without an author" task exists for.</p></div>
<div class="sec"><h2>Real examples: one article citing another of the same journal</h2><div class="exs">{examples}</div></div>
<div class="two">
<div class="card"><h2>Quality</h2><ul>
<li>126 of 126 articles answered; 126 masters valid against the JATS DTD and ALTO XSD.</li>
<li>Flags per 100 pages: high 0.86 · medium 3.85 · low 6.64 (the exam: 0.53 · 7.17 · 12.22). High: 20 tables with lost cells.</li>
<li>Judge on {JS['pages']['flagged']['pages']} flagged + {JS['pages']['random']['pages']} random pages: {JS['findings']} findings — 3 applied with two keys,
5 page retries applied, 22 to a person (20 of them «wrong kind»). Random pages: {JS['pages']['random']['none']} of 50 clean.</li>
<li>Ten random pages looked at beside the scan: <b>9 right, 1 minor, 0 serious</b>.</li></ul>
<ul class="muted" style="margin-top:8px">{look}</ul></div>
<div class="card"><h2>New in v3.5b</h2><ul>{v35}</ul>
<h2 style="margin-top:12px">Correction load</h2>
<p>{DJ['tasks_touching_set']} Desk tasks touch the journal ({DJ['per_article']:.2f} an article; random 600: {D6['per_article']:.2f}).
Almost all are «possible same work» ({DJ['kinds']['possible_same_work']['touching_set']}): in a dense journal the same book is cited in slightly
different words, and the linker leaves them apart. Each one a person answers makes the shared-works count above go up.</p></div>
</div>
<p class="muted">Pages: <a href="http://127.0.0.1:8899/j0130_final/index.html">the run's articles beside their scans</a> ·
files: experiments/52_journal_gate1/ (README.md, progress.md, out/). Private data: local only.</p>
</div></main></body></html>"""
    (O / "gate1.html").write_text(page, encoding="utf-8")
    print(O / "gate1.html", len(page))


if __name__ == "__main__":
    main()
