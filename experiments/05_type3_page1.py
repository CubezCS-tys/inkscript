"""Page 1 as a native-text PDF: the page's own ink becomes the font.

Each Azure word box -> one Type 3 glyph whose outline is the word's actual ink
(the blob polygons), mapped through ToUnicode to the word's text (Gemini's on
page 1). Lines are written as single text runs, right-to-left words placed in
visual order with real space glyphs between them.

Two outputs:
  <stem>_p1_native.pdf   scan image + the glyphs drawn with 0 opacity (invisible, selectable)
  <stem>_p1_vector.pdf   no image: the glyphs ARE the page (fully vector)
"""
import sys, json, re
from pathlib import Path
import numpy as np, cv2, fitz
sys.path.insert(0, "/home/cubez/Desktop/AI-Search-Mandumah/scripts")
import ocr_frontpage as F
from ocr_hybrid import load_azure, norm

STEM = "0582-004-009-012"
B = Path("/home/cubez/Desktop/OCR_gem_json/output/bakeoff_full")
O = Path("/home/cubez/Desktop/OCR_gem_json/output/frontpage_set")
OUT = Path(__file__).parent
DPI = 300
SIZE_PT = 8.0

# ---- inputs: azure boxes (+lines), gemini text per box, scan pixels
words, _, dims = load_azure(B / "azure" / STEM / f"{STEM}.json")
p1 = [w for w in words if w["page"] == 1]
texts, st = F.page1_text(p1, F.fold_digits((O / f"{STEM}.gemini.p1.md").read_text()), 0.6)
j = json.load(open(B / "azure" / STEM / f"{STEM}.json")); ar = j.get("analyzeResult", j)
az_lines = ar["pages"][0]["lines"]

src = fitz.open(B / "input" / f"{STEM}.pdf")        # image-only scan: same page, no text layer to strip
page = src[0]
pix = page.get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
W_in, H_in = dims[1]
PX = DPI  # azure inches -> pixels at DPI (page rect == azure page: verified by ocr_frontpage)
sx, sy = pix.w / W_in, pix.h / H_in

# ---- blobs
_, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
n, lab, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
blobs = []
for i in range(1, n):
    x, y, w, h, area = stats[i]
    if area < 6: continue
    mask = (lab[y:y+h, x:x+w] == i).astype(np.uint8)
    cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    paths = [(cv2.approxPolyDP(c, 0.6, True).reshape(-1, 2) + [x, y]) for c in cs]
    paths = [p for p in paths if len(p) >= 3]
    if paths: blobs.append(dict(x=x, y=y, w=w, h=h, cx=x + w / 2, cy=y + h / 2, paths=paths, word=None))

# ---- words in pixels, grouped into azure lines
wpx = []
for b, t in zip(p1, texts):
    x0, y0, x1, y1 = b["box"]
    wpx.append(dict(x0=x0 * sx, y0=y0 * sy, x1=x1 * sx, y1=y1 * sy, off=b["off"], text=t, az=b["text"], blobs=[]))
lines = []
for L in az_lines:
    lo = L["spans"][0]["offset"]; hi = lo + L["spans"][0]["length"]
    ws = [w for w in wpx if lo <= w["off"] < hi]
    if ws: lines.append(ws)
seen = {id(w) for L in lines for w in L}
for w in wpx:
    if id(w) not in seen: lines.append([w])

# ---- blobs -> words: centre inside the box, else same line + horizontal overlap (dots, marks)
def overlap(a0, a1, b0, b1): return max(0, min(a1, b1) - max(a0, b0))
for bl in blobs:
    inside = [w for w in wpx if w["x0"] <= bl["cx"] <= w["x1"] and w["y0"] <= bl["cy"] <= w["y1"]]
    if inside:
        bl["word"] = min(inside, key=lambda w: (w["x1"] - w["x0"]) * (w["y1"] - w["y0"])); continue   # the tightest box: `:` beside a word
    best = max(wpx, key=lambda w: overlap(bl["x"], bl["x"] + bl["w"], w["x0"], w["x1"]) * overlap(bl["y"], bl["y"] + bl["h"], w["y0"], w["y1"]))
    if overlap(bl["x"], bl["x"] + bl["w"], best["x0"], best["x1"]) * overlap(bl["y"], bl["y"] + bl["h"], best["y0"], best["y1"]) > 0:
        bl["word"] = best; continue
    for L in lines:
        lh_ = max(w["y1"] for w in L) - min(w["y0"] for w in L)
        ly0, ly1 = min(w["y0"] for w in L) - 0.3 * lh_, max(w["y1"] for w in L) + 0.1 * lh_
        if ly0 <= bl["cy"] <= ly1:
            cands = [w for w in L if overlap(bl["x"], bl["x"] + bl["w"], w["x0"], w["x1"]) > 0]
            if cands:
                bl["word"] = min(cands, key=lambda w: abs((w["x0"] + w["x1"]) / 2 - bl["cx"])); break
