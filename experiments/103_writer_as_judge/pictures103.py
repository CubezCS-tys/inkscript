"""Experiment 103's pictures for the owner.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python pictures103.py mixed     -> out/pictures/mixed_targets.png

mixed: 20 training lines (experiment 102's M, never the exam) whose target the fixer changes, chosen at random
(seed 103) among those whose Azure string displays as its word boxes show.  Per line: the crop as printed (250 dpi,
experiment 77's geometry); Azure's stored text as an RTL paragraph displays it; the fixed text as it displays (the
same, by construction: the fix changes only the ORDER in which the characters are stored); and what a reader gets
when copying the Latin part, left to right: Azure's order against the fixed order.
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))
OUT = HERE / "out/pictures"
AR_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"      # Arabic and Latin in one face (Noto Naskh has no Latin)
LAT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ISL = re.compile("[^ؠ-يٮ-ۓۺ-ۿ]+")


def latin_parts(s):
    return " | ".join(m.group().strip() for m in ISL.finditer(s) if re.search("[A-Za-z]", m.group()))


def mixed(n=20):
    import cv2
    import numpy as np
    import pypdfium2 as pdfium
    from PIL import Image, ImageDraw, ImageFont
    from common77 import azure_pages, cut_line, nonempty_lines, render_page
    rows = [json.loads(l) for l in open(HERE / "out/diag/boxes103.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["set"] == "M" and r["azure_boxes_ok"] and r["text_fix"] != r["azure"].replace("ـ", "")]
    random.Random(103).shuffle(rows)
    rows = rows[:n]
    W = 1500
    far = ImageFont.truetype(AR_FONT, 26)
    flat = ImageFont.truetype(LAT_FONT, 18)
    fsm = ImageFont.truetype(LAT_FONT, 15)
    tiles = []
    for r in rows:
        doc = pdfium.PdfDocument(r["pdf"])
        img = render_page(doc, r["page"] - 1)
        doc.close()
        pg = azure_pages(Path(r["azure_json"]))[r["page"] - 1]
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        ln = {x["i"]: x for x in nonempty_lines(pg)}[r["i"]]
        crop, _ = cut_line(img, ln["poly"], sx, sy, H=64, test=True)
        c = Image.fromarray(crop).convert("RGB")
        if c.width > W - 20:
            c = c.resize((W - 20, int(c.height * (W - 20) / c.width)))
        h = c.height + 4 * 40 + 20
        t = Image.new("RGB", (W, h), "white")
        d = ImageDraw.Draw(t)
        t.paste(c, (W - 10 - c.width, 6))
        y = c.height + 12
        for label, txt, col in (("Azure, as shown", r["azure"], (150, 40, 40)), ("fixed, as shown", r["text_fix"], (30, 110, 40))):
            d.text((10, y + 6), label, font=fsm, fill=(90, 90, 90))
            tw = d.textlength(txt, font=far, direction="rtl")
            d.text((W - 10 - min(tw, W - 200), y), txt, font=far, fill=col, direction="rtl")
            y += 40
        d.text((10, y + 6), "copied, Latin part:", font=fsm, fill=(90, 90, 90))
        d.text((200, y + 4), "Azure  " + latin_parts(r["azure"]), font=flat, fill=(150, 40, 40))
        y += 32
        d.text((200, y + 4), "fixed  " + latin_parts(r["text_fix"]), font=flat, fill=(30, 110, 40))
        d.text((10, y + 6), r["key"] + "  " + (r.get("era") or ""), font=ImageFont.truetype(LAT_FONT, 11), fill=(150, 150, 150))
        d.line([(0, h - 2), (W, h - 2)], fill=(210, 210, 210), width=2)
        tiles.append(t)
    head = Image.new("RGB", (W, 70), "white")
    dh = ImageDraw.Draw(head)
    dh.text((10, 10), "Mixed Arabic + Latin training lines: the target fix changes the stored ORDER, not what is shown", font=flat, fill=(0, 0, 0))
    dh.text((10, 38), "20 random lines of experiment 102's M (seed 103) whose Azure text displays as its word boxes show. Never exam lines.",
            font=fsm, fill=(80, 80, 80))
    tiles = [head] + tiles
    OUT.mkdir(parents=True, exist_ok=True)
    # two columns would be too narrow for long lines: one tall column, in two files of 10
    for part, ts in ((1, tiles[:11]), (2, [head] + tiles[11:])):
        H = sum(x.height for x in ts)
        sheet = Image.new("RGB", (W, H), "white")
        y = 0
        for x in ts:
            sheet.paste(x, (0, y))
            y += x.height
        sheet.save(OUT / f"mixed_targets_{part}.png")
    print("wrote", OUT)




# ------------------------------------------------------------------------------------------------ B1 / B2 after the key

BLUE, ORANGE, INK, MUTED, SURF = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#fcfcfb"
M_AD = "/work/weights/M/ckpt-3125"


def _jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def _rtl(d, xy_right, y, txt, font, fill):
    from PIL import ImageDraw  # noqa: F401
    tw = d.textlength(txt, font=font, direction="rtl") if txt else 0
    d.text((xy_right - tw, y), txt or "(nothing)", font=font, fill=fill, direction="rtl" if txt else None)


def _diff_words(a, b):
    """indices of words of a that are not matched in b (LCS on words)."""
    import difflib
    wa, wb = a.split(), b.split()
    sm = difflib.SequenceMatcher(a=wa, b=wb, autojunk=False)
    keep = set()
    for blk in sm.get_matching_blocks():
        keep |= set(range(blk.a, blk.a + blk.size))
    return wa, keep


def _rtl_marked(d, right, y, txt, font, base, mark, other):
    """Draw txt right to left word by word; words not in `other` in the mark colour."""
    wa, keep = _diff_words(txt, other)
    x = right
    sp = d.textlength(" ", font=font)
    for i, w in enumerate(wa):
        tw = d.textlength(w, font=font, direction="rtl")
        d.text((x - tw, y), w, font=font, fill=base if i in keep else mark, direction="rtl")
        x -= tw + sp


def b1_real(n=12):
    import random as R
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, str(HERE))
    import score103 as S
    from pool103 import gross
    T = S.truths()
    b1 = json.loads((HERE / "out/scores/b1.json").read_text())
    thr_w, thr_c = b1["writer_threshold"], b1["confidence"]["-lp_mean"]["threshold"]
    rows = _jl(HERE / "out/judge/check103.jsonl")
    for r, w in zip(rows, S.writer_score_87(rows)):
        r["w"] = float(w)
    read = {d["key"]: d for d in _jl(HERE / "out/eval/heldout_M.jsonl") if d["adapter"] == M_AD}
    pos = [r for r in rows if r["kind"] == "real_reader" and r["key"] in T and gross(T[r["key"]], r["text"])]
    R.Random(103).shuffle(pos)
    pick = pos[:n]
    W = 1500
    far = ImageFont.truetype(AR_FONT, 24)
    fs = ImageFont.truetype(LAT_FONT, 15)
    tiles = []
    head = Image.new("RGB", (W, 92), SURF)
    dh = ImageDraw.Draw(head)
    nc_w = sum(r["w"] > thr_w for r in pos)
    nc_c = sum(-read[r["key"]]["lp_mean"] > thr_c for r in pos)
    dh.text((10, 8), f"B1: real gross errors of the reader (M), settled by blind readers - {n} drawn at random (seed 103) of {len(pos)}",
            font=ImageFont.truetype(LAT_FONT, 18), fill=INK)
    dh.text((10, 38), f"Thresholds keep 99% of correct lines unflagged.  Over all {len(pos)}: the writer flags {nc_w} "
            f"({100 * nc_w / len(pos):.1f}%), the reader's own confidence flags {nc_c} ({100 * nc_c / len(pos):.1f}%).",
            font=fs, fill=MUTED)
    dh.text((10, 62), "An empty truth = the blind readers found no readable text on the crop (show-through): the reader invented the line.",
            font=fs, fill=MUTED)
    tiles.append(head)
    for r in pick:
        k = r["key"]
        c = Image.open(HERE / "out/blind/crops" / f"{k}.png").convert("RGB")
        c = c.resize((int(c.width * 64 / c.height), 64))
        if c.width > W - 20:
            c = c.resize((W - 20, int(c.height * (W - 20) / c.width)))
        h = c.height + 3 * 36 + 30
        t = Image.new("RGB", (W, h), SURF)
        d = ImageDraw.Draw(t)
        t.paste(c, (W - 10 - c.width, 6))
        y = c.height + 12
        d.text((10, y + 6), "reader (M)", font=fs, fill=MUTED)
        _rtl(d, W - 10, y, r["text"], far, ORANGE)
        y += 36
        d.text((10, y + 6), "settled truth", font=fs, fill=MUTED)
        if T[k]:
            _rtl(d, W - 10, y, T[k], far, INK)
        else:
            d.text((W - 420, y + 4), "(no readable text: show-through / empty crop)", font=ImageFont.truetype(LAT_FONT, 17), fill=INK)
        y += 36
        from analyse103 import fnp
        fold_g = "yes" if gross(fnp(T[k]), fnp(r["text"])) else "NO (the difference is small once marks and punctuation are ignored)"
        cw = "CAUGHT" if r["w"] > thr_w else "missed"
        cc = "CAUGHT" if -read[k]["lp_mean"] > thr_c else "missed"
        d.text((10, y + 4), f"writer score {r['w']:.2f} vs threshold {thr_w:.2f}: {cw}     "
                            f"confidence -lp_mean {-read[k]['lp_mean']:.3f} vs {thr_c:.3f}: {cc}     gross when folded: {fold_g}",
               font=fs, fill=INK)
        d.text((W - 260, y + 22), k, font=ImageFont.truetype(LAT_FONT, 11), fill=MUTED)
        d.line([(0, h - 2), (W, h - 2)], fill=(215, 215, 215), width=2)
        tiles.append(t)
    _stack(tiles, OUT / "b1_real.png")


def _stack(tiles, path):
    from PIL import Image
    H = sum(x.height for x in tiles)
    sheet = Image.new("RGB", (max(x.width for x in tiles), H), SURF)
    y = 0
    for x in tiles:
        sheet.paste(x, (0, y))
        y += x.height
    OUT.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    print("wrote", path)


def b2_pairs(n=12):
    import random as R
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, str(HERE))
    import score103 as S
    T = S.truths()
    G = {g["key"]: g for g in _jl(HERE / "out/b/contrast_groups.jsonl")}
    C = {r["key"]: r for r in _jl(HERE / "out/judge/contrast_j.jsonl")}
    read = {d["key"]: d for d in _jl(HERE / "out/eval/heldout_M.jsonl") if d["adapter"] == M_AD}
    force = {(d["key"], d["cid"]): d for d in _jl(HERE / "out/eval/force_b.jsonl")}
    lines = []
    for k, g in G.items():
        if k not in T:
            continue
        rd, az = (" ".join(x.split()) for x in g["cands"])
        if (T[k] == rd) == (T[k] == az):
            continue
        wp = S.contrast_pick(C[k], default=0)[0] if k in C else None
        lines.append(dict(key=k, page=g["page"], rd=rd, az=az, truth_is=int(T[k] == az), writer_pick=wp))
    # the confidence rule that was the best free rule (out-of-fold, as scored)
    y = np.array([l["truth_is"] for l in lines])
    lmin = np.array([read[l["key"]]["lp_min"] or 0.0 for l in lines])
    cv = S.logit_cv(lmin[:, None], y, [l["page"] for l in lines]) > 0
    for l, c in zip(lines, cv):
        l["conf_pick"] = int(c)
    R.Random(103).shuffle(lines)
    pick = lines[:n]
    W = 1500
    far = ImageFont.truetype(AR_FONT, 24)
    fs = ImageFont.truetype(LAT_FONT, 15)
    head = Image.new("RGB", (W, 70), SURF)
    dh = ImageDraw.Draw(head)
    dh.text((10, 8), f"B2: lines where the reader (M) and Azure disagree, settled by blind readers - {n} drawn at random of {len(lines)}",
            font=ImageFont.truetype(LAT_FONT, 18), fill=INK)
    dh.text((10, 38), "Words where the two readings differ are in orange.  Right = the rule picked the settled reading.",
            font=fs, fill=MUTED)
    tiles = [head]
    name = {0: "reader", 1: "Azure", None: "reader (fallback)"}
    for l in pick:
        k = l["key"]
        c = Image.open(HERE / "out/blind/crops" / f"{k}.png").convert("RGB")
        c = c.resize((int(c.width * 64 / c.height), 64))
        if c.width > W - 20:
            c = c.resize((W - 20, int(c.height * (W - 20) / c.width)))
        h = c.height + 4 * 36 + 18
        t = Image.new("RGB", (W, h), SURF)
        d = ImageDraw.Draw(t)
        t.paste(c, (W - 10 - c.width, 6))
        y = c.height + 12
        for lab, txt, oth in (("reader (M)", l["rd"], l["az"]), ("Azure", l["az"], l["rd"])):
            d.text((10, y + 6), lab, font=fs, fill=MUTED)
            _rtl_marked(d, W - 10, y, txt, far, INK, ORANGE, oth)
            y += 36
        d.text((10, y + 6), "settled truth", font=fs, fill=MUTED)
        _rtl(d, W - 10, y, T[k], far, (40, 110, 40))
        y += 36
        right = lambda p: "right" if (p if p is not None else 0) == l["truth_is"] else "WRONG"   # noqa: E731
        d.text((10, y + 4), f"writer picks {name[l['writer_pick']]} ({right(l['writer_pick'])});   confidence rule picks "
                            f"{name[l['conf_pick']]} ({right(l['conf_pick'])});   always Azure ({right(1)})     {k}", font=fs, fill=INK)
        d.line([(0, h - 2), (W, h - 2)], fill=(215, 215, 215), width=2)
        tiles.append(t)
    _stack(tiles, OUT / "b2_pairs.png")


def charts():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    sys.path.insert(0, str(HERE))
    import score103 as S
    from pool103 import gross
    T = S.truths()
    b1 = json.loads((HERE / "out/scores/b1.json").read_text())
    ak = json.loads((HERE / "out/scores/b_after_key.json").read_text())
    rows = _jl(HERE / "out/judge/check103.jsonl")
    for r, w in zip(rows, S.writer_score_87(rows)):
        r["w"] = float(w)
    read = {d["key"]: d for d in _jl(HERE / "out/eval/heldout_M.jsonl") if d["adapter"] == M_AD}
    pos = [r for r in rows if r["kind"] == "real_reader" and r["key"] in T and gross(T[r["key"]], r["text"])]
    neg = [r for r in rows if (r["kind"] == "correct" and (r["key"] not in T or T[r["key"]] == " ".join(r["text"].split())))
           or (r["kind"] == "real_reader" and r["key"] in T and not gross(T[r["key"]], r["text"]))]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11, "axes.edgecolor": "#c9c8c2",
                         "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED})
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.6), facecolor=SURF)
    for ax, (name, val, thr, lab) in zip(axs, (
            ("writer score (exp 87 frozen checker)", lambda r: r["w"], b1["writer_threshold"], "writer"),
            ("reader's confidence, -lp_mean", lambda r: -read[r["key"]]["lp_mean"], b1["confidence"]["-lp_mean"]["threshold"], "confidence"))):
        ax.set_facecolor(SURF)
        a = np.array([val(r) for r in neg])
        b = np.array([val(r) for r in pos])
        lo, hi = np.quantile(np.r_[a, b], [0.0, 0.995])
        if lab == "confidence":
            bins = np.logspace(np.log10(max(1e-5, lo)), np.log10(hi), 40)
            ax.set_xscale("log")
        else:
            bins = np.linspace(lo, hi, 40)
        ax.hist(a, bins=bins, color=BLUE, alpha=0.85, label=f"correct lines ({len(a)})", density=True, edgecolor=SURF, linewidth=1)
        ax.hist(b, bins=bins, color=ORANGE, alpha=0.75, label=f"real gross errors ({len(b)})", density=True, edgecolor=SURF, linewidth=1)
        ax.axvline(thr, color=INK, lw=1.5, ls="--")
        caught = (b > thr).mean()
        ax.text(thr, ax.get_ylim()[1] * 0.92, f"  keeps 99% of correct lines\n  catches {100 * caught:.1f}% of errors",
                color=INK, fontsize=10, va="top")
        auc = S.auc(np.r_[b, a], np.r_[np.ones(len(b)), np.zeros(len(a))])
        ax.set_title(f"{name}: AUC {auc:.2f}", color=INK, fontsize=12, loc="left")
        ax.set_yticks([])
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.legend(frameon=False, loc="upper right", fontsize=9, bbox_to_anchor=(1.0, 0.75))
    fig.suptitle("B1: does the score separate the reader's real gross errors from correct lines?  (strict key; bar: AUC >= 0.90 and >= 60% caught)",
                 color=INK, fontsize=12, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(OUT / "b1_separation.png", dpi=110, facecolor=SURF)
    plt.close(fig)
    # B2: rule accuracies, strict and folded (one axis: share of lines where the rule picks the settled reading)
    rules = ["always_reader", "always_azure", "confidence", "confidence_cv", "writer", "writer_conf"]
    lab = ["always the reader", "always Azure", "higher likelihood\n(reader's own)", "reader's confidence\n(threshold, CV)", "writer\n(exp 95 rule)", "writer +\nconfidence (CV)"]
    s, f = ak["b2_strict"], ak["b2_folded"]
    fig, ax = plt.subplots(figsize=(12, 4.8), facecolor=SURF)
    ax.set_facecolor(SURF)
    x = np.arange(len(rules))
    ax.bar(x - 0.2, [100 * s["accuracy"][r] for r in rules], 0.38, color=BLUE, label=f"strict key ({s['n']} lines; decides the bar)", edgecolor=SURF, linewidth=2)
    ax.bar(x + 0.2, [100 * f["accuracy"][r] for r in rules], 0.38, color=ORANGE, label=f"folded, no punct ({f['n']} lines; added after the key)", edgecolor=SURF, linewidth=2)
    for i, r in enumerate(rules):
        ax.text(i - 0.2, 100 * s["accuracy"][r] + 1, f"{100 * s['accuracy'][r]:.0f}", ha="center", color=INK, fontsize=9)
        ax.text(i + 0.2, 100 * f["accuracy"][r] + 1, f"{100 * f['accuracy'][r]:.0f}", ha="center", color=INK, fontsize=9)
    best = 100 * s["accuracy"][s["best_free"]]
    ax.axhline(best + 5, color=INK, ls="--", lw=1)
    ax.text(len(rules) - 0.5, best + 6, "bar: best free rule + 5 points (strict)", ha="right", color=INK, fontsize=9)
    ax.set_xticks(x, lab)
    ax.set_ylim(0, 100)
    ax.set_ylabel("% of lines where the rule picks the settled reading")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_title("B2: reader vs Azure disagreements - which rule picks the right reading?", color=INK, fontsize=12, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "b2_rules.png", dpi=110, facecolor=SURF)
    plt.close(fig)
    print("wrote charts")


if __name__ == "__main__":
    {"mixed": mixed, "b1_real": b1_real, "b2_pairs": b2_pairs, "charts": charts}[sys.argv[1]]()
