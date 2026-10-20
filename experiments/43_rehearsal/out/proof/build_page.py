"""Build proof.html (one page for the owner) and proof.md from the judgement files in this folder."""
import json, html
S = json.load(open('stats.json')); P = [json.loads(l) for l in open('pages.jsonl')]
D = json.load(open('detector.json')); PR = json.load(open('patches_review.json'))
C = json.load(open('cites_score.json')); CD = {x['i']: x for x in json.load(open('cites_draw.json'))['sample']}
IB = json.load(open('ibid_score.json')); M = json.load(open('meta_score.json')); MD = json.load(open('meta_draw.json'))
W = [json.loads(l) for l in open('words.jsonl')]; CO = json.load(open('consistency.json'))
pct = lambda k, n: f"{100*k/n:.0f}%"
ci = lambda c: f"{100*c[0]:.0f}–{100*c[1]:.0f}%"
e = html.escape
v = S['verdicts']
cards = []
for x, d in zip(P, D):
    img = x['image']; th = 'thumb/' + img.split('/')[-1]
    det = ('flagged: ' + ', '.join(d['flags'])) if d['flags'] else 'not flagged'
    if d['judge']: det += ' · judge: ' + ', '.join(f"{r}{'/'+t if t else ''}" for g, r, t in d['judge'])
    cards.append(f'''<figure class="card {x['verdict']}"><a href="{img}" data-full="{img}" data-cap="{e(x['stem'])} p{x['page']} — {x['verdict']}: {e(x['why'])}"><img src="{th}" loading="lazy" alt="scan beside our page, {e(x['stem'])} page {x['page']}"></a>
<figcaption><b>{e(x['stem'])} p{x['page']}</b> <span class="tag {x['verdict']}">{x['verdict']}</span><br>{e(x['why'])}<br><small>{e(det)}</small></figcaption></figure>''')
KN = {'word_errors':'small word / punctuation slips (e.g. a stray ")" in «…)», split words in pull quotes)','table_picture':'table cells or picture text missing','format_loss':'layout lost (glosses flattened, a bidi line order)',
      'metadata':'page-1 metadata slip (honorific in name, Hijri year)','notes_links':'note markers not linked to notes','missing_text':'printed text missing (a page number)',
      'verse':'verse halves not split','wrong_kind':'wrong block kind','wrong_order':'reading order (line-end fragments as blocks)'}
krows = ''.join(f"<tr><td>{e(KN.get(k,k))}</td><td class=n>{o['n']}</td><td class=n>{pct(o['n'],60)}</td><td class=n>{ci(o['ci'])}</td></tr>" for k, o in S['kinds'].items())
krows += "<tr><td>text not on the scan (show-through, invented)</td><td class=n>0</td><td class=n>0%</td><td class=n>0–6%</td></tr>"
pf = C['per_field']
frows = ''.join(f"<tr><td>{k}</td>" + ''.join(f"<td class=n>{pf[k].get(c,0)}</td>" for c in ('right','loose','missing','wrong')) + "</tr>" for k in ['authors','title','source','year','volume','issue','pages','publisher','place','link','other'] if k in pf)
mf = M['per_field']
mrows = ''.join(f"<tr><td>{k}</td>" + ''.join(f"<td class=n>{mf[k].get(c,0)}</td>" for c in ('right','loose','wrong','unverified')) + "</tr>" for k in ['title','authors','affiliation','year','pages'])
def plist(d):
    return ''.join(f"<li><span class='tag {'right' if a=='right' else ('serious' if a in ('wrong','no gain') else 'minor')}'>{e(a)}</span> <b>{e(k)}</b> — {e(w)}</li>" for k, (a, w) in d.items())
jtri = {'0201':'0201_p001','0700':'0700_p003','0732':'0732_p003','0849':'0849_p004','1080':'1080_p009','1539':'1539_p002'}
def tri(name, cap):
    return f'<figure class="wide"><a href="auto/tri_{name}.jpg" data-full="auto/tri_{name}.jpg" data-cap="{e(cap)}"><img src="thumb/tri_{name}.jpg" loading="lazy" alt="{e(cap)}"></a><figcaption>{e(cap)}</figcaption></figure>'
