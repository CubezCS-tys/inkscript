"""The feeler, live: one self-contained page from feel.json.

    python make_page.py out/feel.json out/feel.html
"""
import sys, json
from pathlib import Path

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Feeling the Word</title>
<style>
:root{--bg:#f7f5f0;--panel:#fff;--ink:#1d1b18;--muted:#6b665d;--line:#e3ded3;--accent:#b4532a;--good:#2f7d4f;--bad:#b23b3b;--trail:rgba(180,83,42,.85);--ghost:#c9c3b6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#17161a;--panel:#222126;--ink:#ece8e0;--muted:#a19b90;--line:#36343b;--accent:#e08a5c;--good:#6cc08f;--bad:#e07a7a;--trail:rgba(224,138,92,.9);--ghost:#55525a}}
:root[data-theme="dark"]{--bg:#17161a;--panel:#222126;--ink:#ece8e0;--muted:#a19b90;--line:#36343b;--accent:#e08a5c;--good:#6cc08f;--bad:#e07a7a;--trail:rgba(224,138,92,.9);--ghost:#55525a}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 16px 8px;max-width:1200px;margin:auto}h1{margin:0 0 4px;font-size:22px}header p{margin:4px 0;color:var(--muted);max-width:820px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0}.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
.stat b{display:block;font-size:20px}.stat span{color:var(--muted);font-size:13px}
main{max-width:1200px;margin:auto;padding:0 16px 40px;display:grid;grid-template-columns:200px 1fr;gap:16px}
@media (max-width:760px){main{grid-template-columns:1fr}}
.list{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px;max-height:640px;overflow:auto}
.filters{display:flex;gap:4px;margin-bottom:6px}.filters button,.ctl button{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:6px;padding:4px 8px;cursor:pointer;font:inherit;font-size:13px}
.filters button.on,.ctl button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.chip{display:flex;justify-content:space-between;align-items:center;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:18px;direction:rtl}
.chip:hover{background:var(--bg)}.chip.sel{outline:2px solid var(--accent)}.chip i{font-style:normal;font-size:12px;direction:ltr}
.chip i.ok{color:var(--good)}.chip i.no{color:var(--bad)}
.stage{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media (max-width:760px){.stage{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px;min-width:0}
.card h2{font-size:14px;margin:0 0 2px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}.card .sub{color:var(--muted);font-size:13px;margin:0 0 8px}
canvas{width:100%;display:block;border-radius:6px;background:var(--bg)}
.verdict{display:flex;gap:24px;align-items:baseline;flex-wrap:wrap;margin-top:12px;min-height:56px}
.verdict div{direction:rtl;font-size:28px}.verdict small{display:block;direction:ltr;font-size:12px;color:var(--muted)}
.letters{display:flex;gap:6px;direction:rtl;flex-wrap:wrap;margin-top:6px;min-height:34px}.letters span{padding:2px 8px;border-radius:6px;font-size:20px;color:#fff}
.ctl{display:flex;gap:6px;align-items:center;margin:0 0 12px;flex-wrap:wrap}.ctl label{color:var(--muted);font-size:13px}
.note{color:var(--muted);font-size:13px;margin-top:10px}
</style></head><body>
<header><h1>Feeling the word</h1>
<p>Right: the printed ink, and a pen travelling it the way a stick would on your back — from the first letter to the last, up every stroke and back down, then the dots tapped afterwards. Left: all the feeler gets. It never sees the picture. From what it remembers feeling on pages __TRAIN__, it says the word and where each letter starts and ends, in one pass.</p>
<div class="stats" id="stats"></div></header>
<main><div class="list"><div class="filters"><button data-f="all" class="on">all</button><button data-f="ok">right</button><button data-f="no">wrong</button></div><div id="chips"></div></div>
<div><div class="ctl"><button id="play">▶ Play</button><button id="prev">‹ prev</button><button id="next">next ›</button><label>speed <input id="speed" type="range" min="1" max="10" value="4"></label></div>
<div class="stage">
<div class="card"><h2>What the feeler feels</h2><p class="sub">No picture: the height of the stick over time (the first letter on the right), then the taps.</p><canvas id="feel" height="300"></canvas>
<div class="letters" id="letters"></div></div>
<div class="card"><h2>The ink and the pen</h2><p class="sub">Traced from the scan. After the reading, each letter it felt is coloured on the ink.</p><canvas id="ink" height="300"></canvas></div>
</div>
<div class="card verdict" id="verdict"></div>
<p class="note">The feeler is crude on purpose: it matches remembered feelings, stretched evenly, with no model trained and no knowledge of words. Tooth letters (ب ت ث ن ي) feel alike and are told apart by their taps, which this face often prints as one blob. "Azure" is the reading in the PDF, not checked by hand.</p>
</div></main>
<script>
const D=__DATA__;const P=D.pieces;const S=D.summary;
const css=n=>getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const COLORS=["#2b6cb0","#c05621","#2f855a","#9b2c2c","#6b46c1","#b7791f","#00838f"];
const st=document.getElementById("stats");
const pct=(a,b)=>b?Math.round(100*a/b)+"%":"–";
const by=S.by_len,iso=by["1"]||[0,0];let jr=0,jn=0;for(const k in by){if(k!=="1"){jr+=by[k][0];jn+=by[k][1]}}
st.innerHTML=[[pct(S.right,S.pieces),`pieces read as Azure reads them (${S.right}/${S.pieces})`],[pct(iso[0],iso[1]),"single letters"],[pct(jr,jn),"joined pieces"],[S.letters_right+"%","letters right"],["41%","reading the PICTURE blind (experiment 10)"]].map(([b,s])=>`<div class="stat"><b>${b}</b><span>${s}</span></div>`).join("");
let filt="all",cur=0,anim=null;
function chips(){const c=document.getElementById("chips");c.innerHTML="";P.forEach((p,i)=>{if(filt==="ok"&&!p.right||filt==="no"&&p.right)return;const d=document.createElement("div");d.className="chip"+(i===cur?" sel":"");d.innerHTML=`<span>${p.truth}</span><i class="${p.right?"ok":"no"}">${p.right?"✓":"✗"}</i>`;d.onclick=()=>{cur=i;show(true)};c.appendChild(d)})}
document.querySelectorAll(".filters button").forEach(b=>b.onclick=()=>{document.querySelectorAll(".filters button").forEach(x=>x.classList.remove("on"));b.classList.add("on");filt=b.dataset.f;chips()});
function img(b64){return new Promise(r=>{const im=new Image();im.onload=()=>r(im);im.src="data:image/png;base64,"+b64})}
function fit(cv){const r=window.devicePixelRatio||1,w=cv.clientWidth;cv.width=w*r;cv.height=cv.clientHeight*r;const x=cv.getContext("2d");x.setTransform(r,0,0,r,0,0);return [x,w,cv.clientHeight]}
function bounds(p){return p.cuts.map(c=>{let k=p.walk_s.findIndex(s=>s<c);return k<0?p.walk.length:k})}
async function show(play){chips();cancelAnimationFrame(anim);const p=P[cur];const ink=await img(p.ink),seg=await img(p.seg);
 const segc=document.createElement("canvas");segc.width=p.w;segc.height=p.h;const sx=segc.getContext("2d");sx.drawImage(seg,0,0);const sd=sx.getImageData(0,0,p.w,p.h).data;
 const inkc=document.createElement("canvas");inkc.width=p.w;inkc.height=p.h;const ix=inkc.getContext("2d");ix.drawImage(ink,0,0);const id=ix.getImageData(0,0,p.w,p.h);
 const colored=ix.createImageData(p.w,p.h);for(let i=0;i<p.w*p.h;i++){const dark=id.data[4*i]<128,l=sd[4*i]-1;if(dark){const c=l>=0?COLORS[l%COLORS.length]:"#888";colored.data[4*i]=parseInt(c.slice(1,3),16);colored.data[4*i+1]=parseInt(c.slice(3,5),16);colored.data[4*i+2]=parseInt(c.slice(5,7),16);colored.data[4*i+3]=255}}
 const colc=document.createElement("canvas");colc.width=p.w;colc.height=p.h;colc.getContext("2d").putImageData(colored,0,0);
 const [ic,iw,ih]=fit(document.getElementById("ink"));const sc=Math.min((iw-20)/p.w,(ih-20)/p.h,6),ox=(iw-p.w*sc)/2,oy=(ih-p.h*sc)/2;
 const [fc,fw,fh]=fit(document.getElementById("feel"));
 const N=p.walk.length,B=bounds(p),taps=p.marks;const tapT=12;const total=N+taps.length*tapT+30;
 const hs=p.walk.map(([y,x])=>(p.base-y)/p.rise);const hmin=Math.min(-1,...hs),hmax=Math.max(1.5,...hs);
 const X=t=>fw-14-(fw-28)*t/Math.max(1,N-1),Y=h=>16+(fh-90)*(hmax-h)/(hmax-hmin);
 document.getElementById("letters").innerHTML="";document.getElementById("verdict").innerHTML="";
 let t=play?0:total;const speed=()=>+document.getElementById("speed").value;
 function frame(){t=Math.min(total,t+speed()*Math.max(0.5,N/900));const tw=Math.min(N,Math.floor(t)),done=t>=total;
  // ink side
  ic.clearRect(0,0,iw,ih);ic.imageSmoothingEnabled=false;ic.globalAlpha=done?1:.35;ic.drawImage(done?colc:inkc,ox,oy,p.w*sc,p.h*sc);ic.globalAlpha=1;
  ic.strokeStyle=css("--trail");ic.lineWidth=2;ic.beginPath();for(let k=0;k<tw;k++){const [y,x]=p.walk[k];k?ic.lineTo(ox+x*sc,oy+y*sc):ic.moveTo(ox+x*sc,oy+y*sc)}if(!done)ic.stroke();
  if(tw>0&&tw<N){const [y,x]=p.walk[tw-1];ic.fillStyle=css("--accent");ic.beginPath();ic.arc(ox+x*sc,oy+y*sc,6,0,7);ic.fill()}
  const nt=Math.max(0,Math.floor((t-N)/tapT));taps.slice(0,Math.min(nt+1,taps.length)).forEach((m,k)=>{if(t<N)return;const fresh=k===nt&&!done;ic.strokeStyle=css("--accent");ic.lineWidth=fresh?3:1.5;ic.beginPath();ic.arc(ox+m[3]*sc,oy+m[2]*sc,fresh?12:7,0,7);ic.stroke()});
  // feel side
  fc.clearRect(0,0,fw,fh);fc.strokeStyle=css("--line");fc.lineWidth=1;fc.beginPath();fc.moveTo(14,Y(0));fc.lineTo(fw-14,Y(0));fc.stroke();
  fc.fillStyle=css("--muted");fc.font="12px system-ui";fc.fillText("baseline",16,Y(0)-4);fc.textAlign="right";fc.fillText("← start",fw-14,fh-60);fc.textAlign="left";
  fc.strokeStyle=css("--ink");fc.lineWidth=1.6;fc.beginPath();for(let k=0;k<tw;k++){k?fc.lineTo(X(k),Y(hs[k])):fc.moveTo(X(k),Y(hs[k]))}fc.stroke();
  const ty=fh-40;fc.fillStyle=css("--muted");fc.fillText("taps",16,ty+4);
  if(t>=N)taps.slice(0,Math.min(nt+1,taps.length)).forEach(m=>{const k=p.walk_s.findIndex(s=>s<=m[0]);const x=X(k<0?N-1:k);fc.fillStyle=css("--accent");fc.beginPath();fc.arc(x,m[1]?ty-8:ty+8,4,0,7);fc.fill()});
  if(done){// walk index 0 is the first letter (drawn on the right); segment k runs from boundary k to k+1
   const order=[0,...B.slice().sort((a,b)=>a-b),N];for(let k=0;k<order.length-1;k++){const b=order[k],a=order[k+1];fc.fillStyle=COLORS[k%COLORS.length]+"22";fc.fillRect(X(b),10,X(a)-X(b),ty-24);
    fc.fillStyle=COLORS[k%COLORS.length];fc.font="20px serif";fc.textAlign="center";fc.fillText(p.letters[k]||"?",(X(a)+X(b))/2,ty-20);fc.textAlign="left"}
   B.forEach(b=>{fc.strokeStyle=css("--accent");fc.setLineDash([4,3]);fc.beginPath();fc.moveTo(X(b),10);fc.lineTo(X(b),ty-14);fc.stroke();fc.setLineDash([])});
   document.getElementById("letters").innerHTML=p.letters.map((l,k)=>`<span style="background:${COLORS[k%COLORS.length]}">${l}</span>`).join("");
   document.getElementById("verdict").innerHTML=`<div>${p.got||"—"}<small>the feeler says</small></div><div>${p.truth}<small>Azure's reading</small></div><div style="color:var(--${p.right?"good":"bad"})">${p.right?"✓ same":"✗ different"}<small>page ${p.page} · ${p.n} letter${p.n>1?"s":""}</small></div>`}
  if(!done)anim=requestAnimationFrame(frame)}
 frame()}
document.getElementById("play").onclick=()=>show(true);document.getElementById("next").onclick=()=>{cur=(cur+1)%P.length;show(true)};document.getElementById("prev").onclick=()=>{cur=(cur-1+P.length)%P.length;show(true)};
addEventListener("resize",()=>show(false));show(true);
</script></body></html>"""


def main(src, out):
    d = json.load(open(src))
    # interesting first: joined pieces read right, then wrong ones, then the rest
    d["pieces"].sort(key=lambda p: (not (p["right"] and p["n"] > 1), p["right"], -p["n"]))
    html = PAGE.replace("__DATA__", json.dumps(d, ensure_ascii=False)).replace("__TRAIN__", ", ".join(map(str, d["summary"]["train"])))
    Path(out).write_text(html, encoding="utf-8"); print(out, f"{len(html) / 1e6:.1f} MB")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
