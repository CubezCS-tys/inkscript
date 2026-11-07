"""Experiment 81: why our readers have FEWER wrong lines than Azure on 2000+ print but MORE letter errors.

    out/venv/bin/python diag81.py [READER=v1] [ERA=2000+]   -> out/diag81_<reader>.json, out/look/worst_<reader>.png

On the judged lines of the era (both strata, weighted N_h / n_h as est81.py), every line's letter errors of our reader
and of Azure against the judge's truth (`no_punct`, strict, est81's form), broken down by line type:
  Latin (no Latin letter / some / > 30% of letters), digits (none / Arabic-Indic / Latin / both), punctuation-heavy
  (> 12% of characters) or reference-like (a year, ص, مرجع, pp., vol., مجلة with digits), length (letters), shape
  (the crop's width / 48 and the line's tilt: > 3 degrees), and the journal.
Per bucket: weighted letter error % of ours and of Azure, line error %, and the bucket's share of our EXCESS letter
errors (sum of w * (ours - Azure) in the bucket / the total).  Then a contact sheet of the 20 lines where ours loses
most letters to Azure: the judge's crop, the judge's reading, ours, Azure.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from est81 import form, load, truth_of  # noqa: E402

LAT = re.compile("[A-Za-zÀ-ɏ]")
AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
DIG_AR = re.compile("[٠-٩۰-۹]")
DIG_LA = re.compile("[0-9]")
PUN = re.compile(r"[^\w\s]|_")
REF = re.compile(r"(1[89]\d\d|20[0-3]\d|١[٨٩][٠-٩][٠-٩]|٢٠[٠-٣][٠-٩])|\bص\s*[\d٠-٩]|مرجع|\bpp?\.|\bvol\.|مجلة.*[\d٠-٩]|[\d٠-٩]+\s*[-–]\s*[\d٠-٩]+")


HDR = re.compile(r"(ال)?[جمل]+ه? ال[عرب]+يه لل?ت[ر]?بي")


def _fold(s):
    sys.path.insert(0, str(HERE.parent.parent / "src"))
    from inkscript.gold.text import folded
    return folded(s)


def polarity(key: str) -> str:
    """'light on dark' when the judge crop's median grey is dark (inverted print: banners, headers on a band)."""
    from PIL import Image
    a = np.asarray(Image.open(OUT / "judge/crops" / f"{key}.png").convert("L"))
    return "light text on dark" if np.median(a) < 110 else "dark on light"


def buckets(az: str, L: dict) -> dict:
    a, l = len(AR.findall(az)), len(LAT.findall(az))
    letters = a + l
    da, dl = bool(DIG_AR.search(az)), bool(DIG_LA.search(az))
    nonsp = len(az.replace(" ", "")) or 1
    return dict(latin="none" if l == 0 else (">30%" if l / max(1, letters) > 0.3 else "some (<=30%)"),
                digits="none" if not (da or dl) else "both" if da and dl else "Arabic-Indic" if da else "Latin",
                punct_ref="reference-like" if REF.search(az) else "punct-heavy" if len(PUN.findall(az)) / nonsp > 0.12 else "plain",
                length="<=10 letters" if letters <= 10 else "11-40" if letters <= 40 else ">40",
                shape="tilted >3°" if abs(L.get("ang") or 0) > 3 else ("very wide (W/48>40)" if (L.get("W") or 0) / 48 > 40 else "normal"),
                polarity=polarity(L["key"]),
                header="0097 running header (display face on a dark band)" if HDR.search(_fold(az)) else "other",
                journal=L["jcode"])