# Rules are not letters: a blob far wider than it is tall, and wider than any
# word's box is tall, is page furniture (the underline beneath the section
# head, the dashes round the page number). Left inside a glyph it renders
# fine but makes the glyph declare a box reaching into the next line, which
# pdfium then reads as the two lines touching.
for bl in blobs:
    w = bl["word"]
    if w is not None and bl["w"] > 8 * bl["h"] and not (w["y0"] <= bl["cy"] <= w["y1"]):
        print(f"  rule detached from {w['text']!r}: {bl['w']}x{bl['h']}px"); bl["word"] = None
for bl in blobs:
    if bl["word"] is not None: bl["word"]["blobs"].append(bl)
stray = [bl for bl in blobs if bl["word"] is None]
print(f"{len(blobs)} blobs -> {sum(1 for b in blobs if b['word'])} assigned to {sum(1 for w in wpx if w['blobs'])}/{len(wpx)} words; {len(stray)} stray (rules, page furniture)")

# glyph text: empty boxes (punctuation that rode on a neighbour) get azure's own char, neighbour loses it
for L in lines:
    for k, w in enumerate(L):
        if not w["text"].strip() and w["blobs"]:
            w["text"] = w["az"]
            for nb in (L[k - 1] if k else None, L[k + 1] if k + 1 < len(L) else None):
                if nb and nb["text"].endswith(" " + w["az"]):
                    nb["text"] = nb["text"][: -len(w["az"]) - 1]; break

# A box carrying several tokens (`معجمية :`, or Gemini words packed into one
# Azure box) becomes one glyph per token when its ink falls into as many
# horizontal groups: tokens are handed out right to left. One glyph holding
# ": ةيمجعم" starts with a neutral, and MuPDF then fails to treat the line as
# right-to-left; a colon in its own glyph is what a native PDF has.
def split_tokens(w, lh):
    toks = w["text"].split()
    if len(toks) < 2 or not w["blobs"]: return [w]
    bs = sorted(w["blobs"], key=lambda b: b["x"])
    groups, cur = [], [bs[0]]
    for b in bs[1:]:
        if b["x"] - max(c["x"] + c["w"] for c in cur) > 0.12 * lh: groups.append(cur); cur = [b]
        else: cur.append(b)
    groups.append(cur)
    if len(groups) != len(toks): return [w]
    out = []
    for g, t in zip(groups, reversed(toks)):          # leftmost ink group = last token
        out.append(dict(w, text=t, az=t, blobs=g, x0=min(b["x"] for b in g), x1=max(b["x"] + b["w"] for b in g)))
    return out
for L in lines:
    lh = max(w["y1"] for w in L) - min(w["y0"] for w in L)
    L[:] = [g for w in L for g in split_tokens(w, lh)]

# ---- PDF writing helpers
def to_pdf(x, y, M):          # pixel -> PDF user space
    return fitz.Point(x * 72 / DPI, y * 72 / DPI) * M
def hex16(s): return s.encode("utf-16-be").hex().upper()

def visual(s):
    """ToUnicode text in VISUAL order. Extractors take a glyph's characters as
    laid out on the page and run bidi over them, which reverses an Arabic run;
    a word stored logically therefore comes out backwards (`تاسارد`). Storing
    Arabic words reversed makes the extractor's reversal restore them. Digits
    and Latin are left as they are: bidi keeps those left-to-right."""
    toks = s.split()
    if not any(F.RTL.search(t) for t in toks): return s
    def vis(t):
        if not F.RTL.search(t): return t
        # digit runs stay in reading order inside the reversed token: pdfium
        # reverses letter runs back but leaves digits as stored, and a native
        # PDF stores `379هـ)` as `)ـه379`. Reversing the digits too gave 973.
        runs = re.findall(r"[0-9٠-٩]+|[^0-9٠-٩]+", t)
        return "".join(r if re.match(r"[0-9٠-٩]", r) else r[::-1] for r in reversed(runs))
    return " ".join(vis(t) for t in reversed(toks))

