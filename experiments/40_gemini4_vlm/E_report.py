"""Experiment 40, approach E: what pass 2 (Azure-arbitrated blind look) did, and a picture gallery of it.

    .venv/bin/python E_report.py [DIR ...]        (default out/E_best)

Writes <DIR>/arb_summary.json: questions and changes by kind; on the truth pages each applied change judged
against the truth word bag (right: the new word is in the truth and the old one is not; wrong: the reverse;
neutral otherwise). Writes <DIR>/arb_gallery.html (+ .jpg screenshot via out/venv's Playwright): each changed
word with its crop, Argon's reading, Azure's, the blind zoomed reading and the verdict.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from D_subset import U, e36, GOLD, gold_load, jload, words  # noqa: E402


def truth_bag(pid):
    u = U.get(pid)
    if not u or not u.get("truth"):
        return None
    if u["truth"] == "gold":
        g = gold_load(GOLD / f"{pid}.json")
        return words([ln["text"] for ln in e36.gold_lines(g) if ln.get("kind", "text") != "equation"])
    return words([ln["text"] for ln in jload(u["truth_file"])["lines"]], dig=True)


def sheet_rows(f: Path):
    """Cut a sheet back into its numbered crops (rows end in a grey 1-px line)."""
    import cv2
    import numpy as np
    img = cv2.imread(str(f))
    grey = np.all(np.abs(img.astype(int) - 180) < 30, axis=2).mean(axis=1) > 0.9
    cuts = [i for i in range(len(grey)) if grey[i] and (i == 0 or not grey[i - 1])]
    rows, a = [], 0
    for c in cuts:
        rows.append(img[a:c + 1, 90:])
        a = c + 1
    return rows


def b64(img):
    import cv2
    return base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()


def main(d: Path):
    arb = d / "arb"
    summ = dict(pages=0, pages_with_questions=0, questions=Counter(), applied=Counter(), chosen=Counter(), usd=0.0,
                truth=Counter(), truth_rows=[])
    gallery = []
    for f in sorted(arb.glob("*.json")):
        r = json.loads(f.read_text())
        pid = f.stem
        summ["pages"] += 1
        summ["usd"] += r.get("usd", 0) or 0
        if r["n_disputes"]:
            summ["pages_with_questions"] += 1
        tb = truth_bag(pid)
        rows = None
        for x in r["decisions"]:
            summ["questions"][x["kind"]] += 1
            summ["chosen"][x["chosen"]] += 1
            if x["applied"]:
                summ["applied"][x["kind"]] += 1
            verdict = None
            if tb is not None and x["applied"]:
                new = x["azure"] if x["chosen"] == "azure" else x["printed"]
                nw, ow = words([new]), words([x["gemini"]])
                ok_new = all(tb[w] for w in nw)
                ok_old = all(tb[w] for w in ow)
                verdict = "right" if ok_new and not ok_old else "wrong" if ok_old and not ok_new else "neutral"
                summ["truth"][verdict] += 1
                summ["truth_rows"].append(dict(pid=pid, gemini=x["gemini"], new=new, verdict=verdict))
            if x["applied"] or (tb is not None and x["kind"] != "marks"):
                if rows is None:
                    rows = []
                    for s in sorted((arb / "sheets").glob(f"{pid}_s*.jpg"), key=lambda p: int(p.stem.rsplit("_s", 1)[1])):
                        rows += sheet_rows(s)
                crop = rows[x["n"] - 1] if x["n"] - 1 < len(rows) else None
                gallery.append(dict(pid=pid, x=x, crop=crop, verdict=verdict))
    summ["questions_total"] = sum(summ["questions"].values())
    summ["applied_total"] = sum(summ["applied"].values())
    out = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in summ.items()}
    (d / "arb_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "truth_rows"}, ensure_ascii=False))
    # gallery: applied changes first (truth-judged ones on top), then kept readings on truth pages
    gallery.sort(key=lambda g: (not g["x"]["applied"], g["verdict"] is None, g["pid"]))
    col = {"right": "#0a7d2c", "wrong": "#c0262d", "neutral": "#777", None: "#555"}
    rows = []
    for g in gallery[:80]:
        x = g["x"]
        img = f'<img src="data:image/jpeg;base64,{b64(g["crop"])}">' if g["crop"] is not None else ""
        final = x["azure"] if x["chosen"] == "azure" else x["printed"] if x["chosen"] == "printed" else x["gemini"]
        v = g["verdict"] or ("changed" if x["applied"] else "kept Argon")
        rows.append(f"<tr><td class=pid>{g['pid']}<br>{x['kind']}</td><td>{img}</td><td>{x['gemini']}</td>"
                    f"<td>{x['azure']}</td><td>{x['printed'] or '—'}</td><td><b>{final}</b></td>"
                    f"<td style='color:{col[g['verdict']]}'>{v}</td></tr>")
    html = ("<!doctype html><html><head><meta charset=utf-8><link href='https://fonts.googleapis.com/css2?family="
            "Scheherazade+New&display=block' rel=stylesheet><style>body{font:14px sans-serif;margin:16px}"
            "td{border-bottom:1px solid #ddd;padding:4px 8px;font-family:'Scheherazade New',serif;font-size:24px;"
            "direction:rtl}td.pid{font:11px monospace;direction:ltr;color:#666}img{max-height:70px}"
            "th{font:12px sans-serif;text-align:right}</style></head><body>"
            "<h3>Pass 2: words where Argon and Azure disagreed, settled by a blind zoomed reading (2 of 3)</h3>"
            "<table><tr><th>page</th><th>crop (red line = the word)</th><th>Argon (page)</th><th>Azure</th>"
            "<th>blind zoom</th><th>kept in edition</th><th>vs truth</th></tr>" + "".join(rows) + "</table></body></html>")
    hf = d / "arb_gallery.html"
    hf.write_text(html, encoding="utf-8")
    shot = HERE / "out/venv/bin/python"
    if shot.exists():
        code = ("import sys;from playwright.sync_api import sync_playwright as P\n"
                "with P() as p:\n b=p.chromium.launch();pg=b.new_page(viewport={'width':1300,'height':900});"
                "pg.goto('file://'+sys.argv[1]);pg.wait_for_timeout(1500);"
                "pg.screenshot(path=sys.argv[2],full_page=True,type='jpeg',quality=80);b.close()")
        subprocess.run([str(shot), "-c", code, str(hf), str(d / "arb_gallery.jpg")], check=False)


if __name__ == "__main__":
    for a in sys.argv[1:] or ["out/E_best"]:
        main((HERE / a) if not Path(a).is_absolute() else Path(a))
