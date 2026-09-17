"""Static HTML review bundles: one renderer for every engine's blocks, so a
visible difference is the OCR, never the drawing."""
from __future__ import annotations
import html, re, urllib.parse

TYPE_COLOURS = {"title": "#C4571A", "header": "#0F6E76", "footer": "#0F6E76",
                "text": "#55636F", "table": "#7A5AA8", "references": "#4A7C3F",
                "equation": "#B0447A", "signature": "#A8752A", "image": "#8DA0AF",
                "list": "#3F6FA8", "caption": "#8A6A2A", "aside_text": "#7A7A7A"}


CSS = """
:root{--bg:#EEF1F4;--surf:#F8FAFB;--sheet:#FCFCFB;--fg:#101823;--mut:#55636F;
--rule:#C9D2D9;--mi:#C4571A;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
--ar:"Noto Naskh Arabic","Amiri","Scheherazade New","Traditional Arabic",serif}
@media(prefers-color-scheme:dark){:root{--bg:#0C131B;--surf:#131D27;--fg:#DBE3EA;
--mut:#8DA0AF;--rule:#26343F;--mi:#F0894A}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:inherit}
.top{display:flex;gap:.8rem;align-items:center;padding:.6rem 1.1rem;
border-bottom:1px solid var(--rule);background:var(--surf);position:sticky;top:0;z-index:20}
.top h1{font-size:.92rem;margin:0;font-family:var(--mono)}
.top .sp{flex:1}
.top a,.top button{font:inherit;font-size:.75rem;background:none;color:var(--mut);
border:1px solid var(--rule);border-radius:3px;padding:.18rem .55rem;cursor:pointer;
text-decoration:none}
.top a:hover,.top button:hover{color:var(--mi);border-color:var(--mi)}
.wrap{display:grid;grid-template-columns:238px 1fr;min-height:calc(100vh - 44px)}
aside{border-right:1px solid var(--rule);background:var(--surf);
max-height:calc(100vh - 44px);overflow:auto;position:sticky;top:44px}
aside .jh{font-family:var(--mono);font-size:.64rem;letter-spacing:.1em;color:var(--mut);
padding:.55rem .8rem .15rem;text-transform:uppercase}
aside a{display:block;padding:.26rem .8rem;font-family:var(--mono);font-size:.72rem;
color:var(--mut);text-decoration:none;border-left:2px solid transparent}
aside a:hover{color:var(--fg);background:var(--bg)}
aside a.on{color:var(--mi);border-left-color:var(--mi);background:var(--bg)}
main{padding:1rem 1.2rem 4rem;min-width:0}
.pgwrap{margin-bottom:2rem}
.pgn{font-family:var(--mono);font-size:.68rem;color:var(--mut);margin:0 0 .3rem}
.split{display:grid;grid-template-columns:1fr 1fr;gap:1rem;align-items:start}
@media(max-width:1080px){.split{grid-template-columns:1fr}
.wrap{grid-template-columns:1fr}aside{position:static;max-height:none}}
.pane h2{font-family:var(--mono);font-size:.66rem;letter-spacing:.09em;text-transform:uppercase;
color:var(--mut);margin:0 0 .35rem;font-weight:500}
.sheet{position:relative;background:var(--sheet);border:1px solid var(--rule);overflow:hidden}
.sheet img.scan{display:block;width:100%}
.blk{position:absolute;overflow:hidden;display:flex;align-items:center}
.blk::after{content:"";position:absolute;inset:0;border:1px dashed var(--bc);opacity:0;
pointer-events:none;transition:opacity .15s}
body.boxes .blk::after{opacity:.45}
.blk .inner{width:100%;max-height:100%;overflow:hidden;color:#101823;font-family:var(--ar);
line-height:1.5}
.blk[data-t="title"] .inner{font-weight:700;text-align:center}
.blk[data-t="header"] .inner,.blk[data-t="footer"] .inner{color:#55636F}
.blk img.crop{width:100%;height:100%;object-fit:contain;display:block}
.blk table{width:100%;border-collapse:collapse}
.blk td{border:1px solid #bbb;padding:.1em .25em}
.meta{display:flex;gap:.35rem;flex-wrap:wrap;margin:0 0 .8rem}
.chip{font-family:var(--mono);font-size:.63rem;border:1px solid var(--bc,var(--rule));
color:var(--bc,var(--mut));border-radius:2px;padding:.04rem .32rem}
mark.hit{background:rgba(196,87,26,.35);border-radius:2px}
.lede{color:var(--mut);max-width:66ch}
h2.big{font-family:var(--mono);font-size:.82rem;color:var(--mut);font-weight:500}
"""


