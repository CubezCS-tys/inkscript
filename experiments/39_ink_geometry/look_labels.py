"""A gallery of referee-labelled training pages for the owner's eye test: one page per decade and pages rich in the
rarer labels, each line filled with its label's colour. -> out/train/look/*.jpg, out/train/look.html"""
import json, random, html
from collections import Counter
from pathlib import Path
import cv2
HERE = Path(__file__).parent; T = HERE / "out/train"; LOOK = T / "look"; LOOK.mkdir(exist_ok=True)
COL = {"body": (170, 170, 170), "heading": (30, 30, 220), "footnote": (200, 110, 20), "references": (0, 140, 255), "list": (170, 40, 170),
       "verse": (20, 160, 200), "furniture": (90, 90, 90), "caption": (40, 150, 40), "table": (150, 120, 0), "equation": (120, 60, 160), "other": (60, 60, 60)}
plan = {f"{j['stem']}_p{j['page']:03d}": j for j in json.load(open(T / "plan.json"))}
labs = {}
for f in T.glob("labels/*.json"):
    r = json.loads(f.read_text())
    if r.get("lines"): labs[r["pid"]] = r
rnd = random.Random(7); pick = []
for d in ["pre-1960", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]:
    c = [p for p in labs if plan.get(p, {}).get("decade") == d and p not in pick]
    if c: pick.append(rnd.choice(c))
for lab in ["list", "verse", "references", "footnote", "table", "equation", "caption", "heading"]:
    c = sorted((p for p in labs if p not in pick), key=lambda p: -sum(x["label"] == lab for x in labs[p]["lines"]))[:5]
    if c: pick.append(rnd.choice(c))
cards = []
for pid in pick:
    r = labs[pid]; img = cv2.cvtColor(cv2.imread(str(T / "pages" / f"{pid}.jpg"), cv2.IMREAD_GRAYSCALE), cv2.COLOR_GRAY2BGR); over = img.copy()
    for x in r["lines"]:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"]); cv2.rectangle(over, (x0 - 4, y0), (x1 + 4, y1), COL.get(x["label"], (0, 0, 0)), -1)
    img = cv2.addWeighted(over, 0.38, img, 0.62, 0); s = 1500 / img.shape[0]
    cv2.imwrite(str(LOOK / f"{pid}.jpg"), cv2.resize(img, (int(img.shape[1] * s), 1500), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 82])
    c = Counter(x["label"] for x in r["lines"]); j = plan.get(pid, {})
    cards.append(f"<figure><img loading=lazy src='look/{pid}.jpg'><figcaption><b>{html.escape(pid)}</b> · {j.get('decade','')} · {html.escape(j.get('journal',''))}<br>"
                 + ", ".join(f"{k} {v}" for k, v in c.most_common()) + "</figcaption></figure>")
hexc = {k: "#%02x%02x%02x" % v[::-1] for k, v in COL.items()}
legend = " ".join(f"<span class=chip style='background:{hexc[k]}'>{k}</span>" for k in COL)
(T / "look.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Referee labels</title>
<style>:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:20px 16px}} main{{max-width:1400px;margin:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}} figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}}
img{{width:100%;display:block;background:#fff}} figcaption{{font-size:.82rem;color:var(--mut);padding-top:4px}} .chip{{color:#fff;font-size:.8rem;padding:1px 7px;border-radius:8px;display:inline-block;margin:2px}}
.sticky{{position:sticky;top:0;background:var(--bg);padding:6px 0;z-index:2}}</style></head><body><main>
<h1>The referee's labels, for an eye test</h1><p>{len(pick)} of the {len(labs)} labelled training pages: one from each decade, then pages with the most lists, verse, references, footnotes, tables, equations, captions and headings. Every Azure line is filled with the colour of the label Gemini Flash gave it. Click a page to open it full size.</p>
<p class=sticky>{legend}</p><div class=grid>{''.join(c.replace("<img loading=lazy src='", "<a href='").replace(".jpg'>", ".jpg'><img loading=lazy src='look/" + c.split("look/")[1].split("'")[0] + "'></a>", 1) if False else c for c in cards)}</div></main></body></html>""")
print(len(pick), "pages")
