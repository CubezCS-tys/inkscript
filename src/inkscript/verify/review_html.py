"""A review page: each contradiction as the word's ink beside its readings,
then every number on every page as ink beside text, so a person can judge
each in a second and mark the wrong ones."""
from __future__ import annotations
import base64, html, json
from pathlib import Path
import fitz

from ..pdf.type3 import Frame, DPI
from .consistency import review

CSS = """<style>
body{margin:0;padding:1.2rem 20px 3rem;background:#F3F1EC;color:#17150F;font:15px/1.5 system-ui,sans-serif}
h1{font-size:1.2rem;margin:0 0 .3rem}h2{font-size:.95rem;margin:1.6rem 0 .5rem;color:#555;letter-spacing:.06em;text-transform:uppercase}
.sum{color:#555;margin:0 0 1rem}
table{border-collapse:collapse;width:100%;max-width:1100px}td,th{border-bottom:1px solid #DAD6CD;padding:.4rem .5rem;vertical-align:middle;text-align:left}
th{font-size:.72rem;color:#666;letter-spacing:.06em;text-transform:uppercase}
img{display:block;max-height:64px;background:#fff;border:1px solid #DAD6CD}
.ar{font-family:"Noto Naskh Arabic","Amiri",serif;font-size:1.25rem;direction:rtl;text-align:right}
.alt{color:#9A3412}.pg{font-family:ui-monospace,monospace;font-size:.78rem;color:#666;white-space:nowrap}
.wrap{overflow-x:auto}
input.fix{font-family:"Noto Naskh Arabic","Amiri",serif;font-size:1.2rem;direction:rtl;text-align:right;width:14rem;padding:.2rem .4rem;border:1px solid #DAD6CD;background:#fff;color:#17150F}
input.fix.changed{border-color:#2C4B96;background:#EAF0FB}
.bar{position:sticky;top:0;z-index:2;background:#F3F1EC;border-bottom:1px solid #DAD6CD;padding:.5rem 0;margin:0 0 .8rem;display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;font-size:.85rem}
.bar button{font:inherit;padding:.35rem .8rem;border:1px solid #DAD6CD;background:#fff;cursor:pointer}
.bar code{font-family:ui-monospace,monospace;font-size:.78rem;background:#fff;padding:.2rem .4rem;border:1px solid #DAD6CD}
textarea.out{width:100%;max-width:1100px;min-height:6rem;font-family:ui-monospace,monospace;font-size:.78rem;margin:.4rem 0 0;display:none}
</style>"""

JS = """<script>
// Edit a reading in place; "Show corrections" lists every changed word as {page, box, text}
// for:  inkscript correct <stem>.pdf --file corrections.json
const inputs=[...document.querySelectorAll('input.fix')];
inputs.forEach(i=>i.addEventListener('input',()=>i.classList.toggle('changed',i.value.trim()!==i.dataset.orig.trim())));
function corrections(){return inputs.filter(i=>i.value.trim()!==i.dataset.orig.trim()&&i.value.trim()).map(i=>({page:+i.dataset.page,box:JSON.parse(i.dataset.box),text:i.value.trim()}))}
document.getElementById('show').addEventListener('click',()=>{const c=corrections();const ta=document.getElementById('out');ta.style.display='block';ta.value=JSON.stringify(c,null,1);document.getElementById('count').textContent=c.length+' correction'+(c.length===1?'':'s');
  if(navigator.clipboard)navigator.clipboard.writeText(ta.value).then(()=>{document.getElementById('count').textContent+=' — copied'}).catch(()=>{});});
</script>"""


def crop(page, box, rot, W, H, pad=6):
    f = Frame(rot, W, H)
    (x0, y0), (x1, y1) = f.to_page(box[0], box[1]), f.to_page(box[2], box[3])
    r = fitz.Rect(min(x0, x1) - pad, min(y0, y1) - pad, max(x0, x1) + pad, max(y0, y1) + pad) * (72 / DPI)
    r = r & page.rect
    if r.is_empty or r.width < 2 or r.height < 2:
        return ""
    pix = page.get_pixmap(dpi=150, clip=r, colorspace=fitz.csGRAY)
    if pix.w < 1 or pix.h < 1:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpeg", jpg_quality=70)).decode()


def write_review_html(shapes_json: Path, pdf: Path, out: Path, max_numbers: int = 600) -> dict:
    r = review(shapes_json)
    doc = fitz.open(pdf); stem = pdf.stem
    dims = {}
    def pagedims(pn):
        if pn not in dims:
            pix = doc[pn - 1].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY); dims[pn] = (pix.w, pix.h)
        return dims[pn]
    def fix(w):                                   # the reading, editable; a change becomes a correction
        return (f'<input class="fix" value="{html.escape(w["text"], quote=True)}" data-orig="{html.escape(w["text"], quote=True)}" '
                f'data-page="{w["page"]}" data-box="{json.dumps([int(v) for v in w["box"]])}" spellcheck="false">')
    rows = []
    for c in r["conflicts"]:
        readings = ", ".join(f"{html.escape(t)} ×{n}" for t, n in sorted(c["readings"].items(), key=lambda x: -x[1]))
        for sp in c["suspects"]:
            W, H = pagedims(sp["page"]); rot = sp.get("rot", 0)
            rows.append(f'<tr><td><img src="{crop(doc[sp["page"] - 1], sp["box"], rot, W, H)}" alt=""></td>'
                        f'<td>{fix(sp)}</td><td class="ar alt">{readings}</td><td class="pg">{c["kind"]}<br>p{sp["page"]}</td></tr>')
    nums = []
    for n in r["numbers"][:max_numbers]:
        W, H = pagedims(n["page"]); rot = n.get("rot", 0)
        nums.append(f'<tr><td><img src="{crop(doc[n["page"] - 1], n["box"], rot, W, H)}" alt=""></td><td>{fix(n)}</td><td class="pg">p{n["page"]}</td></tr>')
    body = (f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>review {html.escape(stem)}</title>{CSS}<h1>{html.escape(stem)}</h1>'
            f'<div class="bar"><button type="button" id="show">Show corrections</button><span id="count"></span><span>then: <code>inkscript correct {html.escape(stem)}.pdf --file corrections.json</code></span></div><textarea class="out" id="out" spellcheck="false"></textarea>'
            f'<p class="sum">{r["words"]} words · {r["repeated_ink"]} share ink with another word · {len(r["conflicts"])} contradictions ({len(rows)} words to judge) · {len(r["numbers"])} numbers</p>'
            f'<h2>Same ink, different reading — {r["kinds"]}</h2><div class="wrap"><table><tr><th>ink</th><th>read as</th><th>other readings of this ink</th><th>kind · page</th></tr>{"".join(rows) or "<tr><td colspan=4>none</td></tr>"}</table></div>'
            f'<h2>Numbers ({min(len(r["numbers"]), max_numbers)} of {len(r["numbers"])})</h2><div class="wrap"><table><tr><th>ink</th><th>read as</th><th>page</th></tr>{"".join(nums)}</table></div>' + JS)
    out.write_text(body, encoding="utf-8")
    return dict(conflicts=len(r["conflicts"]), suspects=len(rows), numbers=len(r["numbers"]))
