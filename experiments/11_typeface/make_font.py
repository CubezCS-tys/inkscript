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


def choose(plans, iso):
    P.solve([p for p, _, _ in plans]); body = float(np.median([lg["rise"] for _, _, lg in plans])); best = {}
    for p, pc, lg in plans:
        if not P.accepted(p) or abs(lg["rise"] / body - 1) > 0.15: continue
        lb = P.letter_blobs(p, pc["blobs"])
        if len(lb) != p["n"]: continue
        for k, s in enumerate(p["scores"]):
            kk = P.key(p, k)
            if s is not None and (kk not in best or s > best[kk][0]):
                b = lb[k][0]; best[kk] = (s, dict(paths=b["paths"], holes=b["holes"], base=lg["baseline"], rise=lg["rise"], cell=b["cell"]))
    out = {kk: v for kk, (s, v) in best.items()}
    for letter, ex in iso.items():
        ex = [e for e in ex if abs(e["rise"] / body - 1) > -1 and abs(e["rise"] / body - 1) <= 0.15]
        if len(ex) < 2: continue
        wid = [max(p[:, 0].max() for p in e["paths"]) - min(p[:, 0].min() for p in e["paths"]) for e in ex]; e = ex[int(np.argsort(wid)[len(wid) // 2])]
        x0 = min(p[:, 0].min() for p in e["paths"]); x1 = max(p[:, 0].max() for p in e["paths"]); sb = 0.05 * e["rise"] / ALEF_OF_EM
        out[(letter, "iso")] = dict(e, cell=(x0 - sb, x1 + 1 + sb))
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
    plans, iso = collect(azure, scan); forms = choose(plans, iso)
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
