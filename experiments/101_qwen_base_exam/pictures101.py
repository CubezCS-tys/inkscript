#!/usr/bin/env python3
"""Experiment 101 pictures (experiment 100's pictures100.py, copied 2026-11-24): the same seeded picks (seed 100), now
with the plain Qwen3.5 arms beside OCRia-1.  Changes: tables get one grid per arm; the strip one row per arm; pages are
drawn for 3 of experiment 100's 6 picks (body, two-column, references) with the plain 4B's answer.  For the owner
(out/pictures/).  Two steps, because the aligner needs rapidfuzz (repo venv)
and Arabic drawing needs PIL + raqm (experiment 49's Desk venv, as experiment 99 did):

    nice -n 19 /home/appuser/inkscript/.venv/bin/python pictures101.py data
    nice -n 19 /home/appuser/inkscript/experiments/49_correction_desk/.venv/bin/python pictures101.py draw

  pages_<stem>_pNNN.png   6 exam pages (2 body, 1 two-column, 2 table, 1 references; seed 100 within each kind): the page
                          with every Azure line the model's answer does not contain filled RED (dropped), found lines
                          pale green; beside it the plain 4B's answer as it reads (right to left where Arabic), block by
                          block, kind in the margin, words matching nothing on the page on ORANGE (invented).
  table_<stem>_pNNN.png   4 tables: the printed table, the answer key's grid, Azure + Gemini's grid, OCRia-1's grid;
                          cells that differ from the key: orange = misplaced, red = different text.
  lines_strip.png         12 exam lines: crop, truth, Azure, our reader t91, ocria-nano (exp 99), OCRia-1.
Picks are seeded, not chosen by looking at the results.
"""
from __future__ import annotations

import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
X = "/home/appuser/inkscript/experiments"
P97 = f"{X}/97_extraction_evals"
OUT = os.environ.get("EXP101_PICTURES") or f"{HERE}/out/pictures"
DATA = f"{OUT}/data.json"
# The plain models break the output contract (pipe tables; the 9B whole HTML pages): the pictures read them leniently (the diagnostic scoring,
# EXP101_LENIENT=1, out/scores/<arm>_lenient), so their table READING can be seen; labelled on the pictures.
ARMS = [("OCRia-1", f"{X}/100_ocria1_exam/out/model", f"{HERE}/out/scores/ocria1_rescored"),
        ("Qwen3.5-4B plain", f"{HERE}/out/model/4B", f"{HERE}/out/scores/4B_lenient"),
        ("Qwen3.5-9B plain", f"{HERE}/out/model/9B", f"{HERE}/out/scores/9B_lenient")]
ARMS = [a for a in ARMS if os.path.exists(f"{a[2]}/r1_lines.jsonl")]
PAGE_ARM = "Qwen3.5-4B plain"
PAGE_KINDS = ("body", "two", "refs")         # the first pick of each of these kinds


def use_arm(Q, label):
    """Point the converter at one arm's answers (the view cache is per arm)."""
    mdir = next(a[1] for a in ARMS if a[0] == label)
    Q.V.MODEL_DIR = mdir
    Q.V.PIPE_TABLES = label != "OCRia-1"
    Q._views.clear()