def add_fonts_and_text(doc, pg, M, invisible):
    """One Type 3 font per line; returns content stream text."""
    res_key = doc.xref_get_key(pg.xref, "Resources")
    if res_key[0] == "xref": res_xref = int(res_key[1].split()[0])
    else:
        res_xref = doc.get_new_xref(); doc.update_object(res_xref, "<< >>"); doc.xref_set_key(pg.xref, "Resources", f"{res_xref} 0 R")
    if doc.xref_get_key(res_xref, "Font")[0] == "null": doc.xref_set_key(res_xref, "Font", "<< >>")
    if invisible:
        gs = doc.get_new_xref(); doc.update_object(gs, "<< /Type /ExtGState /ca 0 /CA 0 >>")
        if doc.xref_get_key(res_xref, "ExtGState")[0] == "null": doc.xref_set_key(res_xref, "ExtGState", "<< >>")
        doc.xref_set_key(res_xref, "ExtGState/GSinv", f"{gs} 0 R")
    out = ["q", "/GSinv gs" if invisible else "0 g"]
    glyph_boxes = []
    # Where each line's ink ends, top to bottom. A line's font box is clipped
    # at the bottom of the line above: descenders and vowel marks of adjacent
    # lines overlap by a few pixels, and pdfium (Chrome) joins text objects
    # whose boxes overlap into one line, which then copies out scrambled.
    bottoms = sorted(max(w["y1"] for w in L if w["blobs"]) for L in lines if any(w["blobs"] for w in L))
    for li, L in enumerate(lines):
        ws = [w for w in L if w["blobs"]]
        if not ws: continue
        ws.sort(key=lambda w: w["x0"])                       # visual order, left to right
        ly1 = max(w["y1"] for w in ws); ly0 = min(min(b["y"] for b in w["blobs"]) for w in ws)
        above = [b for b in bottoms if b < ly1 - 2]
        if above: ly0 = max(ly0, above[-1] + 1)               # never reach into the line above
        # pdfium takes a Type 3 glyph's box from its d1 declaration, not the
        # font box, so the declared box is clipped the same way: top at the
        # line above, bottom at the next line's ink. The outline itself is
        # untouched; only what the glyph *declares* as its extent shrinks.
        tops = sorted(min(min(b["y"] for b in w["blobs"]) for w in L2 if w["blobs"]) for L2 in lines if any(w["blobs"] for w in L2))
        below = [t for t in tops if t > ly1 - 2]
        lh = max(1.0, ly1 - ly0)
        # One nominal text size for every line. pdfium decides "same line" by
        # vertical distance relative to the font size, so a 40pt title
        # swallowed the author line beneath it and sorted the two by x —
        # author before title. Glyph outlines are simply scaled so that
        # SIZE_PT * units reproduces the ink at true size; Type 3 glyph space
        # is unbounded, so a title glyph is just a large glyph.
        size_pt = SIZE_PT; u = 1000.0 / (size_pt * DPI / 72)  # glyph units per pixel
        lim_top = (ly1 - ly0) * u
        lim_bot = -((below[0] - ly1) - 1) * u if below else -1e9
        procs, widths, names, tou, bbox = {}, [], [], [], [0, 0, 0, 0]
        # code 1 = space glyph (empty), width = median gap or 0.25 em
        gaps = [ws[k + 1]["x0"] - ws[k]["x1"] for k in range(len(ws) - 1)]
        # narrow, never wider than the smallest real gap: a space glyph that
        # overlaps the next word gets dropped by extractors as "not a gap"
        # A real space glyph between words, never wider than the smallest gap
        # on the line so it never overlaps a word (poppler then drops it). A
        # space character carried inside each word's text instead confused
        # both MuPDF and poppler. Measured: this gives 198/209 words intact
        # in MuPDF and 190/209 in poppler; the poppler misses are the title's
        # touching words, which no layer can separate.
        sp_w = max(1.0, min([g for g in gaps if g > 0] + [0.2 * lh])) * u
        procs["sp"] = f"{sp_w:.1f} 0 0 0 0 0 d1\n"; widths.append(sp_w); names.append("sp"); tou.append((1, " "))
        for k, w in enumerate(ws):
            code = k + 2
            gx0 = min(min(p[:, 0].min() for p in b["paths"]) for b in w["blobs"])
            gx1 = max(max(p[:, 0].max() for p in b["paths"]) for b in w["blobs"])
            adv = (gx1 - gx0) * u
            cmds = []
            for b in w["blobs"]:
                for p in b["paths"]:
                    pts = [((px - gx0) * u, (ly1 - py) * u) for px, py in p]
                    cmds.append(f"{pts[0][0]:.1f} {pts[0][1]:.1f} m " + " ".join(f"{x:.1f} {y:.1f} l" for x, y in pts[1:]) + " h")
            gy0 = min(min(p[:, 1].min() for p in b["paths"]) for b in w["blobs"]); gy1 = max(max(p[:, 1].max() for p in b["paths"]) for b in w["blobs"])
            by0, by1 = (ly1 - gy1) * u, (ly1 - gy0) * u
            dy0, dy1 = max(by0, min(lim_bot, 0.0)), min(by1, lim_top)
            procs[f"g{code}"] = f"{adv:.1f} 0 0 {dy0:.1f} {adv:.1f} {dy1:.1f} d1\n" + "\n".join(cmds) + "\nf*\n"
            widths.append(adv); names.append(f"g{code}"); tou.append((code, visual(w["text"].strip() or w["az"])))
            bbox = [0, min(bbox[1], dy0), max(bbox[2], adv), max(bbox[3], dy1)]
            w["_gx0"], w["_adv"] = gx0, adv
            glyph_boxes.append((w, gx0, gy0, gx1, gy1))
        # font objects
        cp = {}
        for nm, body in procs.items():
            x = doc.get_new_xref(); doc.update_object(x, "<< >>"); doc.update_stream(x, body.encode()); cp[nm] = x
        tu = doc.get_new_xref(); doc.update_object(tu, "<< >>")
        doc.update_stream(tu, ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /T3-UCS def /CMapType 2 def\n"
            "1 begincodespacerange <00> <FF> endcodespacerange\n" + f"{len(tou)} beginbfchar\n" +
            "".join(f"<{c:02X}> <{hex16(s)}>\n" for c, s in tou) + "endbfchar\nendcmap CMapName currentdict /CMap defineresource pop end end").encode())
        fx = doc.get_new_xref()
        doc.update_object(fx, "<< /Type /Font /Subtype /Type3 /FontBBox [%d %d %d %d] /FontMatrix [0.001 0 0 0.001 0 0] "
            "/CharProcs << %s >> /Encoding << /Type /Encoding /Differences [1 %s] >> /FirstChar 1 /LastChar %d /Widths [%s] "
            "/Resources << >> /ToUnicode %d 0 R >>" % (bbox[0], bbox[1] - 1, bbox[2] + 1, bbox[3] + 1,
            " ".join(f"/{nm} {x} 0 R" for nm, x in cp.items()), " ".join("/" + nm for nm in names), len(names),
            " ".join(f"{wd:.1f}" for wd in widths), tu))
        doc.xref_set_key(res_xref, f"Font/T3L{li}", f"{fx} 0 R")
        # text run: TJ with exact positioning; space glyph between words
        origin = to_pdf(ws[0]["_gx0"], ly1, M)
        parts = []; pen = ws[0]["_gx0"]
        for k, w in enumerate(ws):
            code = k + 2
            if k:
                gap = (w["_gx0"] - pen) * u
                parts.append(f"<01> {-(gap - sp_w):.1f}")   # space glyph, then the pen to this word's exact x
            parts.append(f"<{code:02X}>")
            pen = w["_gx0"] + w["_adv"] / u
        out.append(f"BT /T3L{li} {size_pt:.3f} Tf 1 0 0 1 {origin.x:.2f} {origin.y:.2f} Tm [{' '.join(parts)}] TJ ET")
    out.append("Q")
    return "\n".join(out) + "\n", glyph_boxes

