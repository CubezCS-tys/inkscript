"""Experiment 51: the owner's page, out/inventory.html: one static file (inventory.json embedded, inline JS, Google
Fonts only), in the Desk's light admin look. Private: Mandumah's text in the examples, so it is served on 127.0.0.1
only (copy: ../49_correction_desk/web/public/inventory/index.html)."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = json.load(open(HERE / "inventory.json"))
items = D["items"]
N = len(items)
st = Counter(i["today"] for i in items)
gaps = [i for i in items if i["prompt_priority"]]
p1 = sum(1 for i in gaps if i["prompt_priority"] == 1)

ASK = [
    ("What kind of document this is", "research, review, editorial, book review, report, conference paper, thesis summary, interview, news, translation, issue front matter. Today all 600 say <i>research-article</i>."),
    ("About the article itself", "a conference's name, place and dates (today they fall into the subtitle); a thesis's degree and university; the book a review is about; the original of a translation; the part number of a series («(٤)»)."),
    ("Authors", "who is the corresponding author; ORCID and other ids; an English byline marked as the same person as the Arabic one (doubled in 11 articles); several affiliations per author; faculty apart from department; the starred author note on page 1."),
    ("Each cited work, the missing parts", "the editor (تحقيق, 89 articles), translator, edition (ط, 101 articles), the author's death date (ت …هـ), the calendar of each year (Hijri in 93 articles), the cited page apart from the page range, access dates, a thesis's degree, a manuscript's library and folio."),
    ("Notes under tables and figures", "table notes and «المصدر:» source lines as their own block tied to the table (136 lines today read as paragraphs); a note's kind: author's, translator's, editor's."),
    ("Each picture's kind", "chart, photograph, map, diagram, manuscript facsimile, logo, stamp, portrait, cartoon, table-as-image."),
    ("On the page", "library stamps, readers' handwriting and marginalia kept apart; scan problems (cut-off edge, blur, missing or out-of-order page)."),
    ("Text only eyes can fix", "an honorific ligature (ﷺ) to its Unicode glyph; inline formulas inside Arabic sentences and letters Azure drops in fully vowelled lines (v3.4's two content lines)."),
]

GROUPS = list(dict.fromkeys(i["group"] for i in items))
STATES = ["extracted-well", "extracted-partly", "kept-as-text-only", "not-extracted"]
LABEL = {"extracted-well": "captured well", "extracted-partly": "partly", "kept-as-text-only": "text only", "not-extracted": "not captured"}

bars = []
for g in GROUPS:
    c = Counter(i["today"] for i in items if i["group"] == g)
    n = sum(c.values())
    segs = "".join(f'<span class="seg s-{s}" style="width:{100*c[s]/n:.1f}%" title="{LABEL[s]}: {c[s]}"></span>' for s in STATES if c[s])
    bars.append(f'<div class="bar-row"><button class="bar-name" data-group="{g}">{g}</button><div class="bar">{segs}</div><span class="bar-n">{n}</span></div>')

import re
bdi = lambda x: re.sub(r"([«(]?[\u0600-\u06FF\uFDF0-\uFDFF][\u0600-\u06FF\uFDF0-\uFDFF\u064B-\u0652 …:.]*[»)]?)", r'<bdi style="font-family:\'Noto Naskh Arabic\',serif">\1</bdi>', x)
ask_html = "".join(f"<li><b>{t}</b> — {bdi(d)}</li>" for t, d in ASK)
data = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Extraction Inventory</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Naskh+Arabic:wght@400;600&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #f3f4f6; --card: #ffffff; --line: #e5e7eb; --line2: #d1d5db; --ink: #111827; --ink2: #374151; --muted: #6b7280;
  --accent: #4f46e5; --accent-d: #4338ca; --accent-l: #eef2ff;
  --well: #059669; --well-l: #d1fae5; --part: #b45309; --part-l: #fef3c7; --text: #4b5563; --text-l: #e5e7eb;
  --not: #b91c1c; --not-l: #fee2e2;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--ink); font: 14px/1.5 Inter, system-ui, sans-serif; }}
header {{ background: var(--card); border-bottom: 1px solid var(--line); }}
.wrap {{ max-width: 1180px; margin: 0 auto; padding: 0 16px; }}
header .wrap {{ padding-top: 18px; padding-bottom: 16px; }}
.crumb {{ color: var(--accent); font-weight: 600; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }}
h1 {{ font-size: 22px; margin: 4px 0 4px; }}
.sub {{ color: var(--muted); margin: 0; max-width: 820px; }}
main .wrap {{ padding-top: 18px; padding-bottom: 60px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 16px; }}
.card {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }}
.kpi .n {{ font-size: 28px; font-weight: 700; line-height: 1.1; }}
.kpi .l {{ color: var(--muted); font-size: 12px; }}
.kpi.well .n {{ color: var(--well); }} .kpi.part .n {{ color: var(--part); }} .kpi.text .n {{ color: var(--text); }} .kpi.not .n {{ color: var(--not); }}
.kpi.ask .n {{ color: var(--accent); }}
.two {{ display: grid; grid-template-columns: 1.25fr 1fr; gap: 12px; margin-bottom: 18px; }}
@media (max-width: 860px) {{ .two {{ grid-template-columns: 1fr; }} }}
h2 {{ font-size: 15px; margin: 0 0 8px; }}
.ask ol {{ margin: 0; padding-left: 20px; }} .ask li {{ margin: 0 0 7px; color: var(--ink2); }}
.ask .foot {{ color: var(--muted); font-size: 12px; margin-top: 8px; }}
.bar-row {{ display: grid; grid-template-columns: 170px 1fr 30px; align-items: center; gap: 8px; margin: 5px 0; }}
.bar-name {{ all: unset; cursor: pointer; font-size: 12.5px; color: var(--ink2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.bar-name:hover {{ color: var(--accent); }}
.bar {{ display: flex; height: 12px; border-radius: 6px; overflow: hidden; background: var(--line); }}
.seg {{ display: block; height: 100%; }}
.s-extracted-well {{ background: var(--well); }} .s-extracted-partly {{ background: #f59e0b; }} .s-kept-as-text-only {{ background: #9ca3af; }} .s-not-extracted {{ background: #ef4444; }}
.bar-n {{ font-size: 12px; color: var(--muted); text-align: right; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--muted); margin-top: 8px; }}
.legend i {{ display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }}
.filters {{ position: sticky; top: 0; z-index: 5; background: var(--bg); padding: 10px 0; border-bottom: 1px solid var(--line); margin-bottom: 12px; }}
.frow {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
.frow + .frow {{ margin-top: 8px; }}
input[type=search], select {{ font: inherit; border: 1px solid var(--line2); border-radius: 8px; padding: 7px 10px; background: var(--card); color: var(--ink); }}
input[type=search] {{ flex: 1 1 260px; min-width: 0; }}
.chip {{ font: inherit; font-size: 12.5px; border: 1px solid var(--line2); background: var(--card); color: var(--ink2); border-radius: 999px; padding: 4px 11px; cursor: pointer; }}
.chip.on {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
.count {{ color: var(--muted); font-size: 12.5px; margin-left: auto; }}
.group-h {{ display: flex; align-items: baseline; gap: 10px; margin: 22px 0 8px; }}
.group-h h3 {{ margin: 0; font-size: 16px; }} .group-h span {{ color: var(--muted); font-size: 12.5px; }}
.list {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 10px; }}
@media (max-width: 420px) {{ .list {{ grid-template-columns: 1fr; }} }}
.item {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; min-width: 0; }}
.item.gap1 {{ border-left: 3px solid var(--accent); }}
.item .top {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }}
.item .f {{ font-weight: 600; font-size: 14px; }}
.pill {{ font-size: 11px; font-weight: 600; border-radius: 999px; padding: 2px 8px; white-space: nowrap; }}
.p-extracted-well {{ background: var(--well-l); color: var(--well); }}
.p-extracted-partly {{ background: var(--part-l); color: var(--part); }}
.p-kept-as-text-only {{ background: var(--text-l); color: var(--text); }}
.p-not-extracted {{ background: var(--not-l); color: var(--not); }}
.p-A {{ background: var(--accent-l); color: var(--accent-d); }}
.p-B {{ background: #f3f4f6; color: var(--ink2); border: 1px solid var(--line); }}
.p-pr {{ background: var(--accent); color: #fff; }}
.p-pr2 {{ background: #c7d2fe; color: var(--accent-d); }}
.p-pr3 {{ background: #f3f4f6; color: var(--muted); }}
.meta {{ font-size: 12px; color: var(--muted); display: flex; flex-wrap: wrap; gap: 4px 12px; }}
.meta code {{ font: 11.5px ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--ink2); background: #f9fafb; border: 1px solid var(--line); border-radius: 4px; padding: 0 4px; overflow-wrap: anywhere; }}
.ev {{ font-size: 12.5px; color: var(--ink2); overflow-wrap: anywhere; }}
.ex {{ background: #f9fafb; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }}
.ex .t {{ font-family: "Noto Naskh Arabic", "Geeza Pro", serif; font-size: 16px; line-height: 1.7; unicode-bidi: plaintext; overflow-wrap: anywhere; }}
.ex .src {{ font-size: 11.5px; color: var(--muted); margin-top: 2px; direction: ltr; }}
.note {{ font-size: 12.5px; color: var(--muted); font-style: italic; }}
.empty {{ color: var(--muted); padding: 30px 0; text-align: center; }}
footer {{ color: var(--muted); font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
<header><div class="wrap">
  <div class="crumb">inkscript · experiment 51 · private (127.0.0.1)</div>
  <h1>Everything worth extracting from a scanned article</h1>
  <p class="sub">Before the big Gemini read (about $106k for a million articles, prices double on 1 December), each article should be read once.
  <b>A</b> = needs eyes or judgment, so it must be in that one read. <b>B</b> = code can take it later, for free, from the stored text.
  Counted in the 600 masters (prompt v3.3), 2026-10-22.</p>
</div></header>
<main><div class="wrap">
  <div class="cards">
    <div class="card kpi"><div class="n">{N}</div><div class="l">things worth extracting</div></div>
    <div class="card kpi well"><div class="n">{st['extracted-well']}</div><div class="l">captured well today</div></div>
    <div class="card kpi part"><div class="n">{st['extracted-partly']}</div><div class="l">captured partly</div></div>
    <div class="card kpi text"><div class="n">{st['kept-as-text-only']}</div><div class="l">kept as text, not as a field</div></div>
    <div class="card kpi not"><div class="n">{st['not-extracted']}</div><div class="l">not captured</div></div>
    <div class="card kpi ask"><div class="n">{p1}</div><div class="l">eyes-or-judgment things to add to the prompt first</div></div>
  </div>
  <div class="two">
    <div class="card ask"><h2>Add to the prompt before the big run (eyes or judgment, missing today)</h2>
      <ol>{ask_html}</ol>
      <div class="foot">{len(gaps)} group-A gaps in all: {p1} to add first (marked with an indigo edge below), {sum(1 for i in gaps if i['prompt_priority']==2)} to test first (styling: italic, bold, super/subscript), {sum(1 for i in gaps if i['prompt_priority']==3)} to leave.</div>
    </div>
    <div class="card"><h2>Where each group stands</h2>
      {''.join(bars)}
      <div class="legend"><span><i class="s-extracted-well"></i>captured well</span><span><i class="s-extracted-partly"></i>partly</span><span><i class="s-kept-as-text-only"></i>text only</span><span><i class="s-not-extracted"></i>not captured</span></div>
      <h2 style="margin-top:16px">Surprises</h2>
      <ul style="margin:0;padding-left:18px;color:var(--ink2)">
        <li>190 of the 600 hold Azure's Persian look-alike letters (ی ک for ي ى ك): 1,889 words, e.g. <span style="font-family:'Noto Naskh Arabic',serif">«المدمنیین الرسمی»</span>. The fold exists in <code>src/inkscript/text.py</code> but experiment 43 never calls it.</li>
        <li>Every master says <i>research-article</i>, news pages and thesis summaries included.</li>
        <li>Funding and conflict-of-interest statements: none found. ORCID: 1 article. E-mails: 64.</li>
      </ul>
    </div>
  </div>

  <div class="filters">
    <div class="frow">
      <input type="search" id="q" placeholder="Search fields, JATS, evidence, examples…" aria-label="Search">
      <select id="grp" aria-label="Group"><option value="">All groups</option>{''.join(f'<option>{g}</option>' for g in GROUPS)}</select>
      <span class="count" id="count"></span>
    </div>
    <div class="frow" id="states">
      {''.join(f'<button class="chip" data-state="{s}">{LABEL[s]}</button>' for s in STATES)}
      <span style="width:8px"></span>
      <button class="chip" data-needs="A">A · eyes / judgment</button>
      <button class="chip" data-needs="B">B · code later</button>
      <span style="width:8px"></span>
      <button class="chip" data-gap="1">add to prompt first</button>
      <button class="chip" data-gap="any">all A gaps</button>
    </div>
  </div>
  <div id="out"></div>
  <footer>Sources: experiments/51_extraction_inventory (inventory.json, count_*.py). Counts are “articles / occurrences” of the 600; regex counts show how often a thing exists, they are not a precision study.</footer>
</div></main>
<script id="data" type="application/json">{data}</script>
<script>
const ITEMS = JSON.parse(document.getElementById('data').textContent);
const LABEL = {json.dumps(LABEL)};
const GROUPS = {json.dumps(GROUPS)};
const f = {{states: new Set(), needs: new Set(), gap: null, q: '', grp: ''}};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
function match(i) {{
  if (f.grp && i.group !== f.grp) return false;
  if (f.states.size && !f.states.has(i.today)) return false;
  if (f.needs.size && !f.needs.has(i.needs)) return false;
  if (f.gap === '1' && i.prompt_priority !== 1) return false;
  if (f.gap === 'any' && !i.prompt_priority) return false;
  if (f.q) {{
    const hay = [i.field, i.why, i.wos_tag, i.jats, i.evidence, i.note, i.group, i.example && i.example.text, i.example && i.example.stem].join(' ').toLowerCase();
    if (!f.q.split(/\\s+/).every(w => hay.includes(w))) return false;
  }}
  return true;
}}
function card(i) {{
  const pr = i.prompt_priority ? `<span class="pill ${{i.prompt_priority===1?'p-pr':'p-pr'+i.prompt_priority}}">${{['','add to prompt','test first','leave'][i.prompt_priority]}}</span>` : '';
  const ex = i.example ? `<div class="ex"><div class="t" dir="auto">${{esc(i.example.text)}}</div><div class="src">${{esc(i.example.stem)}} · page ${{esc(i.example.page ?? '?')}}${{i.example.context ? ' · ' + esc(i.example.context) : ''}}</div></div>` : '';
  return `<div class="item${{i.prompt_priority===1?' gap1':''}}">
    <div class="top"><span class="f">${{esc(i.field)}}</span></div>
    <div class="top"><span class="pill p-${{i.today}}">${{LABEL[i.today]}}</span><span class="pill p-${{i.needs}}">${{i.needs==='A'?'A · eyes / judgment':'B · code later'}}</span>${{pr}}</div>
    <div class="meta"><span>for: ${{esc(i.why)}}</span>${{i.wos_tag?`<span>WoS <code>${{esc(i.wos_tag)}}</code></span>`:''}}<span>JATS <code>${{esc(i.jats)}}</code></span></div>
    <div class="ev">${{esc(i.evidence)}}</div>
    ${{ex}}
    ${{i.note?`<div class="note">${{esc(i.note)}}</div>`:''}}
  </div>`;
}}
function render() {{
  const shown = ITEMS.filter(match);
  document.getElementById('count').textContent = `${{shown.length}} of ${{ITEMS.length}} items`;
  let h = '';
  for (const g of GROUPS) {{
    const xs = shown.filter(i => i.group === g);
    if (!xs.length) continue;
    const well = xs.filter(i => i.today === 'extracted-well').length;
    h += `<div class="group-h"><h3>${{esc(g)}}</h3><span>${{xs.length}} items · ${{well}} captured well</span></div><div class="list">${{xs.map(card).join('')}}</div>`;
  }}
  document.getElementById('out').innerHTML = h || '<div class="empty">Nothing matches these filters.</div>';
}}
document.getElementById('q').addEventListener('input', e => {{ f.q = e.target.value.trim().toLowerCase(); render(); }});
document.getElementById('grp').addEventListener('change', e => {{ f.grp = e.target.value; render(); }});
document.querySelectorAll('[data-state]').forEach(b => b.onclick = () => {{ const s = b.dataset.state; f.states.has(s) ? f.states.delete(s) : f.states.add(s); b.classList.toggle('on'); render(); }});
document.querySelectorAll('[data-needs]').forEach(b => b.onclick = () => {{ const s = b.dataset.needs; f.needs.has(s) ? f.needs.delete(s) : f.needs.add(s); b.classList.toggle('on'); render(); }});
document.querySelectorAll('[data-gap]').forEach(b => b.onclick = () => {{
  const on = f.gap === b.dataset.gap; f.gap = on ? null : b.dataset.gap;
  document.querySelectorAll('[data-gap]').forEach(x => x.classList.toggle('on', !on && x === b)); render(); }});
document.querySelectorAll('.bar-name').forEach(b => b.onclick = () => {{ f.grp = b.dataset.group; document.getElementById('grp').value = f.grp; render(); document.querySelector('.filters').scrollIntoView({{behavior:'smooth'}}); }});
render();
</script>
</body>
</html>
"""

(HERE / "out").mkdir(exist_ok=True)
(HERE / "out" / "inventory.html").write_text(HTML, encoding="utf-8")
print("wrote", HERE / "out" / "inventory.html", len(HTML), "bytes")