def main(reader: str = "v1", era: str = "2000+"):
    rows, S, C, ans = load()
    frame = json.loads((OUT / "judge/frame.json").read_text())
    lines = {d["key"]: d for d in map(json.loads, open(OUT / "lines81.jsonl", encoding="utf-8"))}
    cells = defaultdict(list)
    for k, s in S.items():
        if s["era"] != era or k not in ans:
            continue
        T, why = truth_of(s, ans[k])
        if T is None or reader not in rows[k]["readings"]:
            continue
        cells[f"{s['stratum']}|{era}"].append((k, T))
    recs = []
    for h, L in cells.items():
        w = frame[h]["frame"] / len(L)
        for k, T in L:
            r = rows[k]
            do = Levenshtein.distance(form(r["readings"][reader]), T)
            da = Levenshtein.distance(form(r["readings"]["azure"]), T)
            recs.append(dict(key=k, w=w, n=len(T), do=do, da=da, lo=int(do > 0), la=int(da > 0), T=T,
                             b=buckets(r["readings"]["azure"], lines[k]), stratum=h))
    tot_excess = sum(x["w"] * (x["do"] - x["da"]) for x in recs)
    W = sum(x["w"] for x in recs)
    N = sum(x["w"] * x["n"] for x in recs)
    out = dict(reader=reader, era=era, judged=len(recs), letters_ours=round(100 * sum(x["w"] * x["do"] for x in recs) / N, 3),
               letters_azure=round(100 * sum(x["w"] * x["da"] for x in recs) / N, 3),
               lines_ours=round(100 * sum(x["w"] * x["lo"] for x in recs) / W, 2),
               lines_azure=round(100 * sum(x["w"] * x["la"] for x in recs) / W, 2), excess_total_weighted=round(tot_excess, 1),
               buckets={})
    for dim in ("header", "polarity", "latin", "digits", "punct_ref", "length", "shape", "journal"):
        g = defaultdict(list)
        for x in recs:
            g[x["b"][dim]].append(x)
        out["buckets"][dim] = {}
        for v, R in sorted(g.items(), key=lambda kv: -sum(x["w"] * (x["do"] - x["da"]) for x in kv[1])):
            n = sum(x["w"] * x["n"] for x in R)
            w = sum(x["w"] for x in R)
            out["buckets"][dim][v] = dict(judged=len(R), frame_lines_est=round(w), share_of_lines=round(100 * w / W, 1),
                                          letters_ours=round(100 * sum(x["w"] * x["do"] for x in R) / max(1, n), 3),
                                          letters_azure=round(100 * sum(x["w"] * x["da"] for x in R) / max(1, n), 3),
                                          lines_ours=round(100 * sum(x["w"] * x["lo"] for x in R) / w, 1),
                                          lines_azure=round(100 * sum(x["w"] * x["la"] for x in R) / w, 1),
                                          share_of_excess=round(100 * sum(x["w"] * (x["do"] - x["da"]) for x in R) / tot_excess, 1)
                                          if tot_excess else None)
    # the lines that lose most (unweighted rank by the letter difference; ties by the weight)
    worst = sorted(recs, key=lambda x: (-(x["do"] - x["da"]), -x["w"]))[:20]
    out["worst20"] = [dict(key=x["key"], ours_minus_azure=x["do"] - x["da"], ours=rows[x["key"]]["readings"][reader],
                           azure=rows[x["key"]]["readings"]["azure"], judge=ans[x["key"]]["reading"], buckets=x["b"],
                           share_of_excess=round(100 * x["w"] * (x["do"] - x["da"]) / tot_excess, 2) if tot_excess else None)
                      for x in worst]
    out["worst20_share_of_excess"] = round(sum(w["share_of_excess"] or 0 for w in out["worst20"]), 1)
    (OUT / f"diag81_{reader}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    sheet(out["worst20"], reader, era)
    print(json.dumps({k: v for k, v in out.items() if k not in ("worst20",)}, ensure_ascii=False, indent=1)[:6000])


def sheet(worst, reader, era):
    from PIL import Image, ImageDraw, ImageFont
    AR_F = ImageFont.truetype("/home/appuser/.local/share/fonts/Amiri-Regular.ttf", 22, layout_engine=ImageFont.Layout.RAQM)
    LA_F = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", 15)
    Wd, rows = 1500, []
    for x in worst:
        im = Image.open(OUT / "judge/crops" / f"{x['key']}.png").convert("RGB")
        s = min(1.0, (Wd - 40) / im.width)
        im = im.resize((int(im.width * s), int(im.height * s)))
        rows.append((x, im))
    H = sum(im.height + 4 * 34 + 26 for _, im in rows) + 70
    page = Image.new("RGB", (Wd, H), "#fcfcfb")
    d = ImageDraw.Draw(page)
    d.text((20, 18), f"Experiment 81: the 20 held-out {era} lines where our reader ({reader}) loses most letters to Azure "
           "(judged by blind Gemini; punctuation ignored)", font=LA_F, fill="#0b0b0b")
    y = 60
    for x, im in rows:
        d.text((20, y), f"{x['key']}   ours - Azure = {x['ours_minus_azure']:+d} letters   "
               f"latin {x['buckets']['latin']}, digits {x['buckets']['digits']}, {x['buckets']['punct_ref']}, "
               f"{x['buckets']['length']}, {x['buckets']['shape']}", font=LA_F, fill="#52514e")
        y += 24
        page.paste(im, (Wd - 20 - im.width, y))
        y += im.height + 4
        for lab, t, col in (("judge", x["judge"], "#0b0b0b"), ("ours", x["ours"], "#b4471b"), ("Azure", x["azure"], "#1f5fae")):
            d.text((20, y + 6), lab, font=LA_F, fill=col)
            d.text((Wd - 20, y), t, font=AR_F, fill=col, anchor="ra", direction="rtl")
            y += 34
        d.line((20, y + 6, Wd - 20, y + 6), fill="#e4e3df", width=1)
        y += 26 - 12 + 12
    (OUT / "look").mkdir(exist_ok=True)
    page.save(OUT / f"look/worst_{reader}_{era.replace('+', 'plus')}.png")
    print(OUT / f"look/worst_{reader}_{era.replace('+', 'plus')}.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "v1", sys.argv[2] if len(sys.argv) > 2 else "2000+")
