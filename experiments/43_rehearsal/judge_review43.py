"""Experiment 43: the owner's page for the judge — out/judge/judge_review.html (served as
http://127.0.0.1:8899/judge/judge_review.html through the symlink experiments/41_azure_structure/out/views/judge).

Per judged page: the scan with our blocks outlined and numbered | our Layout page (and, when an edit was applied,
the page after it); the judge's findings with confidence and evidence, the code check (second key), and what
happens: applied automatically / bespoke retry / owner. Calibration pages show what was known on them and how each
model did. No model calls.

    python3 judge_review43.py --dir gemini-3.8-flash [--calib-dirs gemini-3.8-flash gemini-4-argon]
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import judge43 as JG  # noqa: E402

J = JG.J
E = html.escape


def card(rec: dict, findings: list[dict], kind: str, truth: dict | None = None, others: dict | None = None,
         after: Path | None = None, retry: dict | None = None) -> str:
    run, stem, p = rec["run"], rec["stem"], rec["page"]
    routes = sorted({f["route"] for f in findings}) or ["none"]
    img = JG.side(run, stem, p).relative_to(J)
    h = [f'<section class="card" data-routes="{" ".join(routes)}" data-kind="{kind}">',
         f'<h2>{E(stem)} <span class="pg">page {p}</span> <span class="run">{E(run)}</span> '
         + "".join(f'<span class="badge {r}">{r}</span>' for r in routes) + "</h2>"]
    if truth is not None:
        tp = truth.get("problems") or []
        h.append('<p class="truth"><b>Known on this page</b> (' + E(truth.get("src", "")) + "): "
                 + ("; ".join(E(x["what"]) for x in tp) if tp else "no structural problem")
                 + (" · words only: " + E(", ".join(truth["words"])) if truth.get("words") else "") + "</p>")
    h.append(f'<figure><a href="{img}"><img loading="lazy" src="{img}" alt="scan with our blocks | our page"></a>'
             '<figcaption>left: the scan with our blocks outlined (numbers = block ids p{page}b<i>N</i>) · right: our '
             'Layout page</figcaption></figure>')
    if after:
        a = after.relative_to(J)
        h.append(f'<figure class="after"><a href="{a}"><img loading="lazy" src="{a}" alt="after"></a>'
                 '<figcaption>after the applied edit(s): out/v33_300_judged</figcaption></figure>')
    if not findings:
        h.append(f'<p class="none">{E(rec.get("model", ""))}: <b>nothing wrong</b> on this page.</p>')
    for f in findings:
        chk = f.get("check") or {}
        ok = chk.get("ok")
        h.append(f'<div class="f {f["route"]}"><div class="fh"><span class="badge {f["route"]}">{f["route"]}</span> '
                 f'<b>{E(str(f["type"]))}</b>{" · " + E(f["subtype"]) if f.get("subtype") else ""} · confidence '
                 f'<b>{f["confidence"]:.2f}</b> · action <code>{E(str(f["action"]))}</code>'
                 + (f' on {E(", ".join(f["blocks"][:8]))}' if f.get("blocks") else "")
                 + (f' · {len(f["lines"])} lines' if f.get("lines") else "") + "</div>"
                 f'<p class="ev">{E(f.get("evidence") or "")}</p>'
                 + (f'<p class="ins">instruction for a retry: {E(f["instruction"])}</p>' if f.get("instruction") else "")
                 + (f'<p class="chk {"ok" if ok else "no" if ok is False else "na"}">code check: '
                    f'{"passed" if ok else "failed" if ok is False else "—"} — {E(chk.get("why") or "")}</p>')
                 + (f'<p class="verdict">my look: {E(f["verdict"])}</p>' if f.get("verdict") else "")
                 + "</div>")
    if retry:
        c = retry.get("check") or {}
        h.append(f'<div class="f retry"><div class="fh"><span class="badge retry">retry done</span> {E(retry.get("model", ""))} '
                 f'${retry.get("usd", 0):.3f} · check {"passed → applied" if c.get("ok") else "failed → owner"}: '
                 f'{E(c.get("why", ""))}</div><p class="ev">blocks before: '
                 + E(", ".join(f'{b["type"]}({len(b["lines"])})' for b in retry.get("old_blocks") or []))
                 + "<br>after: " + E(", ".join(f'{b["type"]}({len(b["lines"])})' for b in retry.get("new_blocks") or []))
                 + "</p></div>")
    if others:
        for d, fs in others.items():
            h.append(f'<p class="other"><b>{E(d)}</b>: ' + ("; ".join(
                f'{E(str(x["type"]))} {x["confidence"]:.2f} ({E(x["route"])})' for x in fs) or "nothing wrong") + "</p>")
    h.append("</section>")
    return "\n".join(h)


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--card:#fff;--line:#e3e0d8;--auto:#1f7a3a;--retry:#a35a00;--human:#8a2b8f;
--none:#5a6b7a;--ok:#1f7a3a;--no:#b3261e}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;--mut:#a3a19a;--card:#21211f;
--line:#3a3935;--auto:#5cc27a;--retry:#e0a050;--human:#d08ad4;--none:#9fb0bf;--ok:#5cc27a;--no:#ff8a80}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:16px}
main{max-width:1500px;margin:auto}h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.05rem;margin:.2em 0 .5em}
.lead{color:var(--mut);max-width:70em}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:12px 14px;margin:14px 0}figure{margin:6px 0}figure img{width:100%;height:auto;border:1px solid var(--line)}
figcaption{color:var(--mut);font-size:.85em}.after figcaption{color:var(--auto)}
.badge{display:inline-block;font-size:.75em;font-weight:600;padding:1px 7px;border-radius:9px;color:#fff;margin-left:4px;
background:var(--none)}.badge.auto{background:var(--auto)}.badge.retry{background:var(--retry)}.badge.human{background:var(--human)}
.pg,.run{color:var(--mut);font-weight:400;font-size:.9em}.f{border-left:4px solid var(--none);padding:4px 10px;margin:8px 0}
.f.auto{border-color:var(--auto)}.f.retry{border-color:var(--retry)}.f.human{border-color:var(--human)}
.ev{margin:.2em 0}.ins{margin:.2em 0;color:var(--retry)}.chk.ok{color:var(--ok)}.chk.no{color:var(--no)}.chk{margin:.2em 0;font-size:.92em}
.truth{background:color-mix(in srgb,var(--retry) 10%,transparent);padding:4px 8px;border-radius:6px}.other{color:var(--mut);font-size:.9em}
.none{color:var(--none)}table{border-collapse:collapse;margin:8px 0;font-size:.92em}td,th{border:1px solid var(--line);padding:3px 8px;text-align:left}
.bar{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--line);z-index:2}
.bar button{margin:2px;padding:4px 10px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;cursor:pointer}
.bar button.on{outline:2px solid var(--fg)}code{font-size:.9em}
@media (max-width:700px){body{padding:8px 16px}}
"""
JS = """
const B=document.querySelectorAll('.bar button');let k='all',r='all';
function go(){document.querySelectorAll('.card').forEach(c=>{const okk=k=='all'||c.dataset.kind==k;
const okr=r=='all'||c.dataset.routes.split(' ').includes(r);c.style.display=okk&&okr?'':'none'});
B.forEach(b=>b.classList.toggle('on',(b.dataset.k&&b.dataset.k==k)||(b.dataset.r&&b.dataset.r==r)))}
B.forEach(b=>b.onclick=()=>{if(b.dataset.k)k=b.dataset.k;if(b.dataset.r)r=b.dataset.r;go()});go();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="gemini-3.8-flash", help="the judge's answers (model dir) used for routes")
    ap.add_argument("--calib-dirs", nargs="*", default=["gemini-3.8-flash", "gemini-4-argon"])
    ap.add_argument("--summary", default=str(J / "summary.json"))
    a = ap.parse_args()
    truth = json.loads((HERE / "judge_truth43.json").read_text(encoding="utf-8"))
    vf = HERE / "judge_verdicts43.json"
    verdicts = json.loads(vf.read_text(encoding="utf-8"))["verdicts"] if vf.exists() else {}
    calib = json.loads((J / "calib.json").read_text()) if (J / "calib.json").exists() else []
    summ = json.loads(Path(a.summary).read_text()) if Path(a.summary).exists() else {}
    cards = []
    seen = set()
    for t in truth["pages"]:
        s, p = t["page"].rsplit(":", 1)
        f = JG.answer_path(a.dir, t["run"], s, int(p))
        if not f.exists():
            continue
        rec = json.loads(f.read_text())
        fs = JG.decide(rec)
        for f_ in fs:
            v = verdicts.get(f"{a.dir}|{t['page']}|{f_['n']}")
            if v:
                f_["verdict"] = v.get("verdict", "") + (": " + v["note"] if v.get("note") else "")
        others = {}
        for d in a.calib_dirs:
            if d == a.dir:
                continue
            g = JG.answer_path(d, t["run"], s, int(p))
            if g.exists():
                others[d] = JG.decide(json.loads(g.read_text()))
        rt = J / "retry" / t["run"] / f"{s}_p{int(p):03d}.json"
        retry = json.loads(rt.read_text()) if rt.exists() else None
        after = None
        if t["run"] == "v33_300" and (JG.OUT / "v33_300_judged" / "views" / "mirror" / f"{s}.html").exists():
            pf = JG.OUT / "v33_300_judged" / "masters" / f"{s}.patches.json"
            if pf.exists() and any(e.get("page") == int(p) for e in json.loads(pf.read_text())["applied"]):
                after = JG.side("v33_300_judged", s, int(p))
        cards.append(card(rec, fs, "calibration", t, others, after, retry))
        seen.add((t["run"], s, int(p)))
    # the 300's flagged pages: auto / retry / human first, then a sample of "none"
    rest = {"auto": [], "retry": [], "human": [], "none": []}
    for f in sorted((J / "answers" / a.dir / "v33_300").glob("*_p[0-9][0-9][0-9].json")):
        rec = json.loads(f.read_text())
        if ("v33_300", rec["stem"], rec["page"]) in seen:
            continue
        fs = JG.decide(rec)
        rs = {x["route"] for x in fs}
        key = "auto" if "auto" in rs else "retry" if "retry" in rs else "human" if "human" in rs else "none"
        rest[key].append((rec, fs))
    for key in ("auto", "retry", "human"):
        for rec, fs in rest[key]:
            after = None
            pf = JG.OUT / "v33_300_judged" / "masters" / f"{rec['stem']}.patches.json"
            if key == "auto" and pf.exists() and (JG.OUT / "v33_300_judged" / "views" / "mirror" / f"{rec['stem']}.html").exists():
                if any(e.get("page") == rec["page"] for e in json.loads(pf.read_text())["applied"]):
                    after = JG.side("v33_300_judged", rec["stem"], rec["page"])
            rt = J / "retry" / "v33_300" / f"{rec['stem']}_p{rec['page']:03d}.json"
            cards.append(card(rec, fs, "the 300", None, None, after, json.loads(rt.read_text()) if rt.exists() else None))
    for rec, fs in rest["none"][:12]:
        cards.append(card(rec, fs, "the 300"))
    # calibration table
    tab = ""
    if calib:
        types = sorted({k for r in calib for f in ("caught", "missed", "false_alarms", "new_real", "debatable") for k in r[f]})
        tab = ("<table><tr><th>problem type</th>" + "".join(f"<th>{E(r['dir'])}<br>caught / known · false alarms · "
                                                           f"new real · debatable</th>" for r in calib) + "</tr>")
        for t in types:
            tab += f"<tr><td>{E(t)}</td>" + "".join(
                f"<td>{r['caught'].get(t, 0)} / {r['caught'].get(t, 0) + r['missed'].get(t, 0)} · "
                f"{r['false_alarms'].get(t, 0)} · {r['new_real'].get(t, 0)} · {r['debatable'].get(t, 0)}</td>" for r in calib) + "</tr>"
        tab += "<tr><td>clean pages answered “none”</td>" + "".join(f"<td>{r['clean_pages_said_none']}</td>" for r in calib) + "</tr>"
        tab += "<tr><td>confidence vs right</td>" + "".join(f"<td>{E(json.dumps(r['confidence'], ensure_ascii=False))}</td>" for r in calib) + "</tr>"
        tab += "<tr><td>cost a page (Standard)</td>" + "".join(f"<td>${r['usd_page']}</td>" for r in calib) + "</tr></table>"
    n300 = {k: len(v) for k, v in rest.items()}
    head = (f"<h1>The judge</h1><p class=lead>A model ({E(a.dir)}) looks at each page — the scan, the scan with our "
            "blocks outlined, our page — and says what is wrong in the structure, never the words. An edit is applied "
            "<b>automatically</b> only with two keys: the judge is sure (confidence ≥ "
            f"{JG.THRESHOLD}) <b>and</b> a code check of the scan agrees (pale ink + non-words / unsure Azure for "
            "show-through; geometry for structure). Otherwise a <b>retry</b> of that page with the judge's note and "
            "close-ups, or the <b>owner</b>. Applied edits go to out/v33_300_judged only; the run's masters are "
            "untouched.</p>"
            + (f"<p class=lead>{E(summ.get('line', ''))}</p>" if summ else "")
            + f"<p class=lead>Flagged pages of the 300 judged: {sum(n300.values())} — auto {n300['auto']}, "
              f"retry {n300['retry']}, owner {n300['human']}, nothing wrong {n300['none']} (12 of those shown).</p>"
            + "<h2>Calibration</h2>" + tab)
    bar = ('<div class=bar>show: <button data-k=all>all</button><button data-k=calibration>calibration pages</button>'
           '<button data-k="the 300">the 300</button> · route: <button data-r=all>any</button>'
           '<button data-r=auto>auto</button><button data-r=retry>retry</button><button data-r=human>owner</button>'
           '<button data-r=none>none</button></div>')
    page = (f'<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,'
            f'initial-scale=1"><title>The judge</title><style>{CSS}</style></head><body><main>{head}{bar}'
            + "\n".join(cards) + f"</main><script>{JS}</script></body></html>")
    out = J / "judge_review.html"
    out.write_text(page, encoding="utf-8")
    print(out, len(cards), "cards")


if __name__ == "__main__":
    main()