JS = """
function fit(el){var b=el.parentElement,lo=3,hi=60,best=3,i,m;
/* max-height:100% clamps .inner, so its scrollHeight is measured against an
   already-capped box and a size that overflows can still pass the test — that
   is how a title lost its last word while still reading correctly in the DOM.
   Lift the clamp for the measurement, then restore it. */
var mh=el.style.maxHeight;el.style.maxHeight='none';
function over(){return el.scrollHeight>b.clientHeight+1||el.scrollWidth>b.clientWidth+1;}
for(i=0;i<9;i++){m=(lo+hi)/2;el.style.fontSize=m+'px';
if(!over()){best=m;lo=m;}else{hi=m;}
if(hi-lo<0.25)break;}
/* Verify, do not trust. The search can land on a size that fits by zero margin —
   one measured title fitted at scrollWidth 376 in a 376px box, then reflowed to
   two lines and lost its last word to overflow:hidden. Step down until the size
   actually chosen does not overflow. */
el.style.fontSize=best.toFixed(2)+'px';
for(i=0;i<24&&best>3&&over();i++){best=best*0.94;el.style.fontSize=best.toFixed(2)+'px';}
el.style.maxHeight=mh;}
function fitAll(){var n=document.querySelectorAll('.blk .inner');for(var i=0;i<n.length;i++)fit(n[i]);}
/* Sizes are computed for one viewport. Without this, resizing the window clips
   text that fitted when the page loaded. */
addEventListener('resize',function(){clearTimeout(window.__rf);window.__rf=setTimeout(fitAll,150);});
window.addEventListener('load',fitAll);
/* Arabic shaping differs enough between the fallback and the real face that a
   size measured before the font resolves can overflow after it does. */
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(fitAll);
var _t;window.addEventListener('resize',function(){clearTimeout(_t);_t=setTimeout(fitAll,150);});
function toggleBoxes(){document.body.classList.toggle('boxes');}
function findText(){var q=prompt('Find in the rebuilt pages:');if(!q)return;
var old=document.querySelectorAll('mark.hit');
for(var i=0;i<old.length;i++){var p=old[i].parentNode;while(old[i].firstChild)p.insertBefore(old[i].firstChild,old[i]);p.removeChild(old[i]);p.normalize();}
var n=0,els=document.querySelectorAll('.blk .inner');
for(var j=0;j<els.length;j++){var w=document.createTreeWalker(els[j],NodeFilter.SHOW_TEXT),hits=[],node;
while(node=w.nextNode()){var k=node.nodeValue.indexOf(q);if(k>=0)hits.push([node,k]);}
for(var h=0;h<hits.length;h++){try{var r=document.createRange();r.setStart(hits[h][0],hits[h][1]);
r.setEnd(hits[h][0],hits[h][1]+q.length);var m=document.createElement('mark');m.className='hit';
r.surroundContents(m);n++;}catch(e){}}}
if(!n)alert('no match — the text searched is what the OCR read, not what the scan shows');
else document.querySelector('mark.hit').scrollIntoView({block:'center'});}
"""


def md_lite(s: str) -> str:
    s = html.escape(s)
    if s.count("|") >= 4:
        rows = [r for r in s.split("\n") if r.strip().startswith("|")]
        if rows:
            out = []
            for r in rows:
                if re.fullmatch(r"[\s|:-]+", r):
                    continue
                out.append("<tr>" + "".join(f"<td>{c.strip()}</td>"
                           for c in r.strip().strip("|").split("|")) + "</tr>")
            return f"<table>{''.join(out)}</table>"
    s = re.sub(r"^\s*#{1,6}\s*(.+)$", r"<b>\1</b>", s, flags=re.M)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s.replace("\n", "<br>")


def sidebar(docs, cur=""):
    out, last = [], None
    for s in docs:
        j = s.split("-")[0]
        if j != last:
            out.append(f'<div class="jh">journal {html.escape(j)}</div>')
            last = j
        cls = " on" if s == cur else ""
        out.append(f'<a class="{cls.strip()}" href="{urllib.parse.quote(s)}.html">{html.escape(s)}</a>')
    return "".join(out)


EXTRA_CSS = """
.split3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.7rem;align-items:start}
.split4{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:.6rem;align-items:start}
@media(max-width:1700px){.split4{grid-template-columns:1fr 1fr}}
@media(max-width:1400px){.split3{grid-template-columns:1fr 1fr}}
@media(max-width:980px){.split3,.split4{grid-template-columns:1fr}}
.pane.mi h2{color:#C4571A}
.pane.az h2{color:#0F6E76}
.pane.hy h2{color:#6B4FA8}
.pane.mi .sheet{box-shadow:inset 0 2px 0 #C4571A}
.pane.az .sheet{box-shadow:inset 0 2px 0 #0F6E76}
.pane.hy .sheet{box-shadow:inset 0 2px 0 #6B4FA8}
.legend{font-family:var(--mono);font-size:.66rem;color:var(--mut);margin:0 0 .9rem}
.legend b{color:var(--fg);font-weight:600}
.missing{padding:2rem .8rem;text-align:center;color:var(--mut);font-family:var(--mono);font-size:.7rem}
"""


