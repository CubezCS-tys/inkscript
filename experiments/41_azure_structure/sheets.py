"""Experiment 41: crop sheets of fixes and misprint flags, for judging by eye (no calls).

    /home/yassine/inkscript/.venv/bin/python sheets.py --run argon [--fixes 40] [--seed 41]

Every flag (span.sic) of the run and a random sample of its applied fixes (seeded), each as: the printed line cropped
from the 300 dpi scan, Azure's text, the change. Written to out/sheets/<run>.html (+ crops in out/sheets/crops/) and
screenshotted to out/sheets/<run>_NN.png in pieces so they can be looked at. Verdicts go by hand into
out/judged.json {run: {item_id: "right"|"wrong"|"unsure"}} (item ids are printed on the sheet).
"""
from __future__ import annotations

import argparse
import base64
import html as H
import json
import random
import re
import subprocess
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import OUT, art_of, page_image, page_lines, sample  # noqa: E402
from render41 import VENV_PY  # noqa: E402

SD = OUT / "sheets"


def crop(a, page, lid, pad=0.6):
    base = re.sub(r"[a-p]$", "", lid)
    ls, W, Hh = page_lines(a, page)
    L = next((l for l in ls if l["id"] == base), None)
    if L is None:
        return None
    img = cv2.imread(str(page_image(a, page)), cv2.IMREAD_COLOR)
    x0, y0, x1, y1 = L["px"]
    h = y1 - y0
    X0, Y0 = max(0, int(x0 - 0.5 * h)), max(0, int(y0 - pad * h))
    X1, Y1 = min(img.shape[1], int(x1 + 0.5 * h)), min(img.shape[0], int(y1 + pad * h))
    c = img[Y0:Y1, X0:X1]
    if c.shape[1] > 1500:
        s = 1500 / c.shape[1]
        c = cv2.resize(c, (1500, int(c.shape[0] * s)), interpolation=cv2.INTER_AREA)
    return c, L["text"]


def items(run, nfix, seed, nsic=40):
    out = []
    fixes = []
    for a in sample():
        f = OUT / run / "book" / f"{a['stem']}.json"
        if not f.exists():
            continue
        b = json.loads(f.read_text(encoding="utf-8"))
        for s in b["sic"]:
            out.append(dict(kind="sic", stem=a["stem"], page=s["page"], line=s["at"], frm=s["text"], to=s["corr"],
                            why=s.get("why")))
        for x in b["fixes_applied"]:
            fixes.append(dict(kind="fix", stem=a["stem"], page=x["page"], line=x["at"], frm=x["from"], to=x.get("to"),
                              why=x.get("why")))
    rnd = random.Random(seed)
    if len(out) > nsic:
        out = sorted(rnd.sample(out, nsic), key=lambda x: (x["stem"], x["page"]))
    pick = rnd.sample(fixes, min(nfix, len(fixes)))
    out += sorted(pick, key=lambda x: (x["stem"], x["page"]))
    for k, x in enumerate(out, 1):
        x["id"] = f"{run}-{x['kind']}-{k:03d}"
    return out, len(fixes)


def mark(text, frm, colour):
    i = text.find(frm)
    if i < 0:
        return H.escape(text)
    return H.escape(text[:i]) + f'<b style="background:{colour}">{H.escape(frm)}</b>' + H.escape(text[i + len(frm):])


def build(run, nfix, seed, shoot=True):
    its, nall = items(run, nfix, seed)
    SD.mkdir(parents=True, exist_ok=True)
    rows = []
    for x in its:
        a = art_of(x["stem"])
        c = crop(a, x["page"], x["line"])
        if c is None:
            continue
        img, az = c
        b64 = base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()).decode()
        x["azure_line"] = az
        x["crop"] = b64
        rows.append(f"""<tr><td class=id>{x['id']}<br>{x['stem']} p{x['page']} {x['line']}</td>
<td><img src="data:image/jpeg;base64,{b64}"><div class=az>Azure: {mark(az, x['frm'], '#ffcdd2')}</div>
<div class=ch>{'flag' if x['kind'] == 'sic' else 'fix'}: <span class=f>{H.escape(x['frm'])}</span> &rarr;
<span class=t>{H.escape(x['to'] or '∅')}</span> <i>({H.escape(x['why'] or '')})</i></div></td></tr>""")
    page = f"""<!doctype html><html dir=rtl><head><meta charset=utf-8><style>
body{{font-family:'Scheherazade New','Noto Naskh Arabic',serif;font-size:22px;margin:10px;width:1600px;background:#fff}}
table{{border-collapse:collapse}} td{{border-bottom:1px solid #ccc;padding:6px;vertical-align:top}}
td.id{{font:13px monospace;direction:ltr;width:150px;color:#333}} img{{max-width:1400px;display:block}}
.az{{color:#444}} .f{{background:#ffcdd2}} .t{{background:#c8e6c9}} i{{font-size:16px;color:#666}}
</style><link href="https://fonts.googleapis.com/css2?family=Scheherazade+New&display=block" rel="stylesheet">
</head><body><h3 dir=ltr>{run}: {sum(1 for x in its if x['kind'] == 'sic')} flags, {sum(1 for x in its if x['kind'] == 'fix')}
of {nall} fixes (seed {seed})</h3><table>{''.join(rows)}</table></body></html>"""
    hf = SD / f"{run}.html"
    hf.write_text(page, encoding="utf-8")
    (SD / f"{run}_items.json").write_text(json.dumps([{k: v for k, v in x.items() if k != "crop"} for x in its],
                                                    ensure_ascii=False, indent=1), encoding="utf-8")
    if shoot:
        js = r"""
import sys
from playwright.sync_api import sync_playwright
src, dst = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1620, "height": 1000})
    pg.goto("file://" + src, wait_until="networkidle", timeout=60000)
    h = pg.evaluate("document.body.scrollHeight"); k = 0; y = 0
    while y < h:
        pg.screenshot(path=f"{dst}_{k:02d}.png", clip={"x": 0, "y": y, "width": 1620, "height": min(2400, h - y)},
                      full_page=True)
        y += 2400; k += 1
    b.close()
"""
        for old in SD.glob(f"{run}_[0-9][0-9].png"):
            old.unlink()
        subprocess.run([str(VENV_PY), "-c", js, str(hf), str(SD / run)])
    print(f"{run}: {len(rows)} items -> {hf}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="argon")
    ap.add_argument("--fixes", type=int, default=40)
    ap.add_argument("--seed", type=int, default=41)
    a = ap.parse_args()
    build(a.run, a.fixes, a.seed)


if __name__ == "__main__":
    main()
