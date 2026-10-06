"""out/report.html for the owner: every accepted correction on the ink, what the judge turned down, the flag
numbers before and after as pictures, the PDF checks. Self-contained (crops inlined), light/dark, phone width.

    python make_report.py
"""
import base64
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

import cv2

from inkscript.enrich.judge import Pages, crop
from inkscript.enrich.quran import quran

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SET = OUT / "set"
ORIG = Path("/home/yassine/inkscript/experiments/24_product/out/set")
AZ = Path("/home/yassine/inkscript/experiments/24_product/out/azure")
E = html.escape
P = Pages()


def img(stem, c, width=520):
    g = P.get(AZ / stem / f"{stem}.pdf", c["page"])
    im = crop(g, c["box"], side=2.5)
    if im.shape[1] > width:
        im = cv2.resize(im, (width, int(im.shape[0] * width / im.shape[1])), interpolation=cv2.INTER_AREA)
    b = base64.b64encode(cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 82])[1].tobytes()).decode()
    return f'<img alt="the printed word on the scan" loading="lazy" src="data:image/jpeg;base64,{b}">'


def verse_html(q, c):
    s, a = (int(x) for x in c["ref"].split(":"))
    text = q.verse_text[(s, a)][1].split()
    mine = {p[2] for p in c.get("verse_pos", []) if p[0] == s and p[1] == a}
    out, i = [], 0
    for wtxt in text:
        if not any("ء" <= ch <= "ي" for ch in wtxt):     # pause marks are their own tokens in Tanzil
            out.append(E(wtxt))
            continue
        out.append(f"<mark>{E(wtxt)}</mark>" if i in mine else E(wtxt))
        i += 1
    return " ".join(out)


def bar(label, value, maxv, fmt, cls=""):
    w = 0 if not maxv else max(0.5, 100 * value / maxv)
    return (f'<div class="bar {cls}"><span class="bl">{E(label)}</span><span class="track"><span class="fill" '
            f'style="width:{w:.1f}%"></span></span><span class="bv">{E(fmt)}</span></div>')


