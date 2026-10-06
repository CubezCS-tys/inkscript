"""Apply the stacked-letter rule (stackrule.py) to a finished PDF: each stacked letter gets its own copy of its
line's Type 3 font whose FontBBox is the letter's box, and its own TJ (its own text object) inside the line's
BT ... ET. Chromium 153 takes a highlight's height from the FontBBox (chromium.py). Variants: "cell" (box = today's
d1: the letter's advance x its own ink height), "ink" (d1 and box = its own ink in x and y), "same" (objects split,
FontBBox left as the line's: the cost of the split alone).

    ../../.venv/bin/python post.py IN.pdf OUT.pdf cell|ink|same      -> OUT.pdf, and OUT.json {page: [letter...]}

The same rule as the type3 patch, applied after the fact to experiment 21's builds (the cutter is unchanged), so the
unseen books need not be rebuilt (0772 takes an hour).
"""
import sys, re, json
from pathlib import Path
import fitz
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import glyphs as G, stackrule as SR

TOK = r"<[0-9A-F]{2}>|-?[\d.]+"


def segments(toks, names, widths, fm):
    """Split one line's TJ tokens so that each stacked letter (code in `names`) is drawn in its own font, in its
    own text object. A space glyph (and its pen move) just before the letter goes into the letter's object, and a
    pen move just after it too. pdfium sorts a line's text objects by where their first glyph starts, so a letter
    whose object would start left of the previous object's (a backward pen move in a word) stays in the line's
    font. Returns ([(font name or None, tokens)], dropped codes)."""
    names = dict(names); dropped = []
    while True:
        seg = [[None, []]]; i = 0
        while i < len(toks):
            t = toks[i]
            if t.startswith("<") and int(t[1:3], 16) in names:
                cur = seg[-1][1]; pull = []
                if len(cur) >= 2 and cur[-2] == "<01>" and not cur[-1].startswith("<"): pull = cur[-2:]
                elif cur and cur[-1] == "<01>": pull = cur[-1:]
                if pull: del cur[-len(pull):]
                ts = pull + [t]
                if i + 1 < len(toks) and not toks[i + 1].startswith("<"): ts.append(toks[i + 1]); i += 1
                seg.append([names[int(t[1:3], 16)], ts]); seg.append([None, []])
            else:
                seg[-1][1].append(t)
            i += 1
        pen = 0.0; prev = None; bad = False
        for nm, ts in seg:
            first = None
            for t in ts:
                if t.startswith("<"):
                    if first is None: first = pen
                    pen += widths[int(t[1:3], 16) - 1] * fm
                else:
                    pen -= float(t) / 1000
            if first is None: continue
            if prev is not None and first < prev[0] - 1e-9:
                for nm2, ts2 in (prev[1], (nm, ts)):
                    if nm2 is not None:
                        code = next(int(x[1:3], 16) for x in ts2 if x.startswith("<") and x != "<01>")
                        names.pop(code, None); dropped.append(code)
                bad = True; break
            prev = (first, (nm, ts))
        if not bad:
            return [(nm, ts) for nm, ts in seg if ts], dropped


def words_of(run):
    wid, out = 0, []
    for i, g in enumerate(run):
        if i and (g["box"][0] - run[i - 1]["box"][2] > 0.3 or g["text"] == " " or run[i - 1]["text"] == " "): wid += 1
        out.append(wid)
    return out


