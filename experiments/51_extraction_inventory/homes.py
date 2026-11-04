"""Where each inventory item lives (owner, 2026-10-22): JATS (the article as a document), ALTO (the page as an
object), or the platform database (connections, judgments, quality). Some live in two.
    python3 homes.py   -> out/homes.json, out/homes.html"""
import html, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
items = json.load(open(HERE / "inventory.json"))
items = items if isinstance(items, list) else items["items"]

PLATFORM_WORDS = re.compile(r"\bflags?\b|\btrust\b|\bWC\b|platform|database|registry|\bdb\b", re.I)
ALTO = re.compile(r"\bALTO\b", re.I)
JATS_EL = re.compile(r"(^|[\s/(\[])(article|front|back|body|sec|p|fn|fig|table|contrib|aff|ref|element-citation|mixed-citation|"
                     r"article-meta|title-group|kwd|abstract|trans|pub-date|history|permissions|funding|xref|disp|"
                     r"named-content|styled-content|italic|bold|sup|sub|sc|underline|custom-meta|conf|product|"
                     r"related-article|verse|list|def-list|app|ack|glossary|caption|label|alt-text|subj-group|"
                     r"article-categories|person-group|source|edition|date-in-citation|@|journal|issue|volume|fpage|"
                     r"page-range|self-uri|contrib-id|string-name|name|role|author-notes|corresp|email|uri|"
                     r"element kind|front / back|sec nesting|article-type|table-wrap)", re.I)

def home(it):
    j = it.get("jats") or ""
    homes = []
    if JATS_EL.search(re.sub(r"\bALTO\b[^;/]*", "", j)) and not re.fullmatch(r"\s*ALTO.*", j):
        homes.append("JATS")
    if ALTO.search(j):
        homes.append("ALTO")
    if PLATFORM_WORDS.search(j) or it["group"] in ("RAG-specific",) and "flag" in it["field"].lower():
        homes.append("Platform")
    if not homes:
        homes = ["JATS"]
    return homes

ENTITY = [  # a field that points to a thing in the world is also connected in the platform (most specific first)
    (r"conference", "event"),
    (r"journal|issn", "journal"),
    (r"affiliation|institution|university|faculty|department|college", "institution"),
    (r"publisher|funder", "organisation"),
    (r"quran|aya|sura", "Quran index (sura:aya)"),
    (r"hadith", "hadith collection + number"),
    (r"keyword|subject|classification|jel", "term"),
    (r"country|city|place of", "place"),
    (r"translator|editor of the text|supervisor|author|byline|person|orcid|researcher id|corresponding|death date", "person"),
    (r"reference|cited work|referenced|back reference|ibid|المرجع|edition|manuscript", "work (and edition)"),
]

def platform_link(it):
    f, g = it["field"].lower(), it["group"]
    if g in ("visual-and-styling", "page-furniture", "body-structure", "tables-figures-math", "RAG-specific"):
        return ""
    if re.search(r"number of|count|voice|availability|contribution|front matter|note kind", f):
        return ""
    for pat, ent in ENTITY[:8]:          # specific things, matched on the item itself
        if re.search(pat, f):
            return ent
    if g == "authors-and-affiliations":
        return "person"
    if g == "references":
        return "person" if re.search(r"author|translator|editor|death", f) else "work (and edition)"
    if re.search(r"translator|supervisor|\bauthor\b", f):
        return "person"
    return ""

rows = []
for it in items:
    h = home(it)
    rows.append(dict(id=it.get("id"), group=it["group"], field=it["field"], homes=h, slot=it.get("jats") or "",
                     platform=platform_link(it), today=it["today"], needs=it["needs"],
                     priority=it.get("prompt_priority")))

