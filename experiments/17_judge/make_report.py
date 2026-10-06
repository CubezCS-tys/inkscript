"""The visual page for the owner: out/report.html (self-contained, light/dark, phone width).

    .venv/bin/python make_report.py
Reads out/summary.json, out/judged_tallied.json, out/calibration/*.json, out/crops/*.png, out/spend.jsonl.
"""
import json, base64, html, sys
from pathlib import Path
import cv2
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
sys.path.insert(0, str(HERE))
import judge as J

# The eleven disagreements where the judge did not side with Azure, and the one agreement it flagged, each looked at by
# hand in the crop (2026-10-06, by the agent that ran this; not the owner). What the ink shows, in plain words.
REVIEW = {
    "dis:0772:14:53:3:0": "real Azure error: the print says لمساهمة (after نسبة); Azure added the alef of ال",
    "dis:1036:1:16:3:1": "real Azure error: the print says نشاطا; Azure dropped the final alef. The feeler read it",
    "dis:1036:1:16:3:0": "the same Azure error (نشاطا) seen through the word's other piece; there the feeler was wrong too",
    "dis:1036:1:6:0:1": "the judge says the print has one ya (التغير), Azure two; too close to settle by eye here",
    "dis:0618:16:13:5:3": "Azure wrote the Persian ya ی, which looks the same as ى here: an encoding slip, it breaks search for الاسلامى",
    "dis:0618:1:14:2:0": "box artefact: the alef was never attached to the word, so the tint covered ن alone (the print reads ان, no hamza)",
    "dis:1036:1:0:0:0": "box artefact: Azure's box for عملية spans a whole title block; the judge reads عملية, as Azure does",
    "dis:0772:16:0:0:0": "a faint running header; the judge reads لجنة, the feeler خة, Azure المجلة. Unsettled",
    "dis:0772:23:18:2:2": "punctuation only: the judge wants the comma; Azure's letters are right",
    "dis:0772:18:8:7:0": "punctuation only: a footnote mark (1); Azure's letters are right",
    "dis:0772:18:13:0:1": "punctuation only: a footnote mark (٢); Azure's letters are right",
    "agree:1036:1:16:7:1": "judge error: no hamza is printed under the alif; likely the blue bar below read as one",
}
COL = {"azure": "var(--az)", "feeler": "var(--fe)", "neither": "var(--ne)", "unsure": "var(--un)"}
NAME = {"azure": "Azure right", "feeler": "Feeler right", "neither": "Both wrong", "unsure": "Can't tell"}


def img64(path_or_img, q=55):
    img = cv2.imread(str(path_or_img)) if isinstance(path_or_img, (str, Path)) else path_or_img
    ok, b = cv2.imencode(".webp", img, [cv2.IMWRITE_WEBP_QUALITY, q])
    return "data:image/webp;base64," + base64.b64encode(b.tobytes()).decode()


def bar(t, keys=("azure", "feeler", "neither", "unsure"), label=""):
    n = max(1, t["n"]); segs = "".join(
        f'<span class="seg" style="width:{100 * t[k] / n:.2f}%;background:{COL[k]}" title="{NAME[k]}: {t[k]} of {t["n"]}">'
        f'{(str(round(100 * t[k] / n)) + "%") if t[k] / n > 0.07 else ""}</span>' for k in keys if t[k])
    return f'<div class="row"><div class="lab">{label}<small>{t["n"]}</small></div><div class="bar">{segs}</div></div>'


