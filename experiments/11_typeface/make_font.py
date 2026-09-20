"""A document's typeface as an installable font.

Every letter-form's glyph is one real occurrence from the document — the cut-out letter that looks most like the
document's own picture of that form (experiment 09's atlas), its outline untouched — placed on the baseline, its
advance the stretch of baseline it occupied in print. OpenType `init`/`medi`/`fina` substitutions and the lam-alef
ligature make it type as joined Arabic in any shaping application (LibreOffice, browsers).

    python make_font.py <azure.json> <scan.pdf> <family name> <out.ttf>
"""
import sys, json
from collections import defaultdict
from pathlib import Path
import numpy as np, cv2, fitz
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from inkscript.geometry import penpath as P
from inkscript.geometry.letters import line_geometry
from inkscript.text import MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word

ALEF_OF_EM = 0.62                                                     # an alef stands about this much of the em above the baseline
LIGS = {"لا": "lamalef", "لأ": "lamalefhamzaabove", "لإ": "lamalefhamzabelow", "لآ": "lamalefmadda"}
LIG_SECOND = {"لا": "ا", "لأ": "أ", "لإ": "إ", "لآ": "آ"}; LIG_CODE = {"لا": 0xFEFB, "لأ": 0xFEF7, "لإ": 0xFEF9, "لآ": 0xFEF5}
SUFFIX = dict(iso="", init=".init", med=".medi", fin=".fina")


def gname(letter, form): return (LIGS[letter] if letter in LIGS else f"uni{ord(letter):04X}") + SUFFIX[form]


def collect(azure, scan):
    words, _, dims = load_azure(Path(azure)); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
    doc = fitz.open(scan); plans = []; iso = defaultdict(list)
    for pno in range(doc.page_count):
        pn = pno + 1; pw = [w for w in words if w["page"] == pn]
        if not pw or pn not in dims: continue
        pix = doc[pno].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
        W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
        for L in lines:
            bl = [b for w in L if w["blobs"] for b in w["blobs"]]
            if not bl: continue
            lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
            if not lg or lg["rise"] < 10: continue
            for w in L:
                if not w["blobs"] or MARKS.search(w["text"]): continue
                for pc in split_word(w, lh):
                    uf = P.units_forms(pc["text"].strip())
                    if not uf or uf[1].count("init") > 1: continue
                    if len(uf[0]) == 1:
                        ps = [p for b in pc["blobs"] for p in b["paths"]]; hs = [h for b in pc["blobs"] for h in b["holes"]]
                        iso[P._base(uf[0][0])].append(dict(paths=ps, holes=hs, base=lg["baseline"], rise=lg["rise"]))
                    elif "iso" not in uf[1]:
                        p = P.plan(uf[0], pc["blobs"], lg, uf[1])
                        if p: plans.append((p, pc, lg))
    return plans, iso


HI = 96                                                               # pixels per alef height on the consensus canvas
CW, CH, CBASE = 5 * HI, 3 * HI, 2 * HI                                # canvas width, height, baseline row
TOP = 15


def hires(mask_or_paths, x_ref, base, rise, off=(0, 0)):
    """A letter on the consensus canvas: scaled so the line's rise is HI pixels, the baseline on a fixed row, the
    reference x (the right edge of its cell: where an Arabic letter begins) on a fixed column."""
    sc = HI / rise
    if isinstance(mask_or_paths, np.ndarray):
        M = np.float32([[sc, 0, 4 * HI - sc * (x_ref - off[0])], [0, sc, CBASE - sc * (base - off[1])]])
        return cv2.warpAffine(mask_or_paths.astype(np.float32), M, (CW, CH), flags=cv2.INTER_LINEAR)
    im = np.zeros((CH, CW), np.uint8)
    for path, hole in sorted(zip(mask_or_paths[0], mask_or_paths[1]), key=lambda t: t[1]):
        pts = np.round((np.asarray(path, float) - [x_ref, base]) * sc + [4 * HI, CBASE]).astype(np.int32); cv2.fillPoly(im, [pts], 0 if hole else 1)
    return im.astype(np.float32)