def blocks_html(pg, aligns_page, stem, pi, page, img_dir, fitz, crops=True):
    """One rebuilt sheet's worth of absolutely-positioned blocks."""
    dim = pg.get("dimensions") or {}
    W, H = dim.get("width") or 1, dim.get("height") or 1
    divs, types = [], {}
    for bi, b in enumerate(pg.get("blocks") or []):
        t = b.get("type", "text")
        types[t] = types.get(t, 0) + 1
        x0, y0 = b.get("top_left_x", 0), b.get("top_left_y", 0)
        x1, y1 = b.get("bottom_right_x", 0), b.get("bottom_right_y", 0)
        content = b.get("content", "") or ""
        is_img = t == "image" or re.fullmatch(r"\s*!\[[^\]]*\]\([^)]*\)\s*", content)
        if is_img and crops:
            cname = f"{stem}_p{pi+1:03d}_b{bi:03d}.jpg"
            clip = fitz.Rect(x0 / W * page.rect.width, y0 / H * page.rect.height,
                             x1 / W * page.rect.width, y1 / H * page.rect.height)
            cp = page.get_pixmap(dpi=140, clip=clip)
            try:
                (img_dir / cname).write_bytes(cp.tobytes("jpeg", jpg_quality=78))
            except TypeError:
                (img_dir / cname).write_bytes(cp.tobytes("jpeg"))
            inner = f'<img class="crop" src="img/{cname}" alt="figure">'
        else:
            al = (aligns_page.get(str(bi)) or {}).get("align", "justify")
            inner = (f'<div class="inner" dir="rtl" style="text-align:{al}">'
                     f'{md_lite(content)}</div>')
        divs.append(f'<div class="blk" data-t="{html.escape(t)}" '
                    f'style="left:{x0/W*100:.3f}%;top:{y0/H*100:.3f}%;'
                    f'width:{(x1-x0)/W*100:.3f}%;height:{(y1-y0)/H*100:.3f}%;'
                    f'--bc:{TYPE_COLOURS.get(t,"#55636F")}">{inner}</div>')
    return "".join(divs), (W, H), types


def shell(title, body, docs, cur=""):
    return f"""<!doctype html><html lang="ar"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><style>{CSS}{EXTRA_CSS}</style></head><body>
<div class="top"><h1>{html.escape(title)}</h1><span class="sp"></span>
<button onclick="findText()">Find in rebuilt</button>
<button onclick="toggleBoxes()">Show blocks</button>
<a href="index.html">Index</a></div>
<div class="wrap"><aside>{sidebar(docs, cur)}</aside><main>{body}</main></div>
<script>{JS}</script></body></html>"""



def to_blocks(words: list[dict], text: list[str | None], paras: list[dict],
              dims: dict, dpi: int) -> tuple[dict, dict]:
    """Emit the two Mistral-shaped documents: paragraph blocks and word blocks.

    Inches -> pixels here, matching ocr_azure_set.py, so ocr_export_static.py
    draws a hybrid page with exactly the code that draws the other engines. Any
    visible difference is then the OCR, never the renderer.
    """
    def px(b):
        x0, y0, x1, y1 = b
        return (round(x0 * dpi), round(y0 * dpi), round(x1 * dpi), round(y1 * dpi))

    def page_shell():
        return {n: {"index": n - 1,
                    "dimensions": {"dpi": dpi,
                                   "width": max(1, round(dims[n][0] * dpi)),
                                   "height": max(1, round(dims[n][1] * dpi))},
                    "blocks": []} for n in sorted(dims)}

    # word-level: one block per word that received text
    wpages = page_shell()
    for w, t in zip(words, text):
        if not t or not t.strip():
            continue
        x0, y0, x1, y1 = px(w["box"])
        wpages[w["page"]]["blocks"].append(
            {"top_left_x": x0, "top_left_y": y0,
             "bottom_right_x": x1, "bottom_right_y": y1,
             "content": t, "confidence_scores": w.get("conf"), "type": "text"})

    # paragraph-level: Azure's paragraph box, filled with the Gemini words whose
    # Azure counterparts fall inside that paragraph's character span
    ppages = page_shell()
    for p in paras:
        lo, hi = p["off"], p["off"] + p["len"]
        got = [t for w, t in zip(words, text)
               if t and lo <= w["off"] < hi and w["page"] == p["page"]]
        if not got:
            continue
        x0, y0, x1, y1 = px(p["box"])
        ppages[p["page"]]["blocks"].append(
            {"top_left_x": x0, "top_left_y": y0,
             "bottom_right_x": x1, "bottom_right_y": y1,
             "content": " ".join(got), "confidence_scores": None, "type": "text"})

    meta = {"model": "hybrid", "engine": "azure-geometry+gemini-text",
            "api_version": None}
    return ({"pages": list(ppages.values()), **meta},
            {"pages": list(wpages.values()), **meta})