def main():
    q = quran()
    entries = []
    trust_before, trust_after = Counter(), Counter()
    for rp in sorted(SET.glob("w*/native_pdf_report.json")):
        for rep in json.loads(rp.read_text(encoding="utf-8")):
            stem = rep["doc"]
            log = rp.parent / f"{stem}.corrections.json"
            if log.exists():
                for c in json.loads(log.read_text(encoding="utf-8"))["corrections"]:
                    entries.append(dict(c, stem=stem))
            for k in ("words", "flagged", "verified", "corrected"):
                trust_after[k] += rep.get("enrich", {}).get("trust", {}).get(k, 0)
        for rep in json.loads((ORIG / rp.parent.name / "native_pdf_report.json").read_text(encoding="utf-8")):
            for k in ("words", "flagged", "verified"):
                trust_before[k] += rep.get("enrich", {}).get("trust", {}).get(k, 0)
    st = Counter(c["status"] for c in entries)
    kinds = Counter(c["kind"] for c in entries if c["status"] == "applied")
    spend = [json.loads(l) for l in (OUT / "spend.jsonl").read_text().splitlines() if l.strip()]
    by_model = defaultdict(float)
    for s in spend:
        by_model[s["model"]] += s["usd"]
    cal = json.loads((OUT / "calibration.json").read_text(encoding="utf-8")) if (OUT / "calibration.json").exists() else {}
    fe = json.loads((OUT / "flag_eval.json").read_text(encoding="utf-8")) if (OUT / "flag_eval.json").exists() else {}
    ver = json.loads((OUT / "verify_set.json").read_text(encoding="utf-8")) if (OUT / "verify_set.json").exists() else {}
    skipped = json.loads((OUT / "skipped.json").read_text(encoding="utf-8")) if (OUT / "skipped.json").exists() else []

    H = []
    H.append(f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Corrections on the ink</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--card:#fff;--line:#e4e1da;--acc:#2f7d4f;--warn:#b5651d;--bad:#a33;--mark:#fff2a8;--fill:#2f7d4f;--fill2:#c08a2b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#171716;--fg:#ecebe6;--mut:#a3a19b;--card:#21211f;--line:#383733;--acc:#6cc28c;--warn:#e0a25a;--bad:#e07070;--mark:#5a4d12;--fill:#6cc28c;--fill2:#e0b45a}}}}
:root[data-theme="dark"]{{--bg:#171716;--fg:#ecebe6;--mut:#a3a19b;--card:#21211f;--line:#383733;--acc:#6cc28c;--warn:#e0a25a;--bad:#e07070;--mark:#5a4d12;--fill:#6cc28c;--fill2:#e0b45a}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:24px 16px 64px}} h1{{font-size:1.7rem;margin:.2em 0}} h2{{margin-top:2.2em;border-bottom:1px solid var(--line);padding-bottom:.2em}}
.mut{{color:var(--mut)}} .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}} .kpi b{{display:block;font-size:1.6rem}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;overflow:hidden}}
.card img{{max-width:100%;height:auto;display:block;border-radius:6px;background:#fff}}
.ar{{font-family:"Noto Naskh Arabic","Amiri","Traditional Arabic",serif;direction:rtl;font-size:1.25rem}}
.pair{{display:flex;gap:8px;align-items:center;justify-content:flex-end;flex-wrap:wrap;margin:8px 0 4px}}
.was{{text-decoration:line-through;color:var(--bad)}} .now{{color:var(--acc);font-weight:600}}
.verse{{font-size:1.05rem;color:var(--mut);margin:4px 0}} mark{{background:var(--mark);color:inherit;border-radius:3px;padding:0 2px}}
.small{{font-size:.85rem}} .tag{{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:0 8px;font-size:.8rem;margin-right:4px}}
.bar{{display:grid;grid-template-columns:minmax(120px,38%) 1fr auto;gap:8px;align-items:center;margin:6px 0}}
.track{{background:var(--line);height:14px;border-radius:7px;overflow:hidden}} .fill{{display:block;height:100%;background:var(--fill)}}
.bar.b .fill{{background:var(--fill2)}} .bv{{font-variant-numeric:tabular-nums;min-width:5em;text-align:right}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}} td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
.scroll{{overflow-x:auto}} details{{margin:10px 0}} summary{{cursor:pointer;font-weight:600}}
</style></head><body><main>
<h1>Corrections on the ink</h1>
<p class="mut">Experiment 27 · {len({c['stem'] for c in entries})} of the 20 documents of experiment 24 had Quran quotations that differ from their verse.
A word in a quotation that differs from its verse word was <b>proposed</b> the verse's word; a judge looked at the
scan's ink and chose, blind, between the printed reading and the proposal; a second judge had to agree. Only then
the word's <b>text</b> was corrected — in the PDFs, the ALTO and JATS files and the trust PDF. The ink is never touched.</p>
<div class="kpis">
<div class="kpi"><b>{len(entries)}</b>proposed</div>
<div class="kpi"><b>{st['applied'] + st['declined'] + st['accepted']}</b>accepted by both judges</div>
<div class="kpi"><b>{st['applied']}</b>written into the text</div>
<div class="kpi"><b>{st['rejected'] + st['disputed']}</b>turned down on the ink</div>
<div class="kpi"><b>${sum(by_model.values()):.2f}</b>Gemini, all of it</div>
</div>
<p class="small">Jump to: <a href="#fixed">the corrections</a> · <a href="#down">turned down</a> · <a href="#flags">fewer false flags</a> · <a href="#pdfs">the PDFs still read right</a> · <a href="#judge">choosing the judge</a></p>""")
    if st["declined"]:
        H.append(f'<p class="small mut">{st["declined"]} accepted correction(s) could not be written: the word is drawn '
                 'with more glyphs than the corrected word has letters, and a glyph cannot be given no text (D13). They '
                 'are listed at the end and stay flagged.</p>')

    applied = [c for c in entries if c["status"] == "applied"]
    H.append(f"<h2 id=fixed>Each correction, on the ink ({len(applied)})</h2>")
    H.append('<p class="small mut">The strip is the scan at 300 dpi, the word on pale yellow paper exactly as the judge saw it. '
             'Struck through: what the PDF carried (Azure\'s reading). Green: what it carries now. Below: the verse, the word marked. '
             f'Kinds: {", ".join(f"{v} {k}" for k, v in kinds.most_common())}.</p><div class="cards">')
    for c in applied:
        s, a = c["ref"].split(":")
        H.append(f'<div class="card">{img(c["stem"], c)}<div class="pair ar"><span class="now">{E(c["text"])}</span>'
                 f'<span class="mut">←</span><span class="was">{E(c["was"])}</span></div>'
                 f'<div class="verse ar">{verse_html(q, c)}</div>'
                 f'<div class="small mut"><span class="tag">{E(c["kind"])}</span><a href="https://tanzil.net/#{s}:{a}">{E(c["sura_name"])} {E(c["ref"])}</a> · '
                 f'<bdi dir="ltr">{E(c["stem"])} p{c["page"]}</bdi> · Azure {c["conf"] if c["conf"] is not None else "?"}<br>'
                 f'Flash: {E((c.get("judge") or {}).get("why", ""))}<br>Pro: {E((c.get("confirm") or {}).get("why", ""))}</div></div>')
    H.append("</div>")

    down = [c for c in entries if c["status"] in ("rejected", "disputed")]
    H.append(f"<h2 id=down>Turned down on the ink ({len(down)})</h2>")
    H.append('<p class="small mut">The judge said the print reads as the PDF already has it (the author\'s own wording, or the '
             'print\'s spelling), or neither reading, or could not tell; or the second judge disagreed with the first. Nothing was changed.</p>')
    vc = Counter((c["status"], ((c.get("confirm") if c["status"] == "disputed" else c.get("judge")) or {}).get("verdict")) for c in down)
    H.append("<p class='small'>" + " · ".join(f"{E(k[0])} ({E(str(k[1]))}): {v}" for k, v in vc.most_common()) + "</p>")
    H.append('<details><summary>Show them</summary><div class="cards">')
    for c in down:
        j = c.get("confirm") if c["status"] == "disputed" else c.get("judge")
        j = j or {}
        H.append(f'<div class="card">{img(c["stem"], c)}<div class="pair ar"><span class="mut">proposed</span> <span>{E(c["text"])}</span>'
                 f' · <span class="mut">printed</span> <b>{E(c["was"])}</b></div>'
                 f'<div class="small mut">{E(c["status"])}: {E(str(j.get("verdict")))} {("— " + E(j["text"])) if j.get("text") else ""}<br>'
                 f'{E(j.get("why", ""))} · {E(c["ref"])} · <bdi dir="ltr">{E(c["stem"])} p{c["page"]}</bdi></div></div>')
    H.append("</div></details>")

    if skipped:
        sc = Counter(s["category"] for s in skipped)
        H.append(f"<h2>Not proposed ({len(skipped)} differences)</h2>")
        H.append("<p class='small mut'>Differences between a quotation and its verse that are not reading errors: the author's "
                 "own wording, the print's spelling, the quotation's edges. Proposing them would ask the judge to "
                 "change what the author printed.</p>")
        H.append("".join(bar(k, v, max(sc.values()), str(v)) for k, v in sc.most_common()))
        H.append('<details><summary>Examples</summary><div class="scroll"><table><tr><th>category</th><th>printed</th><th>verse</th><th>why</th></tr>')
        seen = Counter()
        for s in skipped:
            if seen[s["category"]] >= 8:
                continue
            seen[s["category"]] += 1
            H.append(f'<tr><td>{E(s["category"])}</td><td class="ar">{E(s["reading"])}</td><td class="ar">{E(s["verse"])}</td><td class="small">{E(s["why"])}</td></tr>')
        H.append("</table></div></details>")

    if fe:
        r = fe["results"]
        base = r["product (experiment 24)"]
        chosen = fe.get("chosen")
        new = r.get(chosen) if chosen else None
        H.append("<h2 id=flags>Fewer false flags</h2>")
        H.append(f'<p class="small mut">Experiment 19\'s judged words ({base["n_errors"]} real errors among them; weighted as the archive). '
                 f'Before: the rule of experiment 24. After: <b>{E(chosen or "")}</b>.</p>')
        if new:
            mx = max(base["flagged"], new["flagged"]) * 100
            H.append("<h3>Share of words flagged</h3>" + bar("before", base["flagged"] * 100, mx, f'{base["flagged"]*100:.1f}%', "b")
                     + bar("after", new["flagged"] * 100, mx, f'{new["flagged"]*100:.1f}%'))
            H.append("<h3>Judged errors caught</h3>" + bar("before", base["n_caught"], base["n_errors"], f'{base["n_caught"]}/{base["n_errors"]}', "b")
                     + bar("after", new["n_caught"], base["n_errors"], f'{new["n_caught"]}/{new["n_errors"]}'))
            H.append("<h3>Flags that are real errors</h3>" + bar("before", base["precision_n"] * 100, 50, f'1 in {1/base["precision_n"]:.1f}', "b")
                     + bar("after", new["precision_n"] * 100, 50, f'1 in {1/new["precision_n"]:.1f}'))
            H.append("<h3>Wrong among unflagged words (weighted)</h3>" + bar("before", base["left"] * 100, 1, f'{base["left"]*100:.2f}%', "b")
                     + bar("after", new["left"] * 100, 1, f'{new["left"]*100:.2f}%'))
        H.append('<details><summary>Every rule tried</summary><div class="scroll"><table><tr><th>rule</th><th>flagged</th><th>n</th><th>caught</th><th>1 flag in</th><th>left wrong</th></tr>')
        for name, m in r.items():
            H.append(f'<tr><td>{E(name)}</td><td>{m["flagged"]*100:.2f}%</td><td>{m["n_flagged"]}</td><td>{m["n_caught"]}/{m["n_errors"]}</td>'
                     f'<td>{1/m["precision_n"]:.1f}</td><td>{m["left"]*100:.3f}%</td></tr>')
        H.append("</table></div></details>")
    if trust_before["words"]:
        fb, fa = trust_before["flagged"] / trust_before["words"], trust_after["flagged"] / max(1, trust_after["words"])
        H.append("<h3>On the 20-document set</h3>" + bar("before", fb * 100, fb * 100, f'{fb*100:.1f}% ({trust_before["flagged"]:,})', "b")
                 + bar("after", fa * 100, fb * 100, f'{fa*100:.1f}% ({trust_after["flagged"]:,})')
                 + f'<p class="small mut">{trust_after["corrected"]} words now marked corrected; verified {trust_before["verified"]:,} → {trust_after["verified"]:,}.</p>')

    if ver:
        H.append("<h2 id=pdfs>The PDFs still read right</h2><p class='small mut'>pdfium 5.12.1 (Chrome's engine, pinned). Words intact: "
                 "the build's placed words, each applied correction counted with its new text. Changed spots: pdfium's words on each "
                 "corrected page before and after, aligned; every difference must be a correction (both PDFs). Ink: the pages with a correction "
                 "rendered before and after, compared pixel for pixel, and the original bytes still the file's first bytes.</p>")
        H.append('<div class="scroll"><table><tr><th>document</th><th>applied</th><th>words intact before → after (faithful)</th><th>(vector)</th><th>changed spots in pdfium (unexplained)</th><th>found in pdfium</th><th>ink</th><th>trust PDFs</th></tr>')
        for stem, v in ver.items():
            f, vv = v.get(f"{stem}.pdf", {}), v.get(f"{stem}_vector.pdf", {})
            H.append(f'<tr><td>{E(stem)}</td><td>{v["applied"]}</td><td>{f.get("intact_before")} → {f.get("intact_after")} / {f.get("words")}</td>'
                     f'<td>{vv.get("intact_before")} → {vv.get("intact_after")}</td><td>{f.get("changes_explained", 0) + vv.get("changes_explained", 0)} ({f.get("changes_unexplained", 0) + vv.get("changes_unexplained", 0)})</td>'
                     f'<td>{f.get("corrections_found")}/{v["applied"]}</td><td>{"identical" if v.get("ink_identical", True) else "CHANGED"}</td>'
                     f'<td>{"same" if f.get("trust_pdf_ok", True) and vv.get("trust_pdf_ok", True) else "DIFFERS"}</td></tr>')
        H.append("</table></div>")

    if cal:
        H.append("<h2 id=judge>Choosing the judge</h2><p class='small mut'>48 Quran words from the set that the print, Azure and the verse agree "
                 "on, each shown against a look-alike (a dot group, a hamza, ة/ه, ى/ي, a dropped letter), or two look-alikes "
                 "(right answer: neither).</p><div class='scroll'><table><tr><th>model</th><th>printed vs look-alike</th><th>vowelled</th><th>neither spotted</th><th>cost</th></tr>")
        for m, d in cal.items():
            s = d["summary"]
            H.append(f'<tr><td>{E(m)}</td><td>{s["pair"]["right"]}/{s["pair"]["n"]}</td><td>{s["pair vowelled"]["right"]}/{s["pair vowelled"]["n"]}</td>'
                     f'<td>{s["neither"]["right"]}/{s["neither"]["n"]}</td><td>${d["spent_this_run"]:.3f}</td></tr>')
        H.append("</table></div><p class='small'>A tie: Flash judges every proposal (cheaper), Pro must agree before anything is written.</p>")
    dec = [c for c in entries if c["status"] == "declined"]
    if dec:
        H.append(f"<h2>Accepted but not written ({len(dec)})</h2><div class='cards'>")
        for c in dec:
            reason = next(iter((c.get("applied") or {}).values()), {}).get("reason", "")
            H.append(f'<div class="card">{img(c["stem"], c)}<div class="pair ar"><span class="now">{E(c["text"])}</span><span class="mut">←</span><span>{E(c["was"])}</span></div>'
                     f'<div class="small mut">{E(reason)}</div></div>')
        H.append("</div>")
    H.append(f"<h2>Spend</h2><p class='small'>{', '.join(f'{m}: ${v:.3f}' for m, v in by_model.items())}; cap $6. Every request in "
             "<code>out/spend.jsonl</code>, every answer cached in <code>out/judge_cache.jsonl</code>.</p>")
    H.append("<p class='small mut'>Verse text: Tanzil Project, Quran text (Simple v1.1), CC BY 3.0, <a href='https://tanzil.net'>tanzil.net</a>.</p></main></body></html>")
    (OUT / "report.html").write_text("\n".join(H), encoding="utf-8")
    print("wrote", OUT / "report.html", f"{(OUT / 'report.html').stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