def consensus(examples):
    """The ink most printings agree on: each example is nudged onto the best one, the stack averaged, and what at
    least half of them print is the letter. A break in one printing fills in; a blot in one disappears."""
    ref = examples[0]["img"]; acc = np.zeros_like(ref); n = 0
    for e in examples:
        best = (-1, 0, 0)
        for dx in range(-6, 7, 2):
            for dy in range(-4, 5, 2):
                sh = np.roll(np.roll(e["img"], dx, 1), dy, 0); v = float(np.minimum(sh, ref).sum())
                if v > best[0]: best = (v, dx, dy)
        acc += np.roll(np.roll(e["img"], best[1], 1), best[2], 0); n += 1
    mean = cv2.GaussianBlur(acc / n, (0, 0), 1.2); ink = (mean >= 0.5).astype(np.uint8)
    cs, hier = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    paths, holes = [], []
    for i, c in enumerate(cs):
        c = cv2.approxPolyDP(c, 0.9, True).reshape(-1, 2)
        if len(c) >= 3 and cv2.contourArea(c) >= 12: paths.append(c.astype(float)); holes.append(int(hier[0][i][3] >= 0))
    width = float(np.median([e["width"] for e in examples])) * HI           # cell width in canvas pixels
    return dict(paths=paths, holes=holes, base=CBASE, rise=HI, cell=(4 * HI - width, 4 * HI), n=n)


