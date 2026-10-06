"""The overnight report as one page: what each idea bought, on pages no method ever saw, shown on the ink.

    python make_report.py          # reads out/results.jsonl + out/report_data.json, writes out/report.html
"""
import json
from pathlib import Path
import bench

STEPS = [  # (method, plain name, what changed) — in the order the ideas came
    ("feel_v1", "The first feeler", "remembered letters, stretched evenly; dots counted"),
    ("warp_gate", "+ a better memory", "every training letter remembered; a letter competes only if its examples crowd round"),
    ("taps_prior", "+ dots by size and shape, + letter habits", "a merged two-dot blob felt as two; which letters usually follow which"),
    ("combo_best", "both of those together", "the memory and the dots and habits combined"),
    ("model_ctc_ft", "a small trained reader", "learns the feel of every letter from all four books, then each book's own"),
    ("hybrid_ctc_geo", "trained reader + cuts from the ink", "the reader names the letters, the pen path decides where they split"),
]
NAMES = {"0582": "a 1950s heavy face", "0618": "a typewriter-like face", "1036": "a modern face", "0772": "a dense journal face"}

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reading by Feel</title>
<style>
:root{color-scheme:light;--bg:#f7f5f0;--surface:#fcfcfb;--panel:#ffffff;--ink:#0b0b0b;--text2:#52514e;--muted:#6f6d68;--line:#e4e1da;--grid:#ecebe7;
--s1:#2a78d6;--s2:#eb6834;--good:#1f7a43;--bad:#b42f2f;--l0:#2a78d6;--l1:#eb6834;--l2:#1baf7a;--l3:#eda100;--l4:#e87ba4;--l5:#008300;--l6:#4a3aa7}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#141413;--surface:#1a1a19;--panel:#1f1f1e;--ink:#ffffff;--text2:#c3c2b7;--muted:#9a988f;--line:#33322f;--grid:#2a2a28;
--s1:#3987e5;--s2:#d95926;--good:#5fbf86;--bad:#e46c6c;--l0:#3987e5;--l1:#d95926;--l2:#199e70;--l3:#c98500;--l4:#d55181;--l5:#008300;--l6:#9085e9}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#141413;--surface:#1a1a19;--panel:#1f1f1e;--ink:#ffffff;--text2:#c3c2b7;--muted:#9a988f;--line:#33322f;--grid:#2a2a28;
--s1:#3987e5;--s2:#d95926;--good:#5fbf86;--bad:#e46c6c;--l0:#3987e5;--l1:#d95926;--l2:#199e70;--l3:#c98500;--l4:#d55181;--l5:#008300;--l6:#9085e9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1080px;margin:auto;padding:28px 16px 60px}h1{font-size:30px;margin:0 0 6px;letter-spacing:-.01em}h2{font-size:21px;margin:44px 0 6px}
.lede{color:var(--text2);max-width:760px;margin:0}.small{font-size:14px;color:var(--muted)}
.hero{display:flex;gap:16px;flex-wrap:wrap;align-items:stretch;margin:24px 0 8px}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px 20px;min-width:200px;flex:1}
.tile b{display:block;font-size:44px;line-height:1.1;font-variant-numeric:tabular-nums}.tile span{color:var(--text2);font-size:14px}
.arrow{align-self:center;font-size:28px;color:var(--muted)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin-top:12px}
.bars{display:grid;grid-template-columns:minmax(150px,280px) 1fr;gap:10px 14px;align-items:center}
.bars .lab b{display:block;font-size:15px}.bars .lab span{font-size:13px;color:var(--muted)}
.track{position:relative;height:30px;background:var(--surface);border-radius:4px}
.track .fill{position:absolute;left:0;top:5px;bottom:5px;background:var(--s1);border-radius:0 4px 4px 0}
.track .fill.best{background:var(--s2)}.track .v{position:absolute;top:50%;transform:translateY(-50%);font-size:14px;font-weight:600;font-variant-numeric:tabular-nums;color:var(--ink)}
.track .dot{position:absolute;top:50%;width:9px;height:9px;margin:-4.5px 0 0 -4.5px;border-radius:50%;background:var(--panel);border:2px solid var(--ink);opacity:.65;cursor:default}
.track .ref{position:absolute;top:-2px;bottom:-2px;width:0;border-left:2px dashed var(--muted)}
.axis{display:grid;grid-template-columns:minmax(150px,280px) 1fr;gap:14px;font-size:12px;color:var(--muted)}.axis .ticks{display:flex;justify-content:space-between}
@media (max-width:640px){.bars,.axis{grid-template-columns:1fr}.axis div:first-child{display:none}}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:14px;color:var(--text2);margin:6px 0 10px}.legend i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.len{display:flex;gap:18px;align-items:flex-end;height:220px;padding:10px 4px 0;border-bottom:1px solid var(--line)}
.len .grp{flex:1;display:flex;gap:2px;align-items:flex-end;height:100%;position:relative}
.len .b{flex:1;border-radius:4px 4px 0 0;position:relative}.len .b em{position:absolute;top:-20px;left:0;right:0;text-align:center;font-style:normal;font-size:12px;color:var(--text2);font-variant-numeric:tabular-nums}
.lenx{display:flex;gap:18px;padding:6px 4px 0;font-size:13px;color:var(--text2)}.lenx div{flex:1;text-align:center}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}.tabs button{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:6px 12px;font:inherit;font-size:14px;cursor:pointer}
.tabs button.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.kinds{display:flex;gap:6px;flex-wrap:wrap}.kinds button{font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:10px}
.w{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px;display:flex;flex-direction:column;gap:6px}
.w canvas{width:100%;height:120px;background:var(--surface);border-radius:6px}
.w .r{display:flex;justify-content:space-between;align-items:baseline;gap:8px}.w .r span{font-size:12px;color:var(--muted)}
.w .ar{direction:rtl;font-size:22px;font-family:"Noto Naskh Arabic","Amiri","Traditional Arabic",serif}
.tag{font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid currentColor}.tag.good{color:var(--good)}.tag.bad{color:var(--bad)}.tag.n{color:var(--text2)}
.w .chips{display:flex;gap:4px;direction:rtl;flex-wrap:wrap}.w .chips b{color:#fff;border-radius:5px;padding:0 6px;font-size:16px;font-weight:500}
.toggle{font-size:13px;color:var(--text2);cursor:pointer;user-select:none}
.cta{display:inline-block;margin-top:10px;padding:10px 16px;border-radius:10px;background:var(--s1);color:#fff;text-decoration:none;font-weight:600}
ul.plain{padding-left:20px;margin:8px 0}ul.plain li{margin:4px 0}
details{margin-top:10px}summary{cursor:pointer;color:var(--text2)}table{border-collapse:collapse;font-size:14px;margin-top:8px;width:100%}td,th{padding:4px 8px;border-bottom:1px solid var(--line);text-align:right;font-variant-numeric:tabular-nums}td:first-child,th:first-child{text-align:left}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);font-size:13px;padding:6px 8px;border-radius:6px;opacity:0;transition:opacity .1s;z-index:9}
</style></head><body><div id="tip"></div><div class="wrap">
<h1>Reading Arabic print by feel</h1>
<p class="lede">Overnight, __DATE__. The idea: a stick writes a word on your back, and without looking you know the word and where each letter starts and ends. The machine gets only that: the path of the pen through the printed ink, never the picture. Every number below is on pages <b>no method ever saw</b>, read once at the end, in four books in four typefaces. "Right" means it reads the piece of ink the way Azure does.</p>
<div class="hero">
 <div class="tile"><b id="h0"></b><span>pieces read right by the first feeler (yesterday's page)</span></div><div class="arrow">→</div>
 <div class="tile"><b id="h1" style="color:var(--s2)"></b><span>by the best feeler this morning, never seeing the picture</span></div>
 <div class="tile"><b id="h2"></b><span>of single letters read right by the best feeler</span></div>
</div>
<p class="small">A <i>piece</i> is one connected stroke of ink: a lone letter, or a run of joined letters like <span class="ar" style="font-size:18px">لمعجم</span>. Averaged over the four books; each book counts the same.</p>

<h2>Each idea, and what it bought</h2>
<p class="lede">Bar = average over the four books. The small rings are the four books one by one (hover for which). The dashed line is reading the <i>picture</i> blind (experiment 10, one book).</p>
<div class="card"><div class="bars" id="bars"></div><div class="axis"><div></div><div class="ticks"><span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span></div></div></div>

<h2>Longer joined words are the hard part</h2>
<p class="lede">Pieces read right, by how many letters are joined in the piece.</p>
<div class="legend"><span><i style="background:var(--s1)"></i>first feeler</span><span><i style="background:var(--s2)"></i>best feeler</span></div>
<div class="card"><div class="len" id="len"></div><div class="lenx" id="lenx"></div></div>

<h2>On the ink</h2>
<p class="lede">Real pieces from the unseen pages. Each letter the best feeler felt is coloured on the ink, in reading order (blue is the first letter, on the right). Tap a card to see how the first feeler cut and read the same ink.</p>
<div class="tabs" id="doctabs"></div>
<div class="tabs kinds" id="kinds"></div>
<div class="grid" id="grid"></div>
<a class="cta" href="feel_best.html">Watch the best feeler work, live →</a>

<h2>What it means</h2>
<ul class="plain" id="means"></ul>

<details><summary>How this was measured, and every number</summary>
<p class="small">Four scanned documents from the archive (0582, 0618, 1036, 0772). Each split into pages to learn from, pages to tune on, and pages held back. Four research agents worked on the tuning pages only; this page shows the held-back pages, each method run once. The truth is Azure's reading, not checked by hand. The cuts are compared with the letter cutter's, which is itself not ground truth. Full notes: <code>experiments/16_feel/notes/</code>; every run: <code>out/results.jsonl</code>.</p>
<table id="tbl"></table></details>
</div>
<script>
const R=__RESULTS__, EX=__EXAMPLES__, STEPS=__STEPS__, NAMES=__NAMES__, DOCS=__DOCS__;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const tip=document.getElementById("tip");function hover(el,txt){el.onmousemove=e=>{tip.textContent=txt;tip.style.left=(e.clientX+12)+"px";tip.style.top=(e.clientY+12)+"px";tip.style.opacity=1};el.onmouseleave=()=>tip.style.opacity=0}
const steps=STEPS.filter(s=>R[s[0]]);const first=R["feel_v1"],best=R[steps[steps.length-1][0]];
const bestIso=DOCS.reduce((a,d)=>{const x=best.docs[d].by_len["1"];return [a[0]+x[0],a[1]+x[1]]},[0,0]);
document.getElementById("h0").textContent=Math.round(first.total.mean_doc_piece_acc)+"%";document.getElementById("h1").textContent=Math.round(best.total.mean_doc_piece_acc)+"%";document.getElementById("h2").textContent=Math.round(100*bestIso[0]/bestIso[1])+"%";
const bars=document.getElementById("bars");
steps.forEach(([m,name,what],i)=>{const r=R[m],v=r.total.mean_doc_piece_acc,isb=i===steps.length-1;
 const lab=document.createElement("div");lab.className="lab";lab.innerHTML=`<b>${name}</b><span>${what}</span>`;bars.appendChild(lab);
 const t=document.createElement("div");t.className="track";t.innerHTML=`<div class="fill${isb?" best":""}" style="width:${v}%"></div><div class="v" style="left:10px;color:#fff">${v.toFixed(1)}%</div><div class="ref" style="left:41%"></div>`;
 DOCS.forEach(d=>{const x=r.docs[d].piece_acc;const dot=document.createElement("div");dot.className="dot";dot.style.left=x+"%";hover(dot,`${d} (${NAMES[d]}): ${x.toFixed(1)}%`);t.appendChild(dot)});
 hover(t.querySelector(".fill"),`${name}: ${v.toFixed(1)}% on average (${r.total.right} of ${r.total.pieces} pieces)`);bars.appendChild(t)});
const L=["1","2","3","4","5"],LN=["1 letter","2 letters","3 letters","4 letters","5 or more"];const agg=(r,k)=>DOCS.reduce((a,d)=>{const x=r.docs[d].by_len[k]||[0,0];return [a[0]+x[0],a[1]+x[1]]},[0,0]);
const len=document.getElementById("len"),lenx=document.getElementById("lenx");
L.forEach((k,i)=>{const g=document.createElement("div");g.className="grp";[[first,"--s1","first feeler"],[best,"--s2","best feeler"]].forEach(([r,c,nm])=>{const [a,n]=agg(r,k),p=n?100*a/n:0;const b=document.createElement("div");b.className="b";b.style.height=p+"%";b.style.background=`var(${c})`;b.innerHTML=`<em>${Math.round(p)}%</em>`;hover(b,`${LN[i]}, ${nm}: ${a} of ${n} pieces (${p.toFixed(1)}%)`);g.appendChild(b)});len.appendChild(g);const x=document.createElement("div");x.textContent=LN[i];lenx.appendChild(x)});
const LC=["--l0","--l1","--l2","--l3","--l4","--l5","--l6"].map(css);const hex=c=>[parseInt(c.slice(1,3),16),parseInt(c.slice(3,5),16),parseInt(c.slice(5,7),16)];
function img(b64){return new Promise(r=>{const im=new Image();im.onload=()=>r(im);im.src="data:image/png;base64,"+b64})}
async function paint(cv,p,seg){const ink=await img(p.ink),sg=await img(seg);const W=p.w,H=p.h;const a=document.createElement("canvas");a.width=W;a.height=H;const x=a.getContext("2d");x.drawImage(ink,0,0);const id=x.getImageData(0,0,W,H);
 const b=document.createElement("canvas");b.width=W;b.height=H;const y=b.getContext("2d");y.drawImage(sg,0,0);const sd=y.getImageData(0,0,W,H).data;const out=x.createImageData(W,H);
 for(let i=0;i<W*H;i++){if(id.data[4*i]<128){const l=sd[4*i]-1,c=l>=0?hex(LC[l%LC.length]):[128,128,128];out.data.set([...c,255],4*i)}}x.putImageData(out,0,0);
 const r=devicePixelRatio||1,cw=cv.clientWidth,ch=cv.clientHeight;cv.width=cw*r;cv.height=ch*r;const g=cv.getContext("2d");g.setTransform(r,0,0,r,0,0);g.imageSmoothingEnabled=true;const s=Math.min((cw-16)/W,(ch-16)/H,4);g.drawImage(a,(cw-W*s)/2,(ch-H*s)/2,W*s,H*s)}
let doc=DOCS[0],kind="all";const KINDS=[["all","all"],["fixed","fixed overnight"],["long","long words read right"],["wrong","still wrong"]];
const dt=document.getElementById("doctabs");DOCS.forEach(d=>{const b=document.createElement("button");b.textContent=`${d} · ${NAMES[d]}`;b.onclick=()=>{doc=d;draw()};dt.appendChild(b)});
const kt=document.getElementById("kinds");KINDS.forEach(([k,n])=>{const b=document.createElement("button");b.textContent=n;b.onclick=()=>{kind=k;draw()};kt.appendChild(b)});
function draw(){[...dt.children].forEach((b,i)=>b.classList.toggle("on",DOCS[i]===doc));[...kt.children].forEach((b,i)=>b.classList.toggle("on",KINDS[i][0]===kind));
 const g=document.getElementById("grid");g.innerHTML="";(EX[doc]||[]).filter(p=>kind==="all"||p.kind===kind).forEach(p=>{const w=document.createElement("div");w.className="w";
 const tag=p.kind==="wrong"?`<span class="tag bad">still wrong</span>`:p.kind==="fixed"?`<span class="tag good">fixed overnight</span>`:`<span class="tag n">${p.n} letters, right</span>`;
 w.innerHTML=`<div class="r">${tag}<span>page ${p.page}</span></div><canvas></canvas><div class="chips">${p.letters.map((l,k)=>`<b style="background:${LC[k%LC.length]}">${l}</b>`).join("")}</div>
 <div class="r"><div class="ar">${p.got||"—"}</div><span>best feeler</span></div><div class="r"><div class="ar" style="color:var(--text2)">${p.truth}</div><span>Azure</span></div>
 <div class="r"><div class="ar" style="color:var(--muted);font-size:18px">${p.v1||"—"}</div><span>first feeler</span></div><div class="toggle">▸ show the first feeler's cuts</div>`;
 g.appendChild(w);const cv=w.querySelector("canvas");let alt=false;paint(cv,p,p.seg);w.querySelector(".toggle").onclick=()=>{alt=!alt;paint(cv,p,alt?p.v1_seg:p.seg);w.querySelector(".toggle").textContent=alt?"▸ show the best feeler's cuts":"▸ show the first feeler's cuts"}})}
draw();
const m=document.getElementById("means");__MEANS__.forEach(t=>{const li=document.createElement("li");li.innerHTML=t;m.appendChild(li)});
const tb=document.getElementById("tbl");tb.innerHTML=`<tr><th>method</th>${DOCS.map(d=>`<th>${d}</th>`).join("")}<th>average</th><th>letters</th></tr>`+steps.map(([mm,nm])=>{const r=R[mm];return `<tr><td>${nm}</td>${DOCS.map(d=>`<td>${r.docs[d].piece_acc.toFixed(1)}%</td>`).join("")}<td>${r.total.mean_doc_piece_acc.toFixed(1)}%</td><td>${r.total.mean_doc_letter_acc.toFixed(1)}%</td></tr>`}).join("");
</script></body></html>"""


def main(means, date="6 October 2026", combo=None):
    final = {}
    for l in open(bench.LOG):
        r = json.loads(l)
        if r["split"] == "test": final[r["method"]] = r                # the last test run of each method
    if combo and combo in final: final["combo_best"] = final[combo]
    ex = json.load(open(bench.OUT / "report_data.json"))
    html = (PAGE.replace("__RESULTS__", json.dumps(final)).replace("__EXAMPLES__", json.dumps(ex["docs"], ensure_ascii=False))
            .replace("__STEPS__", json.dumps(STEPS, ensure_ascii=False)).replace("__NAMES__", json.dumps(NAMES))
            .replace("__DOCS__", json.dumps(list(bench.SUITE))).replace("__MEANS__", json.dumps(means, ensure_ascii=False)).replace("__DATE__", date))
    (bench.OUT / "report.html").write_text(html, encoding="utf-8"); print(bench.OUT / "report.html", f"{len(html) / 1e6:.1f} MB")


if __name__ == "__main__":
    import sys
    main(json.load(open(sys.argv[1])) if len(sys.argv) > 1 else [], combo=sys.argv[2] if len(sys.argv) > 2 else None)
