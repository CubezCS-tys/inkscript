"""Experiment 44: draw out/bucket_map.html from out/summary44.json (no network).

    .venv/bin/python experiments/44_bucket_map/render44.py
"""
import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
S = json.loads((OUT / "summary44.json").read_text())
P = S["prefixes"]
SRC, QDR = "mandumah-source-docs", "mandumah-qdrant-backups"
TRAIL = "aws-cloudtrail-logs-006127064053-14137c60"


def n(x):
    return f"{x:,}"


def gb(b):
    if b >= 1e12:
        return f"{b / 1e12:.2f} TB"
    if b >= 1e9:
        return f"{b / 1e9:.1f} GB" if b < 1e11 else f"{b / 1e9:.0f} GB"
    if b >= 1e6:
        return f"{b / 1e6:.0f} MB"
    if b >= 1e3:
        return f"{b / 1e3:.0f} KB"
    return f"{b} B"


e = html.escape
MYSQL_MIN = min(int(ln.split('\t')[1]) for ln in (OUT / f'listing/{QDR}__mysql_.tsv').open())
docs = P[f"{SRC}/(document folders)/"]
xb = docs["ext_bytes"]
gem = S["patterns"].get("<id>/<id>.gemini.title.json", {}).get("n", 0)
leg = P[f"{SRC}/legacy/"]
lt = P[f"{SRC}/legacy-test/"]
meta = P[f"{SRC}/metadata/"]
qd = P[f"{QDR}/qdrant/"]
my = P[f"{QDR}/mysql/"]
tr = P[f"{TRAIL}/AWSLogs/"]
D, O, C, M43 = S["docs"], S["overlap"], S["catalogue"], S["exp43_missing"]
src_total = docs["bytes"] + leg["bytes"] + lt["bytes"] + meta["bytes"] + 607
qdr_total = qd["bytes"] + my["bytes"]
all_total = src_total + qdr_total + tr["bytes"]

# One storage bar: every segment to scale
segs = [("Azure JSON", xb[".json"], "c-json", f"{n(D['main']['ids'])} files"),
        ("Searchable PDF", xb[".pdf"], "c-pdf", f"{n(D['main']['ids'])} files"),
        ("HTML reading view", xb[".html"], "c-html", f"{n(docs['ext']['.html'])} files"),
        ("legacy/ PDFs", leg["bytes"], "c-legacy", f"{n(leg['objects'])} files"),
        ("Qdrant snapshots", qd["bytes"], "c-qdrant", "3 collections"),
        ("MySQL dumps", my["bytes"], "c-mysql", f"{my['objects']} daily dumps"),
        ("catalogue + legacy-test + logs", meta["bytes"] + lt["bytes"] + tr["bytes"] + 607, "c-misc", "")]
bar = "".join(f'<div class="seg {c}" style="flex-grow:{b / all_total:.5f}" title="{e(l)}: {gb(b)}">'
              f'<span>{e(l) if b / all_total > .07 else ""}</span></div>' for l, b, c, _ in segs)
legend = "".join(f'<li><i class="sw {c}"></i><b>{e(l)}</b><span class="num">{gb(b)}</span>'
                 f'<span class="muted">{e(x)}</span></li>' for l, b, c, x in segs)

# Catalogue picture: articles (to scale) and dissertations
fam = C["by_family"]
art_total = fam["article:main"] + fam["article:legacy"] + fam["article:none"]
cbar = "".join(f'<div class="seg {c}" style="flex-grow:{v / art_total:.5f}"><span>{100 * v / art_total:.0f}%</span></div>'
               for v, c in ((fam["article:main"], "c-pdf"), (fam["article:legacy"], "c-legacy"),
                            (fam["article:none"], "c-none")))