def process(doc, variant):
    report = {}
    for pno in range(1, len(doc) + 1):
        pg = doc[pno - 1]; gl = G.glyphs(doc, pno); changed = []
        res = doc.xref_get_key(pg.xref, "Resources"); rx = int(res[1].split()[0])
        fk = doc.xref_get_key(rx, "Font"); fdx, pre = (int(fk[1].split()[0]), "") if fk[0] == "xref" else (rx, "Font/")
        conts = {cx: doc.xref_stream(cx).decode("latin1") for cx in pg.get_contents()}
        by = {}
        for g in gl: by.setdefault(g["font"], []).append(g)
        for fname, run in by.items():
            wids = words_of(run)
            gs = []
            for g, w in zip(run, wids):
                k = (g["box"][2] - g["box"][0]) / (g["d1"][4] - g["d1"][2]) if g["d1"][4] > g["d1"][2] else 0.0576
                gs.append(dict(word=w, text=g["text"], paths=g["paths"], d1=g["d1"], x0=g["origin"][0], y0=g["origin"][1], k=k))
            nb = SR.boxes(gs, variant if variant != "same" else "cell")
            if not nb: continue
            fx = run[0]["font_xref"]; obj = doc.xref_object(fx); names = {}; plan = {}
            widths = [float(x) for x in re.search(r"/Widths\s*\[(.*?)\]", obj, re.S).group(1).split()]
            fm = float(re.search(r"/FontMatrix\s*\[\s*([\d.]+)", obj).group(1))
            for j, (i, bx) in enumerate(sorted(nb.items())):
                names[run[i]["code"]] = f"{fname}s{j}"; plan[run[i]["code"]] = (i, bx)
            for cx, c in conts.items():
                m = re.search(r"BT /%s ([\d.]+) Tf ([-\d. ]+) Tm \[(.*?)\] TJ ET" % re.escape(fname), c, re.S)
                if not m: continue
                size = m.group(1); seg, dropped = segments(re.findall(TOK, m.group(3)), names, widths, fm)
                for code in dropped: names.pop(code, None)
                out = []
                for nm, ts in seg:
                    out.append((f"/{nm} {size} Tf " if nm else "") + f"[{' '.join(ts)}] TJ" + (f" /{fname} {size} Tf" if nm else ""))
                conts[cx] = c[:m.start()] + f"BT /{fname} {size} Tf {m.group(2)} Tm " + " ".join(out) + " ET" + c[m.end():]; break
            for code, nm in names.items():
                i, bx = plan[code]; g = run[i]; d1 = g["d1"]
                body = doc.xref_stream(g["proc_xref"]).decode().split("\n", 1)
                if variant == "ink" and [d1[2], d1[3], d1[4], d1[5]] != bx:
                    doc.update_stream(g["proc_xref"], (f"{d1[0]:.0f} 0 {bx[0]:.0f} {bx[1]:.0f} {bx[2]:.0f} {bx[3]:.0f} d1\n" + body[1]).encode())
                elif variant == "cell":
                    # pdfium starts a new line between two text objects whose boxes do not overlap vertically: a
                    # stacked pair, drawn as two objects, would break the line in two (measured: 1036 lost 20 of
                    # 238 lines). The letter's d1 (pdfium's char box: lines, hit-testing) therefore takes the line's
                    # full height; its highlight's height comes from its own font's FontBBox (Chromium).
                    fb = [float(x) for x in re.search(r"/FontBBox\s*\[([^\]]*)\]", obj).group(1).split()]
                    doc.update_stream(g["proc_xref"], (f"{d1[0]:.0f} 0 {d1[2]:.0f} {fb[1] + 1:.0f} {d1[4]:.0f} {fb[3] - 1:.0f} d1\n" + body[1]).encode())
                nobj = obj if variant == "same" else re.sub(r"/FontBBox\s*\[[^\]]*\]", f"/FontBBox [{bx[0]:.0f} {bx[1]:.0f} {bx[2]:.0f} {bx[3]:.0f}]", obj)
                nx = doc.get_new_xref(); doc.update_object(nx, nobj); doc.xref_set_key(fdx, f"{pre}{nm}", f"{nx} 0 R")
                ox, oy = g["origin"]; kk = gs[i]["k"]
                a = fitz.Point(ox + bx[0] * kk, oy + bx[1] * kk) * pg.transformation_matrix * (300 / 72)
                b = fitz.Point(ox + bx[2] * kk, oy + bx[3] * kk) * pg.transformation_matrix * (300 / 72)
                changed.append(dict(text=g["text"], box_px=[min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)], adv_px=g["box_px"]))
        for cx, c in conts.items(): doc.update_stream(cx, c.encode("latin1"))
        report[pno] = changed
    return report


if __name__ == "__main__":
    doc = fitz.open(sys.argv[1]); rep = process(doc, sys.argv[3]); doc.save(sys.argv[2], garbage=0, deflate=True)
    json.dump(rep, open(Path(sys.argv[2]).with_suffix(".json"), "w"), ensure_ascii=False)
    print("stacked letters given their own box:", sum(len(v) for v in rep.values()))