def main():
    S = json.load(open(OUT / "summary.json")); items = json.load(open(OUT / "judged_tallied.json"))["items"]
    cal = {m: json.load(open(OUT / f"calibration/{m}_b6.json")) for m in ("gemini-3.1-pro-preview", "gemini-3.8-flash")}
    spend = [json.loads(l) for l in open(OUT / "spend.jsonl")]; usd = sum(s["usd"] for s in spend)
    D = S["disagreements"]; A = S["agreements"]

    # calibration
    calrows = ""
    for m, c in cal.items():
        p, ne = c["summary"]["pairs"], c["summary"]["neither"]
        rw = c["summary"]["pairs, look-alike a real word"]
        calrows += (f'<tr><td><b>{m}</b></td><td>{p["right"]}/{p["n"]} <span class="pct">{100 * p["right"] / p["n"]:.1f}%</span></td>'
                    f'<td>{rw["right"]}/{rw["n"]}</td><td>{ne["right"]}/{ne["n"]}</td><td>{p["unsure"] + ne["unsure"]}</td></tr>')
    pro = cal["gemini-3.1-pro-preview"]["rows"]
    gold_imgs = {}
    for stem, pn in (("0005-032-001-001", 2), ("1110-000-001-001", 1)):
        g = J.page_image(OUT / "gold_docs" / stem / f"{stem}.pdf", pn)
        for r in pro:
            if r["stem"] == stem and (r["test"] == "special" or r["ok"] is False): gold_imgs[r["id"]] = img64(J.crop(g, r["box"]))
    calcards = ""
    for r in pro:
        if r["id"] not in gold_imgs: continue
        what = ("owner: " + r["kind"].split(": ")[1]) if r["test"] == "special" else "judge's one miss"
        pick = {"r1": r["real"], "r2": r["alt"], "neither": "neither: " + r["text"], "unsure": "can't tell"}[r["verdict"]]
        calcards += (f'<div class="card"><img src="{gold_imgs[r["id"]]}" alt=""><div class="meta"><span class="tag">{what}</span>'
                     f'<div class="rd"><span>owner\'s page</span><b dir="rtl">{html.escape(r["real"])}</b></div>'
                     f'<div class="rd"><span>offered against</span><b dir="rtl">{html.escape(r["alt"])}</b></div>'
                     f'<div class="rd"><span>judge</span><b dir="rtl">{html.escape(pick)}</b></div><p class="why">{html.escape(r["why"])}</p></div></div>')

    # cards
    data = []
    for f in items:
        if f["test"] != "dis" and f["v"] not in ("neither", "feeler"): continue
        p = OUT / "crops" / (f["id"].replace(":", "_") + ".png")
        if not p.exists(): continue
        data.append(dict(t=f["test"], v=f["v"] if f["test"] == "dis" else "agreewrong", k=f["kind"], d=f["doc"], pg=f["page"], n=f["letters"],
                         az=f["azure"], fe=f["other"], rv=REVIEW.get(f["id"], ""), ap=f["azure_piece"], fp=f["feel_piece"], tx=f.get("text", ""), why=f.get("why", ""), im=img64(p)))
    rank = {"feeler": 0, "neither": 1, "agreewrong": 2, "unsure": 3, "azure": 4}
    data.sort(key=lambda d: rank[d["v"]])
    kinds = list(S["by_kind"])
    # on the way: the first marking (v1) misled the judge; show two of its crops with what the judge said then
    v1 = {f["id"]: f for f in json.load(open(OUT / "v1/judged_tallied.json"))["items"]}
    v1cards = ""
    for iid, note in (("agree:0618:1:17:0:0", "the blue bar under a lone alef was read as a hamza below"),
                      ("dis:0772:18:20:11:0", "the red box's edge hid the alef of ال, so 'لعدد' looked right"),
                      ("v2", "second marking, a red bar in a margin above the line: the judge read the word of the line above (the owner's word was كان)")):
        f = v1.get(iid); pth = OUT / "v1/crops" / (iid.replace(":", "_") + ".png")
        if iid == "v2":
            f = dict(text="بغية", why="The red bar is above the word 'بغية' (ba, ghayn, ya, ta marbuta)."); pth = OUT / "v2/kan_v2.png"
        if not f or not pth.exists(): continue
        v1cards += (f'<div class="card"><img src="{img64(pth)}" alt=""><div class="meta"><span class="tag kd">{"second" if iid == "v2" else "first"} marking</span>'
                    f'<div class="rd"><span>judge then said</span><b dir="rtl">{html.escape(f.get("text") or f["other"])}</b></div><p class="why">{html.escape(note)}. '
                    f'Judge: “{html.escape(f.get("why", ""))}”</p></div></div>')

    head_bar = bar(D, label="All")
    books = "".join(bar(t, label=f"book {d}") for d, t in S["by_book"].items())
    lens = "".join(bar(t, label=f"{l} letter{'s' if l != '1' else ''}") for l, t in S["by_len"].items() if t["n"])
    kindbars = "".join(bar(t, label=k) for k, t in S["by_kind"].items())
    legend = "".join(f'<span class="lg"><i style="background:{COL[k]}"></i>{NAME[k]}</span>' for k in COL)
    feeler_right = D["feeler"]; az_wrong = D["feeler"] + D["neither"]
    page = TEMPLATE
    for k, v in dict(
        HEAD=head_bar, V1CARDS=v1cards, NPG=str(len(list((OUT / "pieces").glob("*.json")))), BOOKS=books, LENS=lens, KINDS=kindbars, LEGEND=legend, CALROWS=calrows, CALCARDS=calcards,
        N=str(D["n"]), NP=str(S["pieces"]["total"]), DP=str(S["pieces"]["disagree_pct"]), AZ=str(D["azure_pct"]), FE=str(D["feeler_pct"]),
        NE=str(D["neither_pct"]), UN=str(D["unsure_pct"]), FEN=str(feeler_right), AGN=str(A["n"]), AGW=str(A["wrong"]), AGP=str(A["wrong_pct"]),
        USD=f"{usd:.2f}", REQ=str(len(spend)), MODEL=S["model"],
        DATA=json.dumps(data, ensure_ascii=False), KINDLIST=json.dumps(kinds, ensure_ascii=False)).items():
        page = page.replace("__" + k + "__", v)
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print(OUT / "report.html", f"{len(page) / 1e6:.1f} MB, {len(data)} cards")


TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Who Reads Right</title>
<style>
:root{--bg:#f7f5f0;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e2ddd3;--az:#3b6fb6;--fe:#d08a1e;--ne:#b4413a;--un:#a8a29a;--chip:#ece7dd}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171614;--fg:#ece8e0;--mut:#a29d93;--card:#22201d;--line:#37332e;--az:#6d9be0;--fe:#e3a647;--ne:#e0695f;--un:#77726a;--chip:#2e2b27}}
:root[data-theme="dark"]{--bg:#171614;--fg:#ece8e0;--mut:#a29d93;--card:#22201d;--line:#37332e;--az:#6d9be0;--fe:#e3a647;--ne:#e0695f;--un:#77726a;--chip:#2e2b27}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px 60px}h1{font-size:1.7rem;margin:.2em 0}h2{font-size:1.15rem;margin:2em 0 .5em}
p{max-width:760px}.mut{color:var(--mut)}.big{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;flex:1 1 150px}.stat b{font-size:1.8rem;display:block}
.row{display:flex;align-items:center;gap:10px;margin:6px 0}.lab{width:170px;flex:none;font-size:.9rem}.lab small{color:var(--mut);margin-left:6px}
.bar{flex:1;display:flex;height:24px;border-radius:5px;overflow:hidden;background:var(--chip)}.seg{color:#fff;font-size:.75rem;display:flex;align-items:center;justify-content:center;white-space:nowrap;overflow:hidden}
.lg{margin-right:14px;font-size:.88rem}.lg i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:5px;vertical-align:-1px}
table{border-collapse:collapse;width:100%;max-width:760px;background:var(--card);border:1px solid var(--line);border-radius:8px}td,th{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;font-size:.9rem}.pct{color:var(--mut)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.card img{width:100%;display:block;background:#fff}.meta{padding:9px 11px}.rd{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.rd span{color:var(--mut);font-size:.8rem}
.rd b{font-size:1.25rem;font-weight:500;font-family:"Noto Naskh Arabic","Amiri","Traditional Arabic",serif}.why{color:var(--mut);font-size:.82rem;margin:.4em 0 0}
.tag{display:inline-block;font-size:.75rem;padding:1px 8px;border-radius:10px;color:#fff;margin-right:5px}.kd{background:var(--chip);color:var(--fg)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.chips button{border:1px solid var(--line);background:var(--chip);color:var(--fg);border-radius:14px;padding:3px 11px;font:inherit;font-size:.85rem;cursor:pointer}
.chips button.on{background:var(--fg);color:var(--bg)}#more{margin:16px auto;display:block;padding:8px 18px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);font:inherit;cursor:pointer}
.box{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;max-width:760px}
@media (max-width:560px){.lab{width:105px;font-size:.8rem}.cards{grid-template-columns:1fr}}
</style></head><body><main>
<h1>Where the feeler and Azure disagree, who is right?</h1>
<p class="mut">Experiment 17 · 2026-10-06 · judge: <b>__MODEL__</b>, shown the scanned ink of each word in its line and two readings as A and B, never told which came from Azure.</p>
<p>The feeler (experiment 16, reading the pen path alone) read __NP__ pieces on __NPG__ pages of three books it had never seen (trained, tuned or tested on); it read __DP__% of them differently from Azure. __N__ of those disagreements were judged.</p>
<div class="big">
<div class="stat"><b style="color:var(--az)">__AZ__%</b>Azure right, the feeler wrong</div>
<div class="stat"><b style="color:var(--fe)">__FE__%</b>the feeler right, Azure wrong (__FEN__ pieces)</div>
<div class="stat"><b style="color:var(--ne)">__NE__%</b>both wrong</div>
<div class="stat"><b style="color:var(--un)">__UN__%</b>can't tell from the ink</div>
</div>
<div>__LEGEND__</div>
__HEAD__
<div class="box" style="margin-top:14px"><p style="margin:0"><b>Looked at by hand, the 11 where the judge did not side with Azure:</b> 2 are real Azure letter errors the feeler caught (لمساهمة, نشاطا), 1 more is likely (التغير), 1 is an encoding slip (Persian ی for ى); 3 are punctuation only, 2 are box artefacts, 1 is an unsettled faint header. So Azure misread the letters in about 3 of 800 disagreements, 4 with the encoding slip. Filter the cards below by "Feeler right" or "Both wrong" to see each.</p></div>
<h2>Can the judge be trusted? Its calibration on the owner's gold pages</h2>
<p>Words the owner marked correct (two pages, experiment 12), each shown with its real reading against a look-alike — one dot group changed, ة/ه, ى/ي, or a hamza added or removed. Half the look-alikes are themselves real words, so "pick the one that is a word" does not win. And "neither" items: two different look-alikes, the real reading missing.</p>
<table><tr><th>model</th><th>real vs look-alike</th><th>…look-alike is a real word</th><th>"neither" spotted</th><th>can't tell</th></tr>__CALROWS__</table>
<p class="mut">Pro was chosen (numbers from the final marking; Pro scored 119/120 and 30/30 with the first marking, and fell to 110/120 with the second — see below). Limits: both gold pages are clean prints, and a look-alike differs by exactly one mark; the disagreements below are often messier ink. The owner's own marks disagree with themselves on two words (التكويني marked a dot error on one sheet, right on the other; طرح and صرح both marked right) — the judge's view of those, and its one miss, are here:</p>
<div class="cards">__CALCARDS__</div>
<h2>On the way: how the word is marked matters</h2>
<p>The first run drew a red box round the word and a blue bar just under the disputed piece; it misled the judge in two ways. The second moved the marks into white margins, and the judge then read the line above. The final marking tints only the paper behind the word pale yellow and puts the piece's blue bar in a margin below; nothing touches the ink, and the strip is only as tall as the word's own line. Every number on this page is from that third marking; the earlier runs are kept in out/v1 and out/v2.</p>
<div class="cards">__V1CARDS__</div>
<h2>By book</h2>__BOOKS__
<h2>By piece length (Azure's letters)</h2>__LENS__
<h2>By kind of difference</h2>
<p class="mut">"dots": the same skeleton, different dots. "other letter": one letter differs in shape. "several letters": more than one change — usually the feeler lost its way.</p>__KINDS__
<h2>The inverse risk: when they agree, are both wrong?</h2>
<div class="box"><p style="margin:0">__AGN__ pieces where the feeler and Azure read alike, each offered against a one-letter look-alike. The judge found the agreed reading wrong in <b>__AGW__ (__AGP__%)</b>. Looked at by hand, that one is the judge's error (no hamza is printed). With 0 real errors in 190, the rate at which both read a piece wrongly is under about 1.6% (95% bound) — and on the gold pages Azure was wrong in 0 of 427 words. That is the error that disagreement can never flag.</p></div>
<h2>The disagreements themselves</h2>
<p class="mut">The judged word stands on pale yellow; when it has several pieces, the blue bar below spans the disputed one. Azure's and the feeler's readings differ only in that piece.</p>
<div class="chips" id="fv"></div><div class="chips" id="fk"></div><div class="chips" id="fb"></div>
<p class="mut" id="cnt"></p><div class="cards" id="cards"></div><button id="more">show more</button>
<p class="mut" style="margin-top:3em">Spend: $__USD__ (upper bound at list prices) over __REQ__ requests, calibration included. Code and numbers: experiments/17_judge.</p>
</main>
<script>
const D=__DATA__,K=__KINDLIST__;const COL={azure:"var(--az)",feeler:"var(--fe)",neither:"var(--ne)",unsure:"var(--un)",agreewrong:"var(--ne)"};
const NAME={azure:"Azure right",feeler:"Feeler right",neither:"Both wrong",unsure:"Can't tell",agreewrong:"Agreed, but wrong"};
let st={v:"all",k:"all",b:"all"},shown=0;const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function chips(id,key,opts){const el=document.getElementById(id);el.innerHTML=opts.map(([v,l])=>`<button data-v="${v}">${l}</button>`).join("");
el.onclick=e=>{const b=e.target.closest("button");if(!b)return;st[key]=b.dataset.v;draw()};}
chips("fv","v",[["all","every verdict"],...["feeler","azure","neither","unsure","agreewrong"].map(v=>[v,NAME[v]])]);
chips("fk","k",[["all","every kind"],...K.map(k=>[k,k])]);chips("fb","b",[["all","every book"],...[...new Set(D.map(d=>d.d))].sort().map(b=>[b,"book "+b])]);
function list(){return D.filter(d=>(st.v=="all"||d.v==st.v)&&(st.k=="all"||d.k==st.k)&&(st.b=="all"||d.d==st.b))}
function card(d){const ag=d.t=="agree";return `<div class="card"><img loading="lazy" src="${d.im}" alt=""><div class="meta"><span class="tag" style="background:${COL[d.v]}">${NAME[d.v]}</span><span class="tag kd">${esc(d.k)}</span><span class="mut" style="font-size:.78rem">${d.d} p${d.pg}</span>
<div class="rd"><span>${ag?"both read":"Azure"}</span><b dir="rtl">${esc(d.az)}</b></div>${ag?"":`<div class="rd"><span>feeler</span><b dir="rtl">${esc(d.fe)}</b></div>`}
${d.tx&&d.v!="azure"&&d.v!="feeler"?`<div class="rd"><span>judge reads</span><b dir="rtl">${esc(d.tx)}</b></div>`:""}<p class="why">${esc(d.why)}</p>${d.rv?`<p class="why" style="color:var(--fg)"><b>Looked at by hand:</b> ${esc(d.rv)}</p>`:""}</div></div>`}
function draw(){for(const[id,k]of[["fv","v"],["fk","k"],["fb","b"]])document.querySelectorAll("#"+id+" button").forEach(b=>b.classList.toggle("on",b.dataset.v==st[k]));
const L=list();document.getElementById("cnt").textContent=L.length+" pieces";shown=0;document.getElementById("cards").innerHTML="";more()}
function more(){const L=list();document.getElementById("cards").insertAdjacentHTML("beforeend",L.slice(shown,shown+60).map(card).join(""));shown+=60;document.getElementById("more").style.display=shown<L.length?"block":"none"}
document.getElementById("more").onclick=more;draw();
</script></body></html>"""

if __name__ == "__main__":
    main()