PLATFORM_ONLY = [
    ("Who is who", "each byline and referenced author linked to one person (authority id, ORCID attached), with method, score and who decided", "persons, person_authorities, person_names, authorships"),
    ("Which institution", "each affiliation linked to one institution and its parent, with ROR id attached", "institutions, institution_names, affiliation_links"),
    ("Which work and edition", "references grouped into works, editions under works, links to Mandumah records or a DOI", "cited_works, cited_work_members, citation_links, work_relations"),
    ("Which journal", "journal names in references linked to journal entities; title history; ISSNs", "journals, journal_titles, journal_issns"),
    ("«المرجع السابق» resolved", "each ibid / op. cit. pointed to its earlier reference", "citation_mentions (full_mention_pk)"),
    ("Citations (incoming) and metrics", "cited by, times cited, h-index, journal metrics: always computed from the links, never stored as numbers", "views (v_times_cited …)"),
    ("Corrections and their history", "every person's decision, with who, when, why and the evidence seen; re-applied on every build", "the Desk (PostgreSQL): decisions, tasks, notes, releases; patches"),
    ("Quality record", "flags, the judge's findings, retries, trust per value, reviews", "flags, judge_findings, patches, reviews, blocks.trust"),
    ("Both readings of the text", "Azure's reading and the fix, the printed form and a proposed misprint correction (D30)", "text_corrections"),
    ("Metadata from every source", "printed, corrected (D33), catalogue, person: each value with its source and which one is shown", "metadata_assertions"),
    ("Catalogue problems for Mandumah", "errors found in the catalogue, with evidence, to send to the cataloguers", "catalogue_reports"),
    ("Runs, costs and provenance", "which run, prompt, model and cost made each reading", "runs, versions, model_calls, load_events"),
    ("Stable ids", "ids that never change across rebuilds; retired ids point to the survivor", "id_registry, merged_ids"),
    ("Search", "full-text index over every piece; links to the RAG's vectors", "search_units, search_fts, vector_points"),
]
# In the platform database (experiment 47's field audit, 2026-10-22: audit_fields47.py -> out/field_audit.json): for
# each field, is its slot filled in the masters, and where the platform database holds it
AUDIT = HERE.parents[0] / "47_platform_v2" / "out" / "field_audit.json"
aud = {f["id"]: f for f in json.load(open(AUDIT))["fields"]} if AUDIT.exists() else {}
for r in rows:
    a = aud.get(r["id"])
    if a:
        r["in_platform"] = a["in_platform"]
        r["platform_where"] = a["platform_now"] if a["filled"] else None
        r["masters_filled"] = {"600": a["articles_600"], "j0130": a["articles_j0130"]}
json.dump(rows, open(HERE / "out" / "homes.json", "w"), ensure_ascii=False, indent=1)

from collections import Counter
print(Counter("+".join(r["homes"]) for r in rows))


def esc(x):
    return html.escape(str(x or ""))

STATE = {"extracted-well": ("captured", "ok"), "extracted-partly": ("partly", "warn"),
         "kept-as-text-only": ("text only", "mute"), "not-extracted": ("not yet", "bad")}
groups = {}
for r in rows:
    groups.setdefault(r["group"], []).append(r)
cnt = Counter()
for r in rows:
    for h in r["homes"]:
        cnt[h] += 1
n_link = sum(1 for r in rows if r["platform"])
n_filled = sum(1 for r in rows if r.get("masters_filled") and (r["masters_filled"]["600"] or r["masters_filled"]["j0130"]))
n_in = sum(1 for r in rows if r.get("in_platform"))
body = []
for g, rs in groups.items():
    trs = []
    for r in rs:
        st, tone = STATE.get(r["today"], (r["today"], "mute"))
        homes = "".join(f'<span class="pill h-{h.lower()}">{h}</span>' for h in r["homes"])
        link = f'<span class="pill h-platform">{esc(r["platform"])}</span>' if r["platform"] else '<span class="dim">—</span>'
        star = ' <span class="new" title="added in prompt v3.5">new in v3.5</span>' if r["priority"] == 1 else ""
        if "in_platform" not in r:
            db = '<span class="dim">—</span>'
        elif r["in_platform"]:
            mf = r.get("masters_filled") or {}
            db = (f'<span class="st ok">in the platform</span><div class="slot">{esc(r["platform_where"])}</div>'
                  f'<div class="dim" style="font-size:11px">filled in {mf.get("600", 0)} of the 600 · {mf.get("j0130", 0)} of j0130</div>')
        elif r.get("platform_where"):
            db = f'<span class="st bad">not loaded</span><div class="slot">{esc(r["platform_where"])}</div>'
        else:
            db = '<span class="st mute">slot empty</span>'
        trs.append(f'<tr><td>{esc(r["field"])}{star}</td><td>{homes}<div class="slot">{esc(r["slot"])}</div></td>'
                   f'<td>{link}</td><td><span class="st {tone}">{esc(st)}</span></td><td class="dim">{esc(r["needs"])}</td>'
                   f'<td>{db}</td></tr>')
    body.append(f'<section class="card"><h2>{esc(g)} <span class="dim">· {len(rs)}</span></h2><div class="tbl"><table>'
                f'<thead><tr><th>Item</th><th>Stored in the files</th><th>Connected in the platform to</th><th>Today</th><th>Needs</th><th>In the platform db (2026-10-22)</th></tr></thead>'
                f'<tbody>{"".join(trs)}</tbody></table></div></section>')