def sidefig(stem4, p, cap):
    f = f"side_{stem4}_p{p:03d}.jpg"
    return f'<figure class="wide"><a href="side/{f}" data-full="side/{f}" data-cap="{e(cap)}"><img src="thumb/{f}" loading="lazy" alt="{e(cap)}"></a><figcaption>{e(cap)}</figcaption></figure>'
usd = 31.943; arts = 300; pages = 3404
gbp = lambda u: u * 1.2 / 1.33
page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Exam Proof Pack</title>
<style>
:root{{--bg:#f7f5f0;--fg:#1d1d1b;--mut:#6b6a66;--card:#fff;--line:#dedad2;--ok:#2f7d4f;--okbg:#e3f2e8;--mi:#a86b00;--mibg:#fbf0d9;--se:#b3261e;--sebg:#fbe3e1;--acc:#2d5c8a}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161614;--fg:#ecebe6;--mut:#a3a19b;--card:#21211e;--line:#3a3934;--ok:#6cc58f;--okbg:#1d3326;--mi:#e0a640;--mibg:#382c14;--se:#f08a82;--sebg:#3d1c1a;--acc:#8fb8e0}}}}
:root[data-theme="dark"]{{--bg:#161614;--fg:#ecebe6;--mut:#a3a19b;--card:#21211e;--line:#3a3934;--ok:#6cc58f;--okbg:#1d3326;--mi:#e0a640;--mibg:#382c14;--se:#f08a82;--sebg:#3d1c1a;--acc:#8fb8e0}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:16px}}h1{{font-size:1.7rem;margin:.4em 0}}h2{{margin-top:2em;border-bottom:1px solid var(--line);padding-bottom:.2em}}
.verdict{{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--acc);padding:14px 18px;border-radius:8px;font-size:1.08rem}}
.big{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:16px 0}}
.big div{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}}.big b{{display:block;font-size:1.7rem;line-height:1.1}}.big small{{color:var(--mut)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}}
.card{{margin:0;background:var(--card);border:1px solid var(--line);border-top:5px solid var(--line);border-radius:8px;overflow:hidden}}
.card.right{{border-top-color:var(--ok)}}.card.minor{{border-top-color:var(--mi)}}.card.serious{{border-top-color:var(--se)}}
.card img,.wide img{{width:100%;display:block}}.card figcaption{{padding:8px 10px;font-size:.85rem}}.card small{{color:var(--mut)}}
.tag{{font-size:.75rem;padding:1px 7px;border-radius:9px;white-space:nowrap}}.tag.right{{background:var(--okbg);color:var(--ok)}}.tag.minor{{background:var(--mibg);color:var(--mi)}}.tag.serious{{background:var(--sebg);color:var(--se)}}
table{{border-collapse:collapse;width:100%;background:var(--card);font-size:.92rem}}td,th{{border:1px solid var(--line);padding:5px 8px;text-align:left;vertical-align:top}}td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.tw{{overflow-x:auto}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}@media(max-width:760px){{.two{{grid-template-columns:1fr}}}}
.wide{{margin:0 0 12px;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}}.wide figcaption{{padding:6px 10px;font-size:.85rem}}
ul li{{margin:.25em 0}}.mut{{color:var(--mut)}}.filters button{{margin:0 6px 8px 0;padding:4px 10px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}}
dialog{{max-width:96vw;max-height:94vh;padding:0;border:0;background:var(--card);color:var(--fg)}}dialog img{{max-width:96vw;max-height:84vh;display:block}}dialog p{{margin:6px 10px;font-size:.9rem}}
.key span{{margin-right:12px}}
</style></head><body><main>
<h1>Exam proof pack: the second 300</h1>
<p class="mut">An independent check of the held-out exam (300 unseen articles, 3,404 pages, frozen pipeline v3.3, Argon, Batch). Every page, citation and article below came from a seeded random draw, not chosen by hand. I looked at each scan myself. No paid model calls. 2026-10-20.</p>
<div class="verdict"><b>Verdict: the product works on unseen documents, but it is not yet error-free enough to skip a safety net, and the current net misses the worst errors.</b>
On 60 random pages, <b>35 were fully right, 23 had only small slips and 2 had a serious error</b>. Both serious errors are table cells left empty that are printed on the scan. The words themselves are very good: 0 wrong words out of 1,532 checked letter by letter. Reading order, notes, verse and pictures were right on almost every page.
The weak spots are the author field in the metadata (honorifics kept in names, extra "authors") and loose or missing citation fields. The bigger issue is that <b>neither serious page was flagged, so the judge never saw them</b>. The judge's automatic edits never made a page worse, but only 9 of 14 were clearly right.</div>
<div class="big">
<div><b>{v['right']['n']}/60</b>pages fully right<br><small>{ci(v['right']['ci'])}</small></div>
<div><b>{v['serious']['n']}/60</b>pages with a serious error<br><small>{ci(v['serious']['ci'])} · both tables</small></div>
<div><b>0 / 1,532</b>wrong words<br><small>error ≤ 0.25% (95%)</small></div>
<div><b>{C['citations_all_right']}/80</b>citations fully right<br><small>{ci(S['cites']['fully_ci'])} · 0 wrong fields</small></div>
<div><b>15/20</b>ibid. / المرجع السابق resolved right<br><small>{ci(S['ibid']['right_ci'])}</small></div>
<div><b>{M['fully_right']}/30</b>articles with all metadata right<br><small>{ci(S['meta']['fully_ci'])} · pages 30/30</small></div>
<div><b>0/2</b>serious pages caught by flags or judge</div>
<div><b>${usd/arts:.3f}</b>per article<br><small>£{gbp(usd/arts):.3f} incl. VAT · ${usd/pages:.4f}/page</small></div>
<div><b>≈ ${usd/arts*1e6/1000:.0f}k</b>per million articles<br><small>≈ £{gbp(usd/arts)*1e6/1000:.0f}k incl. VAT</small></div>
</div>

<h2>60 random pages: the scan beside our page</h2>
<p class="key mut"><span class="tag right">right</span>everything on the page is right <span class="tag minor">minor</span>a small slip a reader may not notice <span class="tag serious">serious</span>content lost or wrong. Click a page to enlarge it. Seed 20261020: 30 random articles with 2 random pages each; 2 one-page articles were topped up with one page from 2 more random articles.</p>
<div class="filters"><button data-f="all">all 60</button><button data-f="serious">serious</button><button data-f="minor">minor</button><button data-f="right">right</button></div>
<div class="grid" id="grid">{''.join(cards)}</div>

<h2>What kind of slips, on how many pages</h2>
<p class="mut">The share of the 60 pages with at least one problem of each kind (a page can count under several kinds), with 95% Wilson intervals. The pages come in pairs from the same article, so the true intervals are a bit wider.</p>
<div class="tw"><table><tr><th>problem</th><th>pages</th><th>share</th><th>95% interval</th></tr>{krows}</table></div>
<p>Not counted per page because it affects every page: <b>inline styling is not kept anywhere</b>. There is no italic, subscript or superscript in any of the 300 JATS files, so chemistry formulas (NH₄OAc → NH4OAc), italic book titles and superscript markers are flattened.</p>

<h2>Words, compared line by line</h2>
<p>I compared 10 of the 60 pages with the scan word by word (seed 20261021): {S['words']['words']:,} words. <b>No word was wrong.</b> There were 13 spelling-level differences (0.85%, 95% interval 0.5–1.4%). Twelve came from Azure normalising the printed spelling: a bare ان stored as أن (8 times on one page), or a kasra stored as tanween. One came from the model adding a hamza (فاحيت → فأحيت). Printer misprints were kept and marked as sic. The model also repaired many words Azure had misread, for example in fully vowelled poetry (تمشي, وخطوها, تصونهم) and in a blurred banner byline (تص محمدقارويت → شعر: محمد هارون الحلو).</p>

<h2>Citations</h2>
<div class="two"><div>
<p>80 random parsed works out of 3,838 (seed 20261022), from reference lists and footnotes. I compared every field with the printed citation.</p>
<div class="tw"><table><tr><th>field</th><th>right</th><th>loose</th><th>missing</th><th>wrong</th></tr>{frows}</table></div>
<p class="mut">"Loose" means the field is there but imperfect, for example a Hijri year in the year field, Jr. inside the surname or an accusative name form. "Missing" means the field is printed but not captured, for example a translator, an editor (تحقيق), an edition, an article title or a URL. One footnote invented a citation: a book mentioned in passing, not cited. No field held a wrong value.</p>
</div><div>
<p><b>ibid. / op. cit. / المرجع السابق</b>: 20 random back references in platform.db out of 510 (seed 20261023).</p>
<ul><li><span class="tag right">15 right</span>14 linked to the right earlier citation, plus 1 correctly left unresolved because the full citation is not in the article.</li>
<li><span class="tag minor">4 missed</span>The full citation was a few notes up but had a different shape: a co-author first (مجاور), an op. cit. chain (Debbasch ×2) or a full name in a much earlier note (عصام ضياء الدين).</li>
<li><span class="tag serious">1 wrong</span>"Mejri (2000) Op. Cit." linked to Mejri 2008 although the 2000 work is in the list.</li></ul>
<p class="mut">8 of the 20 came from one article with long Ibid. chains (0486), all right.</p>
</div></div>

<h2>Metadata on page 1</h2>
<div class="two"><div>
<p>30 random articles (seed 20261024). I compared each field with page 1 of the scan and with the catalogue (marc records in platform.db).</p>
<div class="tw"><table><tr><th>field</th><th>right</th><th>loose</th><th>wrong</th><th>can't tell</th></tr>{mrows}</table></div>
</div><div><ul>
<li><b>Pages: 30/30 right.</b> All 16 D33 page corrections in these articles are sensible (for example, a printed range of 158 changed to 165 for a 15-page scan). In 2 articles the catalogue is wrong and we are right: 0821 (catalogue p.1, printed p.194) and 1289 (catalogue 51–52, printed صفحة 9).</li>
<li><b>Authors are the weak field.</b> Honorifics and professions are kept in names (أ.د., الاستاذ, المحامى) in 5 articles. In 1036, the Latin spelling of the author and the translator became two extra authors. In 1633, the 8 rapporteurs named at the end became the authors of a colloquium report (the catalogue says "Editorial Board").</li>
<li><b>Year:</b> 0266 prints 1409هـ/1989م and our year field holds 1409. Hijri years appear in the year field without a calendar mark, which happens in more articles (0764, 0596).</li>
<li>Titles: 2 loose. A book review is titled with the reviewed book, and a section label (افتتاحية العدد) is prepended to a title.</li></ul></div></div>

<h2>The safety net: flags and the judge</h2>
<p>On my 60 pages the code raised flags on 13. I judged 8 of those 13 fully right, so most flags point at pages that are fine. The 2 serious pages and 18 of the 23 minor pages were not flagged, and the judge only sees flagged pages plus 50 random ones. <b>Recall of my serious problems: 0 of 2 by the flags, 0 of 2 by the judge.</b> On my pages the judge produced only 2 findings: a correct advertisement mark (1539 p2) and a note-link proposal sent to the owner.</p>
<div class="two"><div><h3>All 14 automatic judge edits, before and after</h3><ul>{plist(PR['judge_auto'])}</ul>
<p><b>9 right, 2 partly right, 3 doubtful, 0 wrong.</b> The doubtful ones change one page of an article in a way that contradicts its other pages.</p></div>
<div><h3>All 12 applied page retries</h3><ul>{plist(PR['retries'])}</ul>
<p><b>7 visibly better, 5 no visible change, 0 worse.</b> One retried page (1187 p2) still reads its two columns line by line, interleaved, which is a serious error that the retry did not fix.</p></div></div>
{tri('1539_p002','Judge edit, right: the book advertisement marked as another article (left: scan, middle: before, right: after)')}
{tri('0849_p004','Judge edit, partly right: one show-through line removed, but "PAR منبن ليس قمساءلنا" is still in the paragraph and the table keeps show-through cells')}
{tri('0732_p003','Judge edit, doubtful: the bottom strip unmarked on p3 and p6 only, while the same strip stays "another article" on the other pages')}

<h2>What still fails (with examples)</h2>
<ol>
<li><b>Table cells silently dropped.</b> In 0201 p11, 13 of 60 cells are empty (row numbers) although they are printed. In 0295 p3, 3 numbers are missing. Neither page was flagged.</li>
<li><b>Authors in the metadata</b>: honorifics kept in names, Latin spellings and translators added as authors, rapporteurs listed as authors (see the metadata section).</li>
<li><b>Hijri years</b> in the year field with no calendar mark (1409, 1428, 1429).</li>
<li><b>Quote leftovers</b>: a stray ")" before » (الفلسطيني)»). I counted 408 occurrences of ")»" across the 300 masters.</li>
<li><b>No inline styling</b>: subscripts, superscripts and italics are flattened everywhere.</li>
<li><b>Superscript and roman note markers</b> (i, ii, xiii in a French article) are glued to the note text and not linked to their calls.</li>
<li><b>Interlinear linguistic glosses</b> are flattened into running lines (0753).</li>
<li><b>Calligraphic headline pictures</b> keep no description text (0549 p2: "والنشاط الإسلامي" is not searchable).</li>
<li><b>Page images</b>: 0529's PDF has no embedded Arabic font, so the page image that Gemini and the views see has blank Arabic text. The output is still right because Azure read the PDF's text layer, but the image check was blind on that article.</li>
</ol>
{sidefig('0201',11,'Serious: table 4 has empty cells (row numbers) that are printed on the scan — not flagged')}
{sidefig('0295',3,'Serious: 3 numbers missing from the two tables — not flagged')}
<h3>…and what works, from the same random draw</h3>
{sidefig('0655',2,'Right: 29 fully vowelled verse lines as hemistichs, ~20 Azure misreads of vowelled words repaired')}
{sidefig('0633',1,'Right: a one-page poem, the blurred banner byline restored (شعر: محمد هارون الحلو)')}
{sidefig('0700',9,'Right: a 12-column table with a 3-level header, two charts as pictures with captions')}
{sidefig('0527',5,'Right: display and inline equations as LaTeX')}