# ================================================================================================ data (repo venv)
def data():
    sys.path.insert(0, HERE)
    import score101 as Q
    V, S = Q.V, Q.S
    from common97 import fold
    gold = S.gold_set("PAGE", "final")[0]["files"]
    tabs = S.gold_set("TAB", "final")[0]["files"]
    lock = {a["stem"]: a for a in Q.LOCK["articles"]}
    by = {"body": [], "two": [], "table": [], "refs": []}
    for name, g in sorted(gold.items()):
        if not S._is_eval_file("PAGE", g) or S.file_left_out(g):
            continue
        kinds = {k for k, p in lock[g["stem"]]["pages"].items() if p == g["page"]}
        if "front" in kinds:
            continue
        if g.get("columns") == 2:
            by["two"].append(name)
        elif "table" in kinds and name in tabs:
            by["table"].append(name)
        elif "refs" in kinds:
            by["refs"].append(name)
        elif "body" in kinds:
            by["body"].append(name)
    rnd = random.Random(100)
    pick = [(k, n) for k, c in (("body", 2), ("two", 1), ("table", 2), ("refs", 1)) for n in rnd.sample(by[k], c)]
    sdir = next(a[2] for a in ARMS if a[0] == PAGE_ARM)
    q2 = {f"{d['stem']}_p{d['page']:03d}.json": d for d in map(json.loads, open(f"{sdir}/q2_pages.jsonl"))}
    use_arm(Q, PAGE_ARM)
    pages = []
    seen_k = set()
    for kind, name in pick:
        if kind not in PAGE_KINDS or kind in seen_k:
            continue
        seen_k.add(kind)
        g = gold[name]
        stem, page = g["stem"], int(g["page"])
        v, ans = Q.view(stem, page)
        pp = Q.S99.V.packet_page(stem, page)
        qq = q2[name]
        nt = set(g.get("azure_lines_that_are_not_text") or [])
        # invented words: the scorer's uncovered runs of 20+ letters that match nothing on the page
        cover = [False] * len(v.NT)
        for ln, L in v.lines.items():
            if L["found"]:
                for k in range(*L["span"]):
                    cover[k] = True
        for k_, b_ in enumerate(v.nblock):          # runs never span two blocks (separators count as covered)
            if b_ is None:
                cover[k_] = True
        az_norm = V.nrm(" ".join(v.texts[l] for l in sorted(v.texts) if l not in nt))
        inv_chars = set()
        run = []
        for k in range(len(v.NT) + 1):
            if k < len(v.NT) and not cover[k]:
                run.append(k)
                continue
            s = "".join(v.NT[i] for i in run).strip()
            if len(s.replace(" ", "")) >= 20 and V.fuzz.partial_ratio(s, az_norm) < 80:
                inv_chars |= {v.idx[i] for i in run}
            run = []
        blocks = []
        for b in v.blocks:
            words, pos = [], b["start"]
            for w in b["text"].split(" "):
                a = v.T.find(w, pos) if w else pos
                a = pos if a < 0 else a
                n_inv = sum(1 for i in range(a, a + len(w)) if i in inv_chars)
                words.append([w, n_inv * 2 > len(w)])
                pos = a + len(w)
            rec = dict(kind=b["kind"], words=words)
            if b["kind"] == "table":
                rec["grid"] = V.fill_grid(b["table"], False)
            blocks.append(rec)
        lines = [dict(line=l["line"], box=[l["x"], l["y"], l["w"], l["h"]],
                      state="not-text" if l["line"] in nt else ("found" if v.lines[l["line"]]["found"] else "dropped"))
                 for l in pp["azure_lines"]]
        pages.append(dict(name=name, kind=kind, image=pp["image"], lines=lines, blocks=blocks,
                          missing=qq["missing_share"], invented=qq["invented_share"], finish=qq["finish_reason"]))
    # ---- tables: key grid, pipeline grid, OCRia-1 grid, with the four-way kinds per cell
    tpick = rnd.sample(sorted(n for n, t in tabs.items() if S._is_eval_file("TAB", t) and not S.file_left_out(t)
                              and any(x.get("cells") for x in t.get("tables") or [])), 4)
    tables = []
    for name in tpick:
        t = tabs[name]
        stem, page = t["stem"], int(t["page"])
        gt = next(x for x in t["tables"] if x.get("cells"))
        pp = Q.S99.V.packet_page(stem, page)
        az = {l["line"]: l for l in pp["azure_lines"]}
        bx = [az[l] for l in (gt.get("lines") or []) if l in az]
        crop = [min(b["x"] for b in bx), min(b["y"] for b in bx), max(b["x"] + b["w"] for b in bx),
                max(b["y"] + b["h"] for b in bx)] if bx else None
        out = dict(name=name, image=pp["image"], crop=crop, key=gt["cells"], key_dir=gt.get("direction") or "rtl")
        out["grids"] = []
        for who in ["Azure + Gemini pipeline"] + [a[0] for a in ARMS]:
            if who.startswith("Azure"):
                pred = S.pipeline_tab(stem, page)
            else:
                use_arm(Q, who)
                pred = V.pred_tab(stem, page, Q.view(stem, page)[0])
            acc, diffs = S.new_acc(), []
            S.compare_tab(dict(t, tables=[gt]), pred, acc, diffs, dict(file=name))
            cells = None
            # the matched pred table: the one compare_tab paired (same line overlap rule): take the best overlap
            pts = pred.get("tables") or []
            best = max(pts, key=lambda p: len(S._lines_of(p) & S._lines_of(gt)), default=None)
            if best and best.get("cells"):
                cells, _ = S.compact_grid(best["cells"])
                if (best.get("direction") or "rtl") != out["key_dir"]:
                    cells = S._mirror(cells)
            kinds = {f"{d['row']},{d['col']}": ("different" if d.get("kind", "").startswith("different") else "misplaced")
                     for d in diffs if d.get("measure") == "P7.cell" and d.get("content_wrong")}
            out["grids"].append(dict(who=who + (" — read leniently (pipe tables, HTML pages)" if "plain" in who else ""), cells=cells, kinds=kinds, n=acc["P7.cells"]["n"], folded=acc["P7.cells"]["folded"]))
        tables.append(out)
    # ---- the strip
    arm_recs = {a[0]: {d["id"]: d for d in map(json.loads, open(f"{a[2]}/r1_lines.jsonl"))} for a in ARMS}
    recs = arm_recs["OCRia-1"]
    nano = {d["id"]: d["liteparse"] for d in map(json.loads, open(f"{X}/99_liteparse_baseline/out/scores/r1_lines_nano.jsonl"))}
    ids = sorted(k for k, v in recs.items() if v.get("truth"))
    byk = {}
    for k in ids:
        byk.setdefault(recs[k]["kind"], []).append(k)
    sp = [k for kd in sorted(byk) for k in rnd.sample(byk[kd], 2)]
    sp += rnd.sample([k for k in ids if k not in sp], 12 - len(sp))
    strip = [dict(id=k, kind=recs[k]["kind"], truth=recs[k]["truth"], azure=recs[k]["azure"], t91=recs[k]["t91"],
                  nano=nano.get(k),
                  arms=[[lab, R[k].get("model", R[k].get("ocria1")) if R[k]["found"] else None] for lab, R in arm_recs.items()])
             for k in sp]
    os.makedirs(OUT, exist_ok=True)
    json.dump(dict(pages=pages, tables=tables, strip=strip), open(DATA, "w"), ensure_ascii=False)
    print("data", len(pages), len(tables), len(strip))