qrows = []
for q in S["qdrant"]:
    if not q["key"].endswith(".snapshot"):
        continue
    col = q["key"].split("/")[1]
    mf = json.loads((OUT / "qdrant_manifests" / f"{col}.manifest.json").read_text())
    fields = ", ".join(mf.get("payload_schema", {}).keys()) or "(no indexed fields)"
    vec = mf["config"]["params"]["vectors"]
    kind = "dense 1536-d + sparse" if "dense" in vec else "one 1536-d vector"
    qrows.append(f"<tr><td><code>{e(col)}</code></td><td class='num'>{mf['created_utc'][:10]}</td>"
                 f"<td class='num'>{gb(q['bytes'])}</td><td class='num'>{n(mf['points_count'])}</td>"
                 f"<td>{kind}</td><td class='small'>{e(fields)}</td></tr>")

pat_rows = [
    ("<id>/<id>.pdf", D["main"]["ids"], "Azure's searchable PDF", "0001-000-002-003/0001-000-002-003.pdf"),
    ("<id>/<id>.json", D["main"]["ids"], "Azure Document Intelligence JSON", "0001-000-002-003/0001-000-002-003.json"),
    ("<id>/<id>.html", docs["ext"][".html"], "an HTML reading view of the pages (toolbar, page boxes)",
     "0244-006-011-001/0244-006-011-001.html"),
    ("<id>/<id>.gemini.title.json", gem, "Gemini's title and authors, ~150 bytes",
     "0001-000-002-003/0001-000-002-003.gemini.title.json"),
    ("legacy/<id>/<id>.pdf", leg["objects"], "a PDF only: no JSON, no HTML", "legacy/0011-030-111-001/0011-030-111-001.pdf"),
    ("legacy-test/<id>/<id>.pdf", lt["ext"].get(".pdf", 0), "test copy; also 48 LibreOffice lock files + 48 empty .tmp",
     "legacy-test/0011-037-140-002/0011-037-140-002.pdf"),
    ("metadata/metadata_final.xml.gz", 1, "the MARC catalogue (1.17 GB, 27 Aug)", "metadata/metadata_final.xml.gz"),
    ("metrics.txt", 1, "607-byte report of an old batch run (batch03, 18 Jun)", "metrics.txt"),
]
prow = "".join(f"<tr><td><code>{e(p)}</code></td><td class='num'>{n(c)}</td><td>{e(w)}</td>"
               f"<td class='small'><code>{e(x)}</code></td></tr>" for p, c, w, x in pat_rows)
forms = D["main"]["id_forms"]
comma = sum(v for k, v in forms.items() if "," in k)