<h2>Gold set, run-to-run variance, cost and speed</h2>
<ul>
<li><b>Gold check</b> (<code>gold43.py check</code>): all 5 gold articles are unchanged under today's code (950aa361c0). This checks that the code has not regressed on the first sample. It does not measure accuracy on the exam.</li>
<li><b>Two runs of the same pipeline</b> (v3.3 low, 3 hard articles, 38 pages, from step G0): {CO['total']['words']:,} words were compared. Words placed in a different kind of block: 1. Words present in only one run: 518 (3.6%), almost all on an advertisement page of 1010-006. 6 of 38 pages have a different number of blocks. Against the gold snapshots, two v3.3 runs differ by 9–98 items per article, and the 94 kind differences on 1140 are the same in both runs. In short, a second run moves words around at the edges, mostly on advertisements, and rarely changes what a block is. These 3 articles were picked because the arms disagreed, so typical pages vary less.</li>
<li><b>Cost</b> (from the spend log): run $27.07 (501 requests), judge $4.34 (599 pages), retries $0.54 (15). <b>Total $31.94 = ${usd/arts:.3f} per article (£{gbp(usd/arts):.3f} incl. 20% VAT) = ${usd/pages:.4f} per page (£{gbp(usd/pages):.4f})</b>, so about ${usd/arts*1e6/1000:.0f}k (£{gbp(usd/arts)*1e6/1000:.0f}k) per million articles at 11.3 pages each. The builders note the price doubles from 1 Dec 2026.</li>
<li><b>Speed and failures</b>: each Batch job took 2.4–7 min. The run took 2 h 46 min from launch to the last answer, including a 64-minute laptop reboot. 3 of 491 first-round requests failed (2 cut off at the output limit, 1 malformed JSON). They were asked again in smaller chunks and all 10 retry requests succeeded. All 300 masters are valid.</li>
</ul>
<p class="mut">Files: pages.jsonl (60 judgements), words.jsonl, cites_draw.json + cites_score.json, ibid_score.json, meta_draw.json + meta_score.json, detector.json, patches_review.json, consistency.json, gold_check.txt, stats.json, proof.md. All numbers and seeds are in proof.md.</p>
</main>
<dialog id="dlg"><img alt=""><p></p></dialog>
<script>
const dlg=document.getElementById('dlg');
document.querySelectorAll('a[data-full]').forEach(a=>a.addEventListener('click',ev=>{{ev.preventDefault();dlg.querySelector('img').src=a.dataset.full;dlg.querySelector('p').textContent=a.dataset.cap;dlg.showModal();}}));
dlg.addEventListener('click',()=>dlg.close());
document.querySelectorAll('.filters button').forEach(b=>b.addEventListener('click',()=>{{const f=b.dataset.f;document.querySelectorAll('#grid .card').forEach(c=>c.style.display=(f==='all'||c.classList.contains(f))?'':'none');}}));
</script></body></html>'''
open('proof.html', 'w').write(page)
print('ok', len(page))
