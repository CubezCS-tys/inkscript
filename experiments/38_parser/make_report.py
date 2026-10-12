"""Experiment 38: the owner's page -> out/report.html (pictures linked from out/pages/*/shots and out/report_files/).

    /home/yassine/inkscript/.venv/bin/python make_report.py
"""
from __future__ import annotations

import json
from html import escape

import cv2

from common import OUT, gold, page_image, pages

RF = OUT / "report_files"


def h(s):
    return escape(str(s if s is not None else ""))


def pct(v, d=1):
    return "–" if v is None else f"{100 * v:.{d}f}%"


def ci(x, d=1):
    v, (lo, hi) = x
    return f"{pct(v, d)} <span class=ci>[{pct(lo, d)}–{pct(hi, d)}]</span>"


def line_crop(pid, box, name, pad=14):
    img = page_image(pid)
    H, W = img.shape[:2]
    x0, y0, x1, y1 = (int(v) for v in box)
    c = img[max(0, y0 - pad):min(H, y1 + pad), max(0, x0 - pad):min(W, x1 + pad)]
    RF.mkdir(exist_ok=True)
    if c.size:
        s = min(1.0, 900 / c.shape[1])
        c = cv2.resize(c, (int(c.shape[1] * s), int(c.shape[0] * s)))
        cv2.imwrite(str(RF / name), c, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return f"report_files/{name}"


def main():
    S = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    M = {m["page_id"]: m for m in json.loads((OUT / "measures.json").read_text(encoding="utf-8"))}
    P = {p["page_id"]: p for p in pages()}
    js = {}
    if (OUT / "judge_sides.jsonl").exists():
        for l in (OUT / "judge_sides.jsonl").read_text().splitlines():
            r = json.loads(l)
            js[r["key"]] = r
    jo = [json.loads(l) for l in (OUT / "judge_objects.jsonl").read_text().splitlines()] \
        if (OUT / "judge_objects.jsonl").exists() else []
    spot = {}
    sd = OUT / "spotcheck"
    if sd.exists():
        for f in sd.glob("*.json"):
            try:
                spot[f.stem] = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                pass
    J = S["judge_sides"]
    W = J["winner"]
    tg, tc = S["text_gold"], S["corrections"]
    o = []
    o.append(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Parser on hard pages</title>
<link rel=stylesheet href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<style>
:root{{--bg:#faf8f4;--fg:#1d1b18;--mut:#6b665d;--card:#fff;--rule:#e2ddd3;--good:#1f7a3a;--bad:#b3261e;--acc:#2b5d9c}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#16150f;--fg:#ece8df;--mut:#a39d91;--card:#211f19;--rule:#3a372e;--good:#6cc58a;--bad:#f2867c;--acc:#8db4ea}}}}
:root[data-theme=dark]{{--bg:#16150f;--fg:#ece8df;--mut:#a39d91;--card:#211f19;--rule:#3a372e;--good:#6cc58a;--bad:#f2867c;--acc:#8db4ea}}
body{{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0;padding:0 16px}}
main{{max-width:1180px;margin:0 auto;padding:24px 0 80px}}
h1{{font-size:1.9rem;margin:.2em 0}} h2{{margin-top:2.2em;border-bottom:1px solid var(--rule);padding-bottom:.2em}}
.lead{{font-size:1.15rem}} .ci{{color:var(--mut);font-size:.85em}} .mut{{color:var(--mut)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:16px 0}}
.card{{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:12px 14px}}
.card b{{display:block;font-size:1.6rem}}
figure{{margin:14px 0;background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:10px}}
figure img{{width:100%;height:auto;display:block}} figcaption{{font-size:.92rem;margin-top:6px}}
.win-new{{color:var(--good);font-weight:600}} .win-old{{color:var(--bad);font-weight:600}}
table.t{{border-collapse:collapse;font-size:.92rem;margin:10px 0;overflow-x:auto;display:block}}
table.t td,table.t th{{border:1px solid var(--rule);padding:4px 8px;text-align:left;vertical-align:top}}
.ar{{direction:rtl;font-family:"Noto Naskh Arabic","Amiri",serif;font-size:1.05rem}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} @media(max-width:700px){{.pair{{grid-template-columns:1fr}}}}
.ok{{color:var(--good)}} .no{{color:var(--bad)}} details{{margin:8px 0}}
.tbl table{{border-collapse:collapse;direction:rtl}} .tbl td,.tbl th{{border:1px solid #888;padding:2px 6px;font-size:.9rem}}
.dots{{background:rgba(255,200,0,.25)}}
</style></head><body><main>
<h1>Azure's words in a model's layout: the hardest pages rebuilt</h1>
<p class=mut>Experiment 38 · 2026-10-12 · {S['hard']} of the hardest yardstick pages and the {S['gold_done']} finished gold pages · Gemini spent ${S['gemini_usd']:.2f} of the $6 cap</p>
""")
    verdict = "Partly yes"
    o.append(f"""<h2>Is this useful?</h2>
<p class=lead><b>{verdict}.</b> A blind judge, shown the scan and the two rebuilds in a random order, preferred the
<b>new</b> page on <b>{W.get('new', 0)} of {J['pages']}</b> hard pages ({pct(J['new_wins_ci'][0], 0)}–{pct(J['new_wins_ci'][1], 0)}),
the old one on {W.get('old', 0)}, a tie on {W.get('tie', 0)}; mean closeness {J['grade_new']} vs {J['grade_old']} of 5.
The text is Azure's: poured into the new layout it keeps Azure's words (word-bag error on gold
{ci(tg['joined']['bag_err'])} vs Azure {ci(tg['azure']['bag_err'])}). The model correction is <b>not</b> good enough to switch on:
of {sum(tc['gold_verdicts'].values())} changes it made on gold pages, {tc['gold_verdicts'].get('right', 0)} were right and
{tc['gold_verdicts'].get('wrong', 0)} wrong.</p>
<div class=cards>
<div class=card>new page preferred<b>{W.get('new', 0)}/{J['pages']}</b><span class=mut>old {W.get('old', 0)}, tie {W.get('tie', 0)}</span></div>
<div class=card>text on gold, characters wrong (in reading order)<b>{pct(tg['corrected']['cer'][0])}</b><span class=mut>Azure as is {pct(tg['azure']['cer'][0])}; joined {pct(tg['joined']['cer'][0])}</span></div>
<div class=card>tables rebuilt with rules<b>{S['assignment']['tables']}</b><span class=mut>{S['assignment']['table_cells_azure']} of {S['assignment']['table_cells']} cells filled from Azure</span></div>
<div class=card>pictures placed<b>{S['assignment']['figures']}</b><span class=mut>formulas typeset: {S['assignment']['formulas']}</span></div>
<div class=card>corrections right on gold<b>{pct(tc['gold_precision'], 0)}</b><span class=mut>[{pct(tc['gold_precision_ci'][0], 0)}–{pct(tc['gold_precision_ci'][1], 0)}], word errors {tc['gold_word_errors_before']} → {tc['gold_word_errors_after']}</span></div>
</div>""")
    # aspects
    asp = J["aspects"]
    o.append("<table class=t><tr><th>aspect (judge)</th><th>new better</th><th>old better</th><th>same</th><th>n/a</th></tr>")
    for k in ("text", "layout", "headings", "tables", "pictures", "formulas", "lists_notes", "latin"):
        c = asp.get(k, {})
        o.append(f"<tr><td>{k}</td><td class=ok>{c.get('new', 0)}</td><td class=no>{c.get('old', 0)}</td>"
                 f"<td>{c.get('same', 0)}</td><td>{c.get('n/a', 0)}</td></tr>")
    o.append("</table>")
    # side by side
    o.append("<h2>Scan, old rebuild, new rebuild</h2><p class=mut>Left the scan, middle experiment 35's layout-faithful "
             "PDF, right the new one. The judge's words under each (it saw the two rebuilds in a shuffled order).</p>")
    order = sorted((p for p in P.values() if p["hard"]), key=lambda p: (p["primary"], p["page_id"]))
    for p in order:
        pid = p["page_id"]
        r = js.get(pid)
        w = (r or {}).get("unblinded", {}).get("winner")
        cls = "win-new" if w == "new" else ("win-old" if w == "old" else "")
        sp = spot.get(pid)
        spn = ""
        if sp:
            faults = sp.get("faults") or []
            spn = "<br><b>Spot-check:</b> " + "; ".join(h(f.get("what") if isinstance(f, dict) else f)
                                                       for f in faults[:4]) if faults else "<br><b>Spot-check:</b> no fault noted"
        o.append(f"""<figure><a href="pages/{h(pid)}/shots/three.jpg"><img loading=lazy src="pages/{h(pid)}/shots/three.jpg" alt="{h(pid)}"></a>
<figcaption><b>{h(pid)}</b> · {h(p['why'])} · judge: <span class="{cls}">{h(w or 'not judged')}</span>
{('(new ' + str(r['grade_new']) + '/5, old ' + str(r['grade_old']) + '/5) — ' + h(r['why'])) if r else ''}{spn}
· <a href="pages/{h(pid)}/shots/layout_overlay.jpg">blocks and order</a> · <a href="pages/{h(pid)}/edition/{h(pid)}/{h(pid)}.onecol.pdf">one-column PDF</a>
· <a href="pages/{h(pid)}/edition/{h(pid)}/{h(pid)}.html">reading page</a></figcaption></figure>""")
    # corrections
    o.append(f"""<h2>Correction with understanding: what it did</h2>
<p>Gemini 3.8 Flash saw each block's crop and Azure's text and could propose only clear OCR errors; rules fixed in
advance threw out low-confidence, long, vowel-mark and deleting edits. Proposals: {tc['proposed']}, applied
{tc['applied']} ({', '.join(f'{k} {v}' for k, v in sorted(tc['by_status'].items()))}). On the {S['gold_done']} gold pages
each applied change was scored on its own line against the truth: <b>right {tc['gold_verdicts'].get('right', 0)}, wrong
{tc['gold_verdicts'].get('wrong', 0)}, neutral {tc['gold_verdicts'].get('neutral', 0)}</b>; word errors on those lines
{tc['gold_word_errors_before']} before, {tc['gold_word_errors_after']} after. Pages it made worse:
{', '.join(tc['pages_worse']) or 'none'}.</p>
<table class=t><tr><th>kind</th><th>right</th><th>wrong</th><th>neutral</th></tr>""")
    for k, c in sorted(tc["gold_by_kind"].items(), key=lambda x: -sum(x[1].values())):
        o.append(f"<tr><td>{h(k)}</td><td class=ok>{c.get('right', 0)}</td><td class=no>{c.get('wrong', 0)}</td>"
                 f"<td>{c.get('neutral', 0)}</td></tr>")
    o.append("</table>")
    n = 0
    for verdict in ("right", "wrong"):
        o.append(f"<h3>{'Good' if verdict == 'right' else 'Bad'} changes (gold pages)</h3><div class=pair>")
        k = 0
        for pid, m in M.items():
            ct = m.get("correction_truth")
            if not ct:
                continue
            L = json.loads((OUT / "pages" / pid / "layout.json").read_text(encoding="utf-8"))
            words = {w["id"]: w for b in L["blocks"] for w in b["words"]}
            byline = {}
            for w in words.values():
                byline.setdefault(w["line"], []).append(w["box"])
            for e in ct["edits"]:
                if e["verdict"] != verdict or k >= 8:
                    continue
                bx = byline.get(e["line"])
                if not bx:
                    continue
                box = [min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx)]
                n += 1
                k += 1
                src = line_crop(pid, box, f"corr{n}.jpg")
                o.append(f"""<figure><img src="{src}" alt="line"><figcaption><span class=ar>{h(e['before'])} → <b>{h(e['after'])}</b></span>
· {h(e['kind'])}, confidence {e['confidence']} · <i>{h(e['reason'])}</i><br><span class=mut>truth:</span> <span class=ar>{h(e['truth'])}</span><br><span class=mut>{h(pid)}</span></figcaption></figure>""")
        o.append("</div>")
    # tables and formulas
    o.append(f"""<h2>Tables and formulas next to the scan</h2>
<p>Tables: dots.mocr's grid, each cell filled with Azure's words where they could be found ({S['assignment']['table_cells_azure']} of
{S['assignment']['table_cells']} cells; the rest keep dots' text, <span class=dots>shaded</span>). Judge (Gemini 3.1 Pro, blind, against the crop): new tables
{S['judge_table']['new']} of 5 vs dots' own {S['judge_table']['dots']} ({S['judge_table']['new_better']} better, {S['judge_table']['new_worse']} worse, n={S['judge_table']['n']}).
Formulas: dots' LaTeX checked on the crop by Gemini 3.1 Pro; judged {S['judge_formula']['new']} vs dots' {S['judge_formula']['dots']}
({S['judge_formula']['new_better']} better, {S['judge_formula']['new_worse']} worse, n={S['judge_formula']['n']}).</p>""")
    from master import apply_corrections, corrected_words
    shown = 0
    for r in jo:
        pid, bid = r["key"].split(":")
        pdir = OUT / "pages" / pid
        L = json.loads((pdir / "layout.json").read_text(encoding="utf-8"))
        b = next(x for x in L["blocks"] if x["id"] == bid)
        g = r.get("grades") or {}
        gd = lambda k: (g.get(k) or {}).get("grade")
        if r["kind"] == "table":
            C = json.loads((pdir / "corrections.json").read_text()) if (pdir / "corrections.json").exists() else None
            rep = apply_corrections(L, C)
            rows = []
            for rr in b["rows"]:
                cs = []
                for c in rr["cells"]:
                    t = " ".join(w["text"] for w in corrected_words(c["words"], rep)) if c.get("words") else c.get("text", "")
                    sp = (f' colspan="{c["colspan"]}"' if c["colspan"] > 1 else "") + (f' rowspan="{c["rowspan"]}"' if c["rowspan"] > 1 else "")
                    cs.append(f"<td{sp}{' class=dots' if not c.get('words') else ''}>{h(t)}</td>")
                rows.append("<tr>" + "".join(cs) + "</tr>")
            right = f"<div class='tbl ar'><table>{''.join(rows)}</table></div>"
        else:
            tex = r["cands"]["new"]
            right = f"<div class=tex data-tex=\"{h(tex)}\"></div><pre style='white-space:pre-wrap;font-size:.8rem'>{h(tex)}</pre>"
        o.append(f"""<figure><div class=pair><div><img src="pages/{h(pid)}/{h(b['crop'])}" alt="crop"></div><div>{right}</div></div>
<figcaption>{h(r['key'])} · {r['kind']} · judge: new {gd('new')}/5, dots {gd('dots')}/5 {'(identical)' if r['same'] else ''}
· {h((g.get('new') or {}).get('note'))}</figcaption></figure>""")
        shown += 1
    # pictures
    o.append("<h2>Pictures placed in the document</h2><div class=pair>")
    for pid, m in M.items():
        if m["stats"].get("figures") and (OUT / "pages" / pid / "shots" / "new_layout.jpg").exists():
            o.append(f"<figure><img loading=lazy src='pages/{h(pid)}/shots/new_layout.jpg' alt='{h(pid)}'><figcaption>{h(pid)}: "
                     f"{m['stats']['figures']} picture(s) cropped from the scan, captions kept</figcaption></figure>")
    o.append("</div>")
    # numbers
    o.append("<h2>The numbers</h2><p class=mut>95% intervals by bootstrap over pages. On gold pages against the owner's "
             "truth; on the other pages against Azure's draft (agreement only: there 0% means 'same as Azure').</p>")
    for name, d in (("gold pages (truth)", S["text_gold"]), ("other pages (vs Azure)", S["text_vs_azure"])):
        o.append(f"<h3>{name}</h3><table class=t><tr><th>reading</th><th>chars wrong, in order</th><th>chars wrong, folded</th>"
                 "<th>words wrong</th><th>word bag error (order-free)</th><th>words missing</th><th>line order kept</th></tr>")
        for rd, lab in (("azure", "Azure as is"), ("joined", "Azure in dots' layout"), ("corrected", "… after correction"),
                        ("dots", "dots.mocr alone")):
            x = d[rd]
            o.append(f"<tr><td>{lab}</td><td>{ci(x['cer'], 2)}</td><td>{ci(x['cer_folded'], 2)}</td><td>{ci(x['wer'])}</td>"
                     f"<td>{ci(x['bag_err'])}</td><td>{ci(x['bag_missing'])}</td><td>{ci(x['order'])}</td></tr>")
        o.append("</table>")
    a = S["assignment"]
    o.append(f"""<h3>Every Azure word in one place</h3><p>{a['azure_words']} Azure words; every page placed each word exactly once
({a['every_word_once_pages']}/{S['pages']} pages). {a['azure_words'] - a['leftover_words']} fell in a dots block ({a['words_near']} of them
by nearness), {a['leftover_words']} were leftovers given blocks of their own, {a['words_in_pictures']} are inside pictures (kept as the
picture's own text). Of {a['dots_blocks']} dots blocks, {a['dots_blocks_no_words']} got no Azure word: {a['dots_blocks_kept_from_dots']}
kept with dots' text (Kraken saw ink there), {a['dots_blocks_dropped']} dropped. Kraken, the net: {a['kraken_outside_blocks']} Kraken lines lie in
no block, {a['azure_lines_no_kraken']} Azure lines lie on no Kraken line, {a['dots_text_no_ink']} dots-only texts have no ink line.</p>""")
    # spot-check
    if spot:
        from collections import Counter
        c = Counter()
        for v in spot.values():
            for f in v.get("faults") or []:
                if isinstance(f, dict):
                    c[(f.get("category") or "other", f.get("severity") or "?")] += 1
        o.append(f"<h2>Spot-check (a reviewer looked at every page)</h2><p>{len(spot)} pages reviewed.</p><table class=t>"
                 "<tr><th>fault</th><th>severity</th><th>count</th></tr>")
        for (k, s), v in c.most_common():
            o.append(f"<tr><td>{h(k)}</td><td>{h(s)}</td><td>{v}</td></tr>")
        o.append("</table>")
    o.append("""<script>document.addEventListener('DOMContentLoaded',()=>{document.querySelectorAll('.tex').forEach(e=>{
try{katex.render(e.dataset.tex,e,{displayMode:true,throwOnError:false})}catch(x){}})})</script></main></body></html>""")
    (OUT / "report.html").write_text("\n".join(o), encoding="utf-8")
    print("report:", OUT / "report.html")


if __name__ == "__main__":
    main()