missing_leg = ", ".join(M43["in_legacy"][:6])
nowhere = ", ".join(M43["nowhere"])

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Mandumah Bucket Map</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&family=Public+Sans:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* Layout: one reading column; storage drawn as to-scale bars, folders as an indented tree */
:root {{
  --bg: #f6f7f9; --panel: #ffffff; --fg: #1c2330; --muted: #5d6676; --line: #d9dee6; --accent: #23508f;
  --json: #2f6fbf; --pdf: #5b9be0; --html: #9cc3ee; --legacy: #d08a2b; --qdrant: #2f9a8a; --mysql: #8a6cc4;
  --misc: #9aa3b0; --none: #c8463d; --segfg: #ffffff;
  --display: "Source Serif 4", Georgia, "Times New Roman", serif;
  --body: "Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg: #12161d; --panel: #1a2029; --fg: #e4e8ee; --muted: #9aa4b3; --line: #2c3440; --accent: #8db7ef;
  --json: #3c7ccc; --pdf: #4f8bd0; --html: #6e9fd6; --legacy: #c98a35; --qdrant: #2f9184; --mysql: #8669bd;
  --misc: #6c7584; --none: #c4544b; --segfg: #ffffff; color-scheme: dark; }} }}
:root[data-theme="dark"] {{
  --bg: #12161d; --panel: #1a2029; --fg: #e4e8ee; --muted: #9aa4b3; --line: #2c3440; --accent: #8db7ef;
  --json: #3c7ccc; --pdf: #4f8bd0; --html: #6e9fd6; --legacy: #c98a35; --qdrant: #2f9184; --mysql: #8669bd;
  --misc: #6c7584; --none: #c4544b; --segfg: #ffffff; color-scheme: dark; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--fg); font: 15px/1.55 var(--body); }}
.wrap {{ max-width: 980px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 60px; display: grid; gap: 34px; }}
h1, h2 {{ font-family: var(--display); text-wrap: balance; margin: 0; line-height: 1.2; }}
h1 {{ font-size: 2rem; }} h2 {{ font-size: 1.35rem; }}
p {{ margin: 0; max-width: 68ch; }}
section {{ display: grid; gap: 14px; min-width: 0; }}
.muted {{ color: var(--muted); }} .small {{ font-size: .82rem; }}
.eyebrow {{ font: 600 .72rem/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); }}
code {{ font-family: var(--mono); font-size: .84em; overflow-wrap: anywhere; }}
.num {{ font-family: var(--mono); font-variant-numeric: tabular-nums; white-space: nowrap; }}
.big {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }}
.big div {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 16px; display: grid; gap: 4px; align-content: start; }}
.big b {{ font: 700 2.1rem/1.1 var(--display); font-variant-numeric: tabular-nums; }}
.big .k-main b {{ color: var(--json); }} .big .k-leg b {{ color: var(--legacy); }}
.bar {{ display: flex; height: 54px; border-radius: 4px; overflow: hidden; gap: 2px; background: var(--line); }}
.seg {{ min-width: 3px; display: flex; align-items: center; justify-content: center; color: var(--segfg); font: 600 .75rem/1.1 var(--mono); text-align: center; padding: 0 4px; overflow: hidden; }}
.c-json {{ background: var(--json); }} .c-pdf {{ background: var(--pdf); }} .c-html {{ background: var(--html); color: #10223a; }}
.c-legacy {{ background: var(--legacy); }} .c-qdrant {{ background: var(--qdrant); }} .c-mysql {{ background: var(--mysql); }}
.c-misc {{ background: var(--misc); }} .c-none {{ background: var(--none); }}
.legend {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(270px, 1fr)); gap: 6px 18px; }}
.legend li {{ display: grid; grid-template-columns: 14px 1fr auto; gap: 2px 8px; align-items: baseline; }}
.legend li .muted {{ grid-column: 2 / 4; font-size: .8rem; }}
.sw {{ width: 12px; height: 12px; border-radius: 2px; display: inline-block; }}
.tree {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 14px 16px; overflow-x: auto; font: .84rem/1.75 var(--mono); }}
.tree ul {{ list-style: none; margin: 0; padding-left: 20px; border-left: 1px solid var(--line); }}
.tree > ul {{ padding-left: 0; border: 0; }}
.tree li {{ overflow-wrap: anywhere; }}
.tree .b {{ font-weight: 600; color: var(--accent); }}
.tree .m {{ color: var(--muted); }}
.tablebox {{ overflow-x: auto; background: var(--panel); border: 1px solid var(--line); border-radius: 6px; }}
table {{ border-collapse: collapse; width: 100%; font-size: .86rem; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
th {{ font: 600 .72rem/1.2 var(--mono); letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }}
tr:last-child td {{ border-bottom: 0; }}
.note {{ border-left: 3px solid var(--accent); padding: 4px 0 4px 14px; display: grid; gap: 8px; }}
</style></head><body><div class="wrap">

<header style="display:grid;gap:10px">
  <span class="eyebrow">Experiment 44 · listed {S['listed_on']} · {n(S['requests'])} list requests</span>
  <h1>What is in the Mandumah buckets</h1>
  <p class="muted">The AWS profile sees three buckets. <code>{SRC}</code> holds the documents,
  <code>{QDR}</code> holds the search-index snapshots and database dumps, and the third is CloudTrail's access log.
  Every key was listed; nothing was downloaded except three tiny Qdrant manifests and two small sample files.</p>
</header>

<section>
  <span class="eyebrow">How many documents</span>
  <div class="big">
    <div class="k-main"><b>{n(D['main']['ids'])}</b><span>documents with Azure's PDF <em>and</em> JSON</span><span class="muted small">every one has both; {n(docs['ext']['.html'])} also have an HTML view</span></div>
    <div class="k-leg"><b>{n(D['legacy']['ids'])}</b><span>more in <code>legacy/</code>, PDF only</span><span class="muted small">no Azure JSON yet; only {O['main_and_legacy']} are also in the main set</span></div>
    <div><b>{n(O['union'])}</b><span>distinct documents in all</span><span class="muted small">same id scheme in both; plus {O['union_all'] - O['union']} test-only ids in <code>legacy-test/</code></span></div>
  </div>
</section>

<section>
  <span class="eyebrow">Storage, to scale · {gb(all_total)} in all</span>
  <div class="bar" role="img" aria-label="Storage split across the buckets">{bar}</div>
  <ul class="legend">{legend}</ul>
</section>

<section>
  <h2>The folders</h2>
  <div class="tree"><ul>
   <li><span class="b">s3://{SRC}/</span> <span class="m">eu-north-1 · {n(docs['objects'] + leg['objects'] + lt['objects'] + 2)} objects · {gb(src_total)}</span>
    <ul>
     <li>&lt;id&gt;/ <span class="m">× {n(D['main']['ids'])} folders · {gb(docs['bytes'])} · uploaded {docs['first'][:10]} → {docs['last'][:10]}</span>
      <ul>
       <li>&lt;id&gt;.pdf <span class="m">{n(docs['ext']['.pdf'])} · {gb(xb['.pdf'])}</span></li>
       <li>&lt;id&gt;.json <span class="m">{n(D['main']['ids'])} · {gb(xb['.json'])} (Azure layout JSON)</span></li>
       <li>&lt;id&gt;.html <span class="m">{n(docs['ext']['.html'])} · {gb(xb['.html'])} (reading view)</span></li>
       <li>&lt;id&gt;.gemini.title.json <span class="m">{n(gem)} · title + authors, written Sep 2026</span></li>
      </ul></li>
     <li>legacy/&lt;id&gt;/&lt;id&gt;.pdf <span class="m">{n(leg['objects'])} · {gb(leg['bytes'])} · uploaded {leg['first'][:10]} → {leg['last'][:10]}</span></li>
     <li>legacy-test/&lt;id&gt;/ <span class="m">{n(D['legacy-test']['ids'])} folders · {gb(lt['bytes'])} · {lt['first'][:10]} · {O['legacy_test_in_legacy']} of them are in legacy/</span></li>
     <li>metadata/metadata_final.xml.gz <span class="m">{gb(meta['bytes'])} · the catalogue</span></li>
     <li>metrics.txt <span class="m">607 B · an old batch report</span></li>
    </ul></li>
   <li><span class="b">s3://{QDR}/</span> <span class="m">eu-west-1 · {qd['objects'] + my['objects']} objects · {gb(qdr_total)}</span>
    <ul>
     <li>qdrant/&lt;collection&gt;/&lt;collection&gt;-…-&lt;date&gt;.snapshot <span class="m">3 snapshots + 3 manifests · {gb(qd['bytes'])} · Glacier Instant Retrieval</span></li>
     <li>mysql/ai_search_feedback-&lt;timestamp&gt;.sql.gz <span class="m">{my['objects']} daily dumps · {gb(my['bytes'])} · {my['first'][:10]} → {my['last'][:10]}</span></li>
    </ul></li>
   <li><span class="b">s3://{TRAIL}/</span> <span class="m">{n(tr['objects'])} CloudTrail log files · {gb(tr['bytes'])} · {tr['first'][:10]} → {tr['last'][:10]} · no documents</span></li>
  </ul></div>
</section>

<section>
  <h2>Key patterns</h2>
  <p class="muted">A document id is <code>JJJJ-VVV-III-AAA</code>: journal, volume, issue, article. {n(comma)} ids
  ({100 * comma / D['main']['ids']:.1f}%) carry a comma where an issue or volume is joint, e.g. <code>0339-000-018,019-008</code>.
  The folder name and the file name are always the same id.</p>
  <div class="tablebox"><table>
   <thead><tr><th>Pattern</th><th>Files</th><th>What it is</th><th>Example</th></tr></thead>
   <tbody>{prow}</tbody></table></div>
</section>

<section>
  <h2>Catalogue against bucket</h2>
  <p>The catalogue (<code>metadata_final.xml.gz</code>, {n(C['records'])} records) names {n(C['pdf_stems'])} PDF ids.
  More than half of those are <b>dissertations</b>: {n(fam['dissertation:none'])} chapter PDFs of {n(C['dissertation_records'])} theses
  (journal codes 98xx, ids like <code>9802-001-001-0001-1</code>). <b>None of them is in the bucket.</b></p>
  <p>The other {n(art_total)} ids are articles. This is where they are:</p>
  <div class="bar" role="img" aria-label="Catalogue articles by location">{cbar}</div>
  <ul class="legend">
   <li><i class="sw c-pdf"></i><b>main folders</b><span class="num">{n(fam['article:main'])}</span><span class="muted">PDF + Azure JSON</span></li>
   <li><i class="sw c-legacy"></i><b>legacy/ only</b><span class="num">{n(fam['article:legacy'])}</span><span class="muted">PDF, no JSON</span></li>
   <li><i class="sw c-none"></i><b>nowhere</b><span class="num">{n(fam['article:none'])}</span><span class="muted">spread over {n(C['article_missing_journals'])} journals</span></li>
  </ul>
  <div class="note">
   <p><b>Experiment 43's missing draws.</b> Of the {M43['drawn']} catalogue articles 43 drew at random, {M43['missing']} were not in the main folders.
   <b>{len(M43['in_legacy'])} of those are in <code>legacy/</code></b> under the same key pattern (PDF only), e.g. {e(missing_leg)}.
   The other {len(M43['nowhere'])} are nowhere in the bucket: {e(nowhere)} (two of them are dissertations).</p>
   <p>The other way round, {n(C['bucket_not_in_catalogue_main'])} main documents and {n(C['bucket_not_in_catalogue_legacy'])} legacy PDFs have no catalogue entry.</p>
   <p>Experiment 19's listing of {S['exp19']['listed']} had {n(S['exp19']['ids'])} main folders; today's is the same set, id for id
   ({S['exp19']['gone']} gone, {S['exp19']['new']} new). The newest main file dates from {docs['last'][:10]}.</p>
  </div>
</section>

<section>
  <h2>Qdrant backups</h2>
  <p class="muted">Three collection snapshots (Qdrant 1.7.4), taken one per night on 30 Sep – 2 Oct 2026, read from their manifests.
  Every collection uses 1536-dimension cosine vectors; the two named <code>mandumah_*</code> also carry sparse vectors and
  document fields. Next to them sit {my['objects']} nightly dumps of a MySQL database <code>ai_search_feedback</code>, growing from
  {gb(MYSQL_MIN)} to {gb(S['mysql']['newest_bytes'])}.</p>
  <div class="tablebox"><table>
   <thead><tr><th>Collection</th><th>Taken</th><th>Size</th><th>Points</th><th>Vectors</th><th>Fields</th></tr></thead>
   <tbody>{''.join(qrows)}</tbody></table></div>
</section>

<footer class="muted small">Made by <code>experiments/44_bucket_map</code>: list44.py (list), analyze44.py (count), render44.py (this page).
Listing cost: {n(S['requests'])} ListObjectsV2 requests, about ${S['requests'] * 0.005 / 1000:.3f}.</footer>
</div></body></html>
"""
(OUT / "bucket_map.html").write_text(page, encoding="utf-8")
print(OUT / "bucket_map.html")
