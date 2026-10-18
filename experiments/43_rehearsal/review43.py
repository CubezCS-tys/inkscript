"""Experiment 43: the owner's review page of a run's doubtful spots (no model calls).

    review43.py --run replay [--max 150] [--min-severity low]
        -> out/<run>/review.html  (self-contained: images inline; works on a phone)

Reads out/<run>/flags.json (flags43.py) and the run's masters (out/<run>/masters, for "replay" out/masters; build
them first with run43.py --assemble or replay43.py masters). For each flagged spot, most serious first: the scan
cropped to the spot, our Layout view (experiment 41's, through views43) cropped to the same place, the reason, and
yes (right) / no (wrong) + a note. Marks stay in the browser (localStorage, per run); "Export my marks" saves them
as JSON for `gold43.py import`. Layout views: out/<run>/review/views/mirror/; screenshots (experiment 40's
Playwright venv, 2x): out/<run>/review/shots/ (kept between builds; --fresh redoes them).
"""
from __future__ import annotations

import argparse
import base64
import html as H
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import flags43 as F  # noqa: E402
import masters43 as M43  # noqa: E402
from masters43 import ST  # noqa: E402

PW = HERE.parent / "40_gemini4_vlm" / "out" / "venv" / "bin" / "python"
SEV_ORDER = ["high", "medium", "low"]
PAD = 18                                   # around the spot, 0-1000 units
MIN_W = 420                                # a crop is at least this wide (0-1000): enough context to judge


def layout_views(run: str, stems: list[str], dst: Path):
    """Experiment 41's Layout view of each article, from the run's masters (views43's other-article fading)."""
    import views43
    import views as V
    import mread as MR
    arts = F.all_articles()
    MR.MAST = F.run_dirs(run)["masters"].resolve()
    V.VIEWS = dst.resolve()
    if views43.CSS43 not in V.MIRROR_CSS:
        V.MIRROR_CSS = V.MIRROR_CSS + views43.CSS43
    V.write_layout_print = lambda *x, **k: None
    for s in stems:
        a = arts[s]
        F.use_pages_of(a)
        if not (MR.MAST / f"{s}.jats.xml").exists():
            print(f"  {s}: no masters in {MR.MAST} (assemble first)")
            continue
        f = dst / "mirror" / f"{s}.html"
        if f.exists() and f.stat().st_mtime >= (MR.MAST / f"{s}.alto.xml").stat().st_mtime:
            continue
        V.build_layout(a, load43(a, MR))


def load43(a, MR):
    """views43.load43 for any article dict (views43's takes experiment 41's sample only through art_of)."""
    doc = MR.load(a)
    other, orn = set(), set()
    for b in doc["D"].A.iter(MR._q("TextBlock")):
        if "role.otherArticle" in (b.get("TAGREFS") or ""):
            other.add(b.get("ID"))
        if "role.ornament" in (b.get("TAGREFS") or ""):
            orn.add(b.get("ID"))
    for rec in doc["blocks"]:
        if rec.get("alto") in other:
            rec["type"] = "other_article"
    doc["blocks"] = [r for r in doc["blocks"] if r.get("alto") not in orn]
    return doc