def choose(plans, iso, smooth=True):
    P.solve([p for p, _, _ in plans]); body = float(np.median([lg["rise"] for _, _, lg in plans])); best = {}; pool = defaultdict(list)
    for p, pc, lg in plans:
        if not P.accepted(p) or abs(lg["rise"] / body - 1) > 0.15: continue
        lb = P.letter_blobs(p, pc["blobs"])
        if len(lb) != p["n"]: continue
        for k, s in enumerate(p["scores"]):
            kk = P.key(p, k)
            if s is None: continue
            b = lb[k][0]
            if smooth and s >= 0.45:
                pool[kk].append(dict(score=s, img=hires((b["paths"], b["holes"]), b["cell"][1], lg["baseline"], lg["rise"]), width=(b["cell"][1] - b["cell"][0]) / lg["rise"]))
                pool[kk] = sorted(pool[kk], key=lambda e: -e["score"])[:TOP]
            if kk not in best or s > best[kk][0]:
                best[kk] = (s, dict(paths=b["paths"], holes=b["holes"], base=lg["baseline"], rise=lg["rise"], cell=b["cell"]))
    out = {kk: v for kk, (s, v) in best.items()}
    for kk, ex in pool.items():
        if len(ex) >= 4: out[kk] = consensus(ex)
    for letter, ex in iso.items():
        ex = [e for e in ex if abs(e["rise"] / body - 1) > -1 and abs(e["rise"] / body - 1) <= 0.15]
        if len(ex) < 2: continue
        wid = [max(p[:, 0].max() for p in e["paths"]) - min(p[:, 0].min() for p in e["paths"]) for e in ex]; e = ex[int(np.argsort(wid)[len(wid) // 2])]
        x0 = min(p[:, 0].min() for p in e["paths"]); x1 = max(p[:, 0].max() for p in e["paths"]); sb = 0.05 * e["rise"] / ALEF_OF_EM
        out[(letter, "iso")] = dict(e, cell=(x0 - sb, x1 + 1 + sb))
        if smooth and len(ex) >= 4:
            med = float(np.median(wid)); near = sorted(ex, key=lambda q: abs((max(p[:, 0].max() for p in q["paths"]) - min(p[:, 0].min() for p in q["paths"])) - med))[:TOP]
            exs = [dict(img=hires((q["paths"], q["holes"]), max(p[:, 0].max() for p in q["paths"]) + 1 + sb, q["base"], q["rise"]),
                        width=(max(p[:, 0].max() for p in q["paths"]) - min(p[:, 0].min() for p in q["paths"]) + 1 + 2 * sb) / q["rise"]) for q in near]
            out[(letter, "iso")] = consensus(exs)
    return out


def draw(g):
    sc = 1000.0 / (g["rise"] / ALEF_OF_EM); pen = TTGlyphPen(None); cx0 = g["cell"][0]
    for path, hole in zip(g["paths"], g["holes"]):
        pts = [((float(x) - cx0) * sc, (g["base"] - float(y)) * sc) for x, y in np.asarray(path)]
        if len(pts) < 3: continue
        area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
        if (area > 0) != bool(hole): pts.reverse()                     # TrueType: outer contours clockwise, holes counter-clockwise
        pen.moveTo(pts[0]); [pen.lineTo(q) for q in pts[1:]]; pen.closePath()
    return pen.glyph(), int(round((g["cell"][1] - cx0) * sc))


def main(azure, scan, family, out):
    plans, iso = collect(azure, scan); forms = choose(plans, iso, smooth="--single" not in sys.argv)
    letters = sorted({l for l, _ in forms})
    for l in letters:                                                  # a form the document never showed borrows its nearest relative
        for want, alt in (("init", "med"), ("med", "init"), ("fin", "iso"), ("iso", "fin")):
            if (l, want) not in forms and (l, alt) in forms and not (want in ("init", "med") and l in "اأإآدذرزوؤةىء"): forms[(l, want)] = forms[(l, alt)]
    if ("ي", "fin") not in forms and ("ى", "fin") in forms: forms[("ي", "fin")] = forms[("ى", "fin")]
    if ("ي", "iso") not in forms and ("ى", "iso") in forms: forms[("ي", "iso")] = forms[("ى", "iso")]
    glyphs = {".notdef": TTGlyphPen(None).glyph(), "space": TTGlyphPen(None).glyph()}; adv = {".notdef": 500, "space": 280}; cmap = {0x20: "space"}
    for (l, f), g in forms.items():
        glyphs[gname(l, f)], adv[gname(l, f)] = draw(g)
    for l in {l for l, _ in forms}:
        base = gname(l, "iso")
        if base not in glyphs:                                         # the code point needs a default glyph
            src = next(gname(l, f) for f in ("fin", "init", "med") if gname(l, f) in glyphs); glyphs[base], adv[base] = glyphs[src], adv[src]
        cmap[LIG_CODE[l] if l in LIGS else ord(l)] = base
    order = [".notdef", "space"] + sorted(n for n in glyphs if n not in (".notdef", "space"))
    fb = FontBuilder(1000, isTTF=True); fb.setupGlyphOrder(order); fb.setupCharacterMap(cmap); fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics({n: (adv[n], int(glyphs[n].xMin) if getattr(glyphs[n], "numberOfContours", 0) else 0) for n in order})
    fb.setupHorizontalHeader(ascent=1150, descent=-650); fb.setupNameTable(dict(familyName=family, styleName="Regular"))
    fb.setupOS2(sTypoAscender=1150, sTypoDescender=-650, usWinAscent=1150, usWinDescent=650, ulUnicodeRange1=(1 << 13) | 1); fb.setupPost()
    rule = lambda f: "\n".join(f"  sub {gname(l, 'iso')} by {gname(l, f)};" for l in sorted({l for l, _ in forms}) if l not in LIGS and gname(l, f) in glyphs and gname(l, f) != gname(l, "iso"))
    lig = []
    for l, name in LIGS.items():
        a = LIG_SECOND[l]
        if name in glyphs and "uni0644.init" in glyphs and f"uni{ord(a):04X}.fina" in glyphs: lig.append(f"  sub uni0644.init uni{ord(a):04X}.fina by {name};")
        if name + ".fina" in glyphs and "uni0644.medi" in glyphs and f"uni{ord(a):04X}.fina" in glyphs: lig.append(f"  sub uni0644.medi uni{ord(a):04X}.fina by {name}.fina;")
    fea = "languagesystem DFLT dflt;\nlanguagesystem arab dflt;\n" + "".join(f"feature {t} {{\n{rule(f)}\n}} {t};\n" for t, f in (("init", "init"), ("medi", "med"), ("fina", "fin")))
    if lig: fea += "feature rlig {\n" + "\n".join(lig) + "\n} rlig;\n"
    addOpenTypeFeaturesFromString(fb.font, fea); Path(out).parent.mkdir(parents=True, exist_ok=True); fb.save(out)
    have = defaultdict(list); [have[l].append(f) for l, f in sorted(forms)]
    print(f"{out}: {len(order) - 2} glyphs for {len(have)} letters; ligatures: {len(lig)}")
    print("letters with all four forms:", "".join(l for l, f in have.items() if len(f) == 4 and l not in LIGS)); print("letters missing from this document:", "".join(c for c in "ءآأؤإئابةتثجحخدذرزسشصضطظعغفقكلمنهوىي" if c not in have))


if __name__ == "__main__":
    main(*sys.argv[1:5])