def stray_paths(M):
    cmds = ["q 0 g"]
    for bl in stray:
        for p in bl["paths"]:
            pts = [to_pdf(x, y, M) for x, y in p]
            cmds.append(f"{pts[0].x:.2f} {pts[0].y:.2f} m " + " ".join(f"{q.x:.2f} {q.y:.2f} l" for q in pts[1:]) + " h")
    cmds.append("f* Q"); return "\n".join(cmds) + "\n"

# ---- A: scan + invisible glyphs
M = ~page.transformation_matrix
content, gboxes = add_fonts_and_text(src, page, M, invisible=True)
cx = src.get_new_xref(); src.update_object(cx, "<< >>"); src.update_stream(cx, content.encode())
old = page.get_contents()
src.xref_set_key(page.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in old + [cx]) + "]")
outA = OUT / f"{STEM}_p1_native.pdf"; src.save(outA, garbage=3, deflate=True)

# ---- B: pure vector page
vec = fitz.open(); vp = vec.new_page(width=page.rect.width, height=page.rect.height)
Mv = ~vp.transformation_matrix
content, _ = add_fonts_and_text(vec, vp, Mv, invisible=False)
cx = vec.get_new_xref(); vec.update_object(cx, "<< >>"); vec.update_stream(cx, (stray_paths(Mv) + content).encode())
vec.xref_set_key(vp.xref, "Contents", f"{cx} 0 R")
outB = OUT / f"{STEM}_p1_vector.pdf"; vec.save(outB, garbage=3, deflate=True)
print(f"wrote {outA.name} ({outA.stat().st_size/1024:.0f} KB) and {outB.name} ({outB.stat().st_size/1024:.0f} KB)")
json.dump([dict(text=w["text"], box=[float(gx0), float(gy0), float(gx1), float(gy1)]) for w, gx0, gy0, gx1, gy1 in gboxes],
          open(OUT / "p1_glyphs.json", "w"), ensure_ascii=False)