def shots(views: Path, shots_dir: Path, need: dict, fresh: bool):
    """One 2x screenshot of each needed Layout page (stem -> pages)."""
    env = dict(os.environ, SHOTS_SCALE="2")
    for s, pages in sorted(need.items()):
        html = views / "mirror" / f"{s}.html"
        if not html.exists():
            continue
        todo = [p for p in sorted(pages) if fresh or not (shots_dir / f"{s}_p{p:03d}.png").exists()]
        if not todo:
            continue
        r = subprocess.run([str(PW), str(HERE / "shots43.py"), str(shots_dir / s), str(html), *map(str, todo)],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            print(f"  {s}: screenshot failed: {r.stderr.strip()[-300:]}")


def crop_box(box) -> list[float]:
    if not box:
        return [0, 0, 1000, 1000]
    x0, y0, x1, y1 = box
    x0, y0, x1, y1 = x0 - PAD, y0 - PAD, x1 + PAD, y1 + PAD
    if x1 - x0 < MIN_W:
        c = (x0 + x1) / 2
        x0, x1 = c - MIN_W / 2, c + MIN_W / 2
    if y1 - y0 > 450:                           # a whole-page spot: keep it readable, top part
        y1 = y0 + 450
    return [max(0, x0), max(0, y0), min(1000, x1), min(1000, y1)]


def crop(img, box, width=640, rect=None) -> str | None:
    if img is None:
        return None
    h, w = img.shape[:2]
    x0, y0, x1, y1 = (int(box[0] * w / 1000), int(box[1] * h / 1000), int(box[2] * w / 1000), int(box[3] * h / 1000))
    c = img[y0:y1, x0:x1].copy()
    if c.size == 0:
        return None
    if rect:                                    # the spot itself, outlined
        rx0, ry0 = int(rect[0] * w / 1000) - x0, int(rect[1] * h / 1000) - y0
        rx1, ry1 = int(rect[2] * w / 1000) - x0, int(rect[3] * h / 1000) - y0
        cv2.rectangle(c, (rx0 - 4, ry0 - 4), (rx1 + 4, ry1 + 4), (40, 40, 220), max(2, c.shape[1] // 300))
    if c.shape[1] > width:
        c = cv2.resize(c, (width, int(c.shape[0] * width / c.shape[1])), interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 60])[1].tobytes()).decode()


CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e2dc;--yes:#2e7d32;--no:#c62828;--accent:#1565c0;
--high:#c62828;--medium:#ef6c00;--low:#78909c}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#202020;
--line:#3a3a37;--yes:#66bb6a;--no:#ef5350;--accent:#64b5f6}}
:root[data-theme=dark]{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#202020;--line:#3a3a37;--yes:#66bb6a;--no:#ef5350;--accent:#64b5f6}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
header.top{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:8px 16px;
display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
header.top h1{font-size:16px;margin:0} header.top .count{color:var(--muted);font-size:13px}
button,select{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 10px;cursor:pointer}
.help{max-width:1100px;margin:12px auto;padding:0 16px;color:var(--muted)}
.spot{max-width:1100px;margin:12px auto;background:var(--card);border:1px solid var(--line);border-inline-start:5px solid var(--sev);
border-radius:6px;padding:10px 14px}
.spot.yes{outline:2px solid var(--yes)} .spot.no{outline:2px solid var(--no)}
.spot.yes .y{background:var(--yes);color:#fff} .spot.no .n{background:var(--no);color:#fff}
.meta{display:flex;flex-wrap:wrap;gap:4px 10px;align-items:baseline;font-size:13px;color:var(--muted)}
.badge{color:#fff;background:var(--sev);border-radius:3px;padding:0 6px;font-weight:600;font-size:12px}
.kind{font-weight:600;color:var(--fg)}
.reason{margin:6px 0 8px;font-size:15px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media (max-width:760px){.pair{grid-template-columns:1fr}}
.pair figure{margin:0} .pair img{width:100%;height:auto;border:1px solid var(--line);background:#fff}
.pair figcaption{font-size:12px;color:var(--muted)}
.ctl{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;align-items:center}
.ctl input{flex:1;min-width:180px;font:13px system-ui;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:4px;padding:4px 6px}
.noimg{color:var(--muted);font-size:13px;font-style:italic}
.hidden{display:none}
"""

JS = r"""
const RUN = document.body.dataset.run, KEY = 'rv43:' + RUN;
let S = {}; try { S = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { S = {}; }
function save(){ try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} count(); }
function count(){ const n = document.querySelectorAll('.spot').length; const v = Object.values(S);
  const y = v.filter(x => x.ok === 'yes').length, no = v.filter(x => x.ok === 'no').length;
  document.getElementById('count').textContent = `${y} right · ${no} wrong · ${n - y - no} not marked, of ${n} spots`; }
function paint(el){ const v = S[el.dataset.id] || {}; el.classList.toggle('yes', v.ok === 'yes'); el.classList.toggle('no', v.ok === 'no');
  el.querySelector('input').value = v.note || ''; }
document.querySelectorAll('.spot').forEach(el => {
  const id = el.dataset.id;
  el.querySelector('.y').onclick = () => { S[id] = Object.assign(S[id] || {}, {ok: (S[id]||{}).ok === 'yes' ? null : 'yes'}); paint(el); save(); };
  el.querySelector('.n').onclick = () => { S[id] = Object.assign(S[id] || {}, {ok: (S[id]||{}).ok === 'no' ? null : 'no'}); paint(el); save(); };
  el.querySelector('input').oninput = e => { S[id] = Object.assign(S[id] || {}, {note: e.target.value}); save(); };
  paint(el);
});
const DATA = JSON.parse(document.getElementById('spots').textContent);
document.getElementById('export').onclick = () => {
  const out = {run: RUN, exported: new Date().toISOString(), versions: DATA.versions,
    spots: DATA.spots.map(s => Object.assign({}, s, {ok: (S[s.id]||{}).ok || null, note: (S[s.id]||{}).note || ''}))};
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'}));
  a.download = `review_${RUN}.json`; a.click(); };
document.getElementById('sev').onchange = e => { const k = e.target.value;
  document.querySelectorAll('.spot').forEach(el => el.classList.toggle('hidden', k !== 'all' && el.dataset.sev !== k)); };
document.getElementById('unmarked').onclick = () => { const el = [...document.querySelectorAll('.spot:not(.hidden)')]
  .find(e => !(S[e.dataset.id]||{}).ok); if (el) el.scrollIntoView({behavior: 'smooth', block: 'start'}); };
document.getElementById('theme').onclick = () => { const r = document.documentElement;
  r.dataset.theme = r.dataset.theme === 'dark' ? 'light' : 'dark'; };
count();
"""


def build(run: str, max_img: int, min_sev: str, fresh: bool) -> Path:
    d = F.run_dirs(run)
    res = json.loads((d["out"] / "flags.json").read_text(encoding="utf-8"))
    keep = SEV_ORDER[:SEV_ORDER.index(min_sev) + 1]
    spots = [f for r in res["articles"].values() for f in r.get("flags", []) if f["severity"] in keep]
    spots.sort(key=lambda f: (SEV_ORDER.index(f["severity"]), f["stem"], f["page"]))
    rv = d["out"] / "review"
    stems = sorted({f["stem"] for f in spots[:max_img]})
    layout_views(run, stems, rv / "views")
    need = {}
    for f in spots[:max_img]:
        need.setdefault(f["stem"], set()).add(f["page"])
    shots(rv / "views", rv / "shots", need, fresh)
    arts = F.all_articles()
    stale = []
    for s in sorted({f["stem"] for f in spots}):
        sf = d["masters"] / f"{s}.stamp.json"
        st = json.loads(sf.read_text()) if sf.exists() else {}
        if st.get("rules_hash") != res["versions"]["rules_hash"]:
            stale.append(s)
    cards, scans = [], {}
    for k, f in enumerate(spots):
        a = arts[f["stem"]]
        F.use_pages_of(a)
        imgs = ""
        if k < max_img and f["page"]:
            cb = crop_box(f["box"])
            key = (f["stem"], f["page"])
            if key not in scans:
                scans = {key: cv2.imread(str(ST.page_image(a, f["page"])), cv2.IMREAD_COLOR)}   # one page in memory
            sc = crop(scans[key], cb, rect=f["box"])
            sh = rv / "shots" / f"{f['stem']}_p{f['page']:03d}.png"
            lv = crop(cv2.imread(str(sh), cv2.IMREAD_COLOR), cb, rect=f["box"]) if sh.exists() else None
            fig = lambda b, cap: (f'<figure><img loading="lazy" src="data:image/jpeg;base64,{b}" alt="{cap}">'  # noqa: E731
                                  f'<figcaption>{cap}</figcaption></figure>') if b else \
                f'<figure><div class="noimg">{cap}: not available</div></figure>'
            imgs = f'<div class="pair">{fig(sc, "the scan")}{fig(lv, "our Layout view")}</div>'
        elif f["page"]:
            imgs = '<div class="noimg">(no pictures beyond the first spots; raise --max)</div>'
        lines = ", ".join(f["lines"][:12]) + (" …" if len(f["lines"]) > 12 else "")
        cards.append(
            f'<section class="spot" data-id="{H.escape(f["id"])}" data-sev="{f["severity"]}" style="--sev:var(--{f["severity"]})">'
            f'<div class="meta"><span class="badge">{f["severity"]}</span><span class="kind">{H.escape(f["kind"])}</span>'
            f'<span>{H.escape(f["stem"])} · page {f["page"]}</span><span>lines {H.escape(lines) or "—"}</span></div>'
            f'<div class="reason" dir="auto">{H.escape(f["reason"])}</div>{imgs}'
            f'<div class="ctl"><button class="y" title="the output is right here">yes, right</button>'
            f'<button class="n" title="the output is wrong here">no, wrong</button>'
            f'<input placeholder="note: what is wrong, or why it is fine" dir="auto"></div></section>')
    by = {s: sum(1 for f in spots if f["severity"] == s) for s in keep}
    data = dict(run=run, versions=res["versions"],
                spots=[{k: f[k] for k in ("id", "stem", "kind", "severity", "page", "lines", "reason")} for f in spots])
    stale_note = (f'<p><b>Note:</b> {len(stale)} article(s) have masters made with other code than these flags '
                  f'({", ".join(stale[:6])}{"…" if len(stale) > 6 else ""}): the Layout view may not match; '
                  f're-assemble them.</p>') if stale else ""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review {H.escape(run)}</title><style>{CSS}</style></head>
<body data-run="{H.escape(run)}">
<header class="top"><h1>Doubtful spots · {H.escape(run)}</h1><span class="count" id="count"></span>
<select id="sev"><option value="all">all</option>{''.join(f'<option value="{s}">{s} ({by[s]})</option>' for s in keep)}</select>
<button id="unmarked">next unmarked</button><button id="export">Export my marks</button><button id="theme">Light / dark</button></header>
<div class="help"><p>The code found these spots doubtful ({', '.join(f'{by[s]} {s}' for s in keep)}; made {res['made']},
rules {res['versions']['rules_hash']}). Each shows the scan and our Layout view of the same place, the spot outlined in
red. Press <b>yes, right</b> if our output is right there, <b>no, wrong</b> if it is not, and say why in the note.
A "yes" makes the spot part of the checked set that every later change must keep; a "no" becomes an issue to fix by a
code rule or a prompt change. Your marks stay in this browser; press <i>Export my marks</i> to save them as a file.</p>
{stale_note}</div>
{''.join(cards)}
<script type="application/json" id="spots">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>
<script>{JS}</script></body></html>"""
    out = d["out"] / "review.html"
    out.write_text(doc, encoding="utf-8")
    print(f"{out}  {len(spots)} spots ({by}), {out.stat().st_size / 1e6:.1f} MB")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--max", type=int, default=150, help="spots with pictures (most serious first)")
    ap.add_argument("--min-severity", choices=SEV_ORDER, default="low")
    ap.add_argument("--fresh", action="store_true", help="redo the Layout screenshots")
    a = ap.parse_args()
    build(a.run, a.max, a.min_severity, a.fresh)


if __name__ == "__main__":
    main()