# ================================================================================================ draw (Desk venv)
def draw():
    from PIL import Image, ImageDraw, ImageFont
    D = json.load(open(DATA))
    NASKH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
    DEJ = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    SANS = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
    fonts = {}

    def F(size, kind="ar"):
        k = (size, kind)
        if k not in fonts:
            fonts[k] = ImageFont.truetype({"ar": NASKH, "mix": DEJ, "la": SANS}[kind], size)
        return fonts[k]

    def is_ar(t):
        return sum(1 for ch in t if "؀" <= ch <= "ۿ") > sum(1 for ch in t if ch.isascii() and ch.isalpha())

    def has_lat(t):
        return any(ch.isascii() and ch.isalpha() for ch in t)

    def tlen(d, t, f, rtl):
        try:
            return d.textlength(t, font=f, direction="rtl" if rtl else "ltr")
        except Exception:  # noqa: BLE001
            return d.textlength(t, font=f)

    def text_line(d, x_right, x_left, y, t, f, rtl):
        w = tlen(d, t, f, rtl)
        x = x_right - w if rtl else x_left
        d.text((x, y), t, fill=(0, 0, 0), font=f, direction="rtl" if rtl else "ltr")

    KIND_COL = {"heading": (230, 120, 40), "paragraph": (120, 170, 230), "list": (60, 180, 120), "table": (170, 120, 210),
                "page_header": (150, 150, 150), "page_footer": (150, 150, 150), "page_number": (90, 90, 90),
                "figure": (150, 150, 0), "quote": (160, 200, 90), "equation": (0, 0, 0), "footnote": (230, 110, 170)}

    def answer_panel(blocks, W, H_max=6000):
        im = Image.new("RGB", (W, H_max), (255, 255, 255))
        d = ImageDraw.Draw(im)
        y, L, R = 10, 120, W - 15
        for b in blocks:
            if y > H_max - 80:
                d.text((L, y), "… (answer continues)", fill=(150, 0, 0), font=F(20, "la"))
                break
            d.rectangle([5, y + 4, 25, y + 24], fill=KIND_COL.get(b["kind"], (200, 0, 200)))
            d.text((30, y + 2), {"page_number": "page no.", "page_header": "header", "page_footer": "footer"}.get(b["kind"], b["kind"])[:11], fill=(90, 90, 90), font=F(16, "la"))
            if b["kind"] == "table" and b.get("grid"):
                for row in b["grid"][:40]:
                    t = " | ".join(c for c in row)
                    f = F(18, "mix")
                    rtl = is_ar(t)
                    while t and tlen(d, t, f, rtl) > R - L:
                        t = t[:-4]
                    text_line(d, R, L, y, t, f, rtl)
                    y += 26
                y += 12
                continue
            words = b["words"]
            txt = " ".join(w for w, _ in words)
            rtl = is_ar(txt)
            size = 26 if b["kind"] == "heading" else 22
            f = F(size, "mix")                  # DejaVu: Arabic, Latin, dashes and brackets in one font
            lh = int(size * 1.7)
            # greedy wrap
            line, lines = [], []
            for w in words:
                trial = " ".join(x for x, _ in line + [w])
                if line and tlen(d, trial, f, rtl) > R - L:
                    lines.append(line)
                    line = [w]
                else:
                    line.append(w)
            if line:
                lines.append(line)
            for ln in lines:
                # orange under invented words: draw word by word in reading order
                x = R if rtl else L
                for w, inv in ln:
                    ww = tlen(d, w, f, rtl)
                    sp = tlen(d, " ", f, rtl)
                    x0 = x - ww if rtl else x
                    if inv:
                        d.rectangle([x0 - 2, y + 2, x0 + ww + 2, y + lh - 4], fill=(255, 190, 90))
                    d.text((x0, y), w, fill=(0, 0, 0), font=f, direction="rtl" if rtl else "ltr")
                    x = x0 - sp if rtl else x + ww + sp
                y += lh
            y += 10
        return im.crop((0, 0, W, min(H_max, y + 20)))

    os.makedirs(OUT, exist_ok=True)
    made = []
    for p in D["pages"]:
        img = Image.open(p["image"]).convert("RGB")
        sc = 1000 / img.width
        im = img.resize((1000, int(img.height * sc)))
        ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        for l in p["lines"]:
            x, y, w, h = [v * sc for v in l["box"]]
            c = {"found": (60, 200, 90, 50), "dropped": (230, 0, 0, 120), "not-text": (0, 0, 0, 0)}[l["state"]]
            d.rectangle([x, y, x + w, y + h], fill=c, outline=(200, 0, 0, 255) if l["state"] == "dropped" else None,
                        width=3)
        im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
        ans = answer_panel(p["blocks"], 1100, H_max=max(im.height, 1400) * 2)
        H = max(im.height, ans.height)
        out = Image.new("RGB", (im.width + ans.width + 30, H + 110), (255, 255, 255))
        dd = ImageDraw.Draw(out)
        n_drop = sum(l["state"] == "dropped" for l in p["lines"])
        dd.text((15, 10), f"{p['name'][:-5]}  ({p['kind']} page)   printed text missing from the answer: "
                f"{100 * (p['missing'] or 0):.1f}% ({n_drop} lines, red on the page);  answer text matching nothing on "
                f"the page: {100 * (p['invented'] or 0):.1f}% (orange);  finish: {p['finish']}", fill=(0, 0, 0), font=F(22, "la"))
        dd.text((15, 44), "Left: the page; pale green = line found in the answer, red = not in the answer.   Right: "
                f"{PAGE_ARM}'s answer as it reads, block by block (kind in the margin; read leniently: pipe tables, HTML pages).", fill=(80, 80, 80), font=F(20, "la"))
        out.paste(im, (10, 100))
        out.paste(ans, (im.width + 20, 100))
        f = f"{OUT}/pages_{p['name'][:-5]}.png"
        out.save(f, optimize=True)
        made.append(f)

    def grid_img(cells, kinds, title, W, rtl=True):
        if not cells:
            im = Image.new("RGB", (W, 120), (255, 255, 255))
            ImageDraw.Draw(im).text((10, 10), title + ": (no table)", fill=(150, 0, 0), font=F(22, "la"))
            return im
        nc = max(len(r) for r in cells)
        cw = max(60, (W - 20) // max(1, nc))
        rh = 34
        im = Image.new("RGB", (W, 50 + rh * len(cells) + 10), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.text((10, 8), title, fill=(0, 0, 0), font=F(22, "la"))
        for r, row in enumerate(cells):
            for c in range(nc):
                t = row[c] if c < len(row) else ""
                x0 = (W - 10 - (c + 1) * cw) if rtl else (10 + c * cw)
                y0 = 46 + r * rh
                k = (kinds or {}).get(f"{r},{c}")
                fill = {"misplaced": (255, 190, 90), "different": (240, 110, 110)}.get(k, (255, 255, 255))
                d.rectangle([x0, y0, x0 + cw, y0 + rh], fill=fill, outline=(170, 170, 170))
                f = F(16, "mix")
                ar = is_ar(t)
                while t and tlen(d, t, f, ar) > cw - 6:
                    t = t[:-2] + "…" if len(t) > 2 else ""
                    t = t.rstrip("…")[:-1] + "…" if len(t) > 2 else t
                    if len(t) <= 2:
                        break
                text_line(d, x0 + cw - 3, x0 + 3, y0 + 6, t, f, ar)
        return im

    for t in D["tables"]:
        img = Image.open(t["image"]).convert("RGB")
        if t["crop"]:
            x0, y0, x1, y1 = t["crop"]
            img = img.crop((max(0, int(x0) - 20), max(0, int(y0) - 20), min(img.width, int(x1) + 20), min(img.height, int(y1) + 20)))
        W = 1500
        s = min(1.0, W / img.width)
        img = img.resize((int(img.width * s), int(img.height * s)))
        rtl = t["key_dir"] == "rtl"
        g1 = grid_img(t["key"], {}, "Answer key", W, rtl)
        parts = [img, g1] + [grid_img(g["cells"], g["kinds"], f"{g['who']} ({g['folded']} of {g['n']} cells right, folded)",
                                      W, rtl) for g in t["grids"]]
        H = sum(p.height for p in parts) + 30 * len(parts) + 60
        out = Image.new("RGB", (W + 20, H), (255, 255, 255))
        d = ImageDraw.Draw(out)
        d.text((10, 10), f"{t['name'][:-5]}: printed table, then the grids. Orange = text in the wrong cell (misplaced), "
               "red = different text, white = same as the key (folded).", fill=(0, 0, 0), font=F(20, "la"))
        y = 50
        for p in parts:
            out.paste(p, (10, y))
            y += p.height + 30
        f = f"{OUT}/table_{t['name'][:-5]}.png"
        out.save(f, optimize=True)
        made.append(f)

    W = 1700
    rows = []
    for r in D["strip"]:
        crop = Image.open(f"{P97}/out/reading/crops/{r['id']}.png").convert("RGB")
        s = min(1.0, (W - 20) / crop.width)
        crop = crop.resize((int(crop.width * s), int(crop.height * s)))
        lines = [("truth (settled)", r["truth"]), ("Azure raw", r["azure"]), ("our reader t91", r["t91"]),
                 ("ocria-nano (exp 99)", r["nano"])] + [tuple(a) for a in r["arms"]]
        h = crop.height + 30 + 44 * len(lines) + 20
        im = Image.new("RGB", (W, h), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.text((10, 4), f"{r['id']}  ({r['kind']} page)", fill=(80, 80, 80), font=F(18, "la"))
        im.paste(crop, (W - 10 - crop.width, 28))
        y = crop.height + 34
        for lab, t in lines:
            t2 = (t or "(not found in the answer)") if lab in {a[0] for a in r["arms"]} else (t or "(nothing)")
            same = (t or "") == (r["truth"] or "")
            d.text((10, y + 6), lab, fill=(0, 120, 0) if same else (170, 0, 0), font=F(20, "la"))
            ar = is_ar(t2)
            f = F(24, "mix")                    # DejaVu: no missing glyphs for / • – in any line
            x_left = 300
            text_line(d, W - 10, x_left, y, t2, f, ar)
            y += 44
        d.line([0, h - 2, W, h - 2], fill=(180, 180, 180), width=2)
        rows.append(im)
    for n in range(2):
        part = rows[6 * n: 6 * n + 6]
        out = Image.new("RGB", (W, sum(r.height for r in part) + 60), (255, 255, 255))
        ImageDraw.Draw(out).text((10, 10), "Twelve exam lines (seed 100: two per page kind, then at random). Green label = "
                                 "same as the truth, red = differs.", fill=(0, 0, 0), font=F(20, "la"))
        y = 50
        for r in part:
            out.paste(r, (0, y))
            y += r.height
        f = f"{OUT}/lines_strip_{n + 1}.png"
        out.save(f, optimize=True)
        made.append(f)
    print("\n".join(made))


if __name__ == "__main__":
    {"data": data, "draw": draw}[sys.argv[1]]()