plat = "".join(f'<tr><td><b>{esc(a)}</b></td><td>{esc(b)}</td><td class="slot">{esc(c)}</td></tr>' for a, b, c in PLATFORM_ONLY)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Where Everything Is Stored</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Noto+Naskh+Arabic&display=swap">
<style>
:root{{--bg:#f9fafb;--card:#fff;--fg:#111827;--muted:#6b7280;--line:#e5e7eb;--accent:#4f46e5;color-scheme:light}}
body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 Inter,"Noto Naskh Arabic",system-ui,sans-serif}}
main{{max-width:76rem;margin:0 auto;padding:24px 16px;display:grid;gap:16px}}
h1{{font-size:22px;margin:0}} h2{{font-size:15px;margin:0 0 8px}} .lead{{color:var(--muted);max-width:70ch;margin:4px 0 0}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 20px;box-shadow:0 1px 2px rgba(0,0,0,.04)}}
.three{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr))}}
.three .card h2{{display:flex;gap:8px;align-items:center}}
.tbl{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:13px}}
th{{text-align:left;color:var(--muted);font-weight:500;background:#f9fafb;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}}
td{{padding:6px 8px;border-bottom:1px solid #f3f4f6;vertical-align:top}}
.slot{{font:11px ui-monospace,monospace;color:var(--muted);margin-top:2px;word-break:break-word}}
.pill{{display:inline-block;font-size:11px;font-weight:600;padding:1px 7px;border-radius:999px;margin:0 4px 2px 0}}
.h-jats{{background:#eef2ff;color:#3730a3}} .h-alto{{background:#ecfeff;color:#155e75}} .h-platform{{background:#f0fdf4;color:#166534}}
.st{{font-size:12px;font-weight:500;padding:1px 7px;border-radius:6px;white-space:nowrap}}
.st.ok{{background:#dcfce7;color:#166534}} .st.warn{{background:#fef3c7;color:#92400e}} .st.mute{{background:#f3f4f6;color:#4b5563}} .st.bad{{background:#fee2e2;color:#991b1b}}
.dim{{color:var(--muted)}} .new{{font-size:11px;color:#4f46e5;border:1px solid #c7d2fe;border-radius:6px;padding:0 5px;margin-left:4px;white-space:nowrap}}
</style></head><body><main>
<header><p class="dim" style="margin:0;font-size:12px">INKSCRIPT · EXPERIMENT 51 · PRIVATE (127.0.0.1)</p>
<h1>Where everything is stored</h1>
<p class="lead">Every item worth extracting, and its home: the article file (JATS), the page file (ALTO), and, for anything that points to a real thing, its connection in the platform database. The files say what is on the paper; the platform says what it connects to and how sure we are. Draft of 2026-10-22; the JATS homes of the v3.5 fields will be checked against the prompt agent's mapping.</p></header>
<div class="three">
<section class="card"><h2><span class="pill h-jats">JATS</span> the article as a document · {cnt['JATS']}</h2><p class="dim" style="margin:0">Metadata, authors, affiliations as printed, structure, text, notes, tables, figures, references with all their fields. Standard, portable, safe to export.</p></section>
<section class="card"><h2><span class="pill h-alto">ALTO</span> the page as an object · {cnt['ALTO']}</h2><p class="dim" style="margin:0">Every word's box on the scan, styling, page furniture (heads, numbers, show-through, adverts), stamps and handwriting as regions, page problems.</p></section>
<section class="card"><h2><span class="pill h-platform">Platform</span> connections and judgments · {n_link} linked fields + {len(PLATFORM_ONLY)} own</h2><p class="dim" style="margin:0">Who is who, which work, which institution and journal, citations and metrics, corrections, quality. Correctable without touching the files.</p></section>
</div>
<section class="card"><h2>In the platform database (2026-10-22)</h2><p class="dim" style="margin:0">{n_in} of the {n_filled} items whose slot is filled in the masters (the 600 and journal 0130's 126) are loaded into the platform database (Datasette :8003, the Desk). The last column says where; the field-by-field audit is experiment 47's <code>out/field_audit.md</code>.</p></section>
<section class="card"><h2>What lives only in the platform</h2><div class="tbl"><table><thead><tr><th>What</th><th>What it holds</th><th>Tables</th></tr></thead><tbody>{plat}</tbody></table></div></section>
{"".join(body)}
</main></body></html>"""
(HERE / "out" / "homes.html").write_text(page)
print("wrote out/homes.html")
