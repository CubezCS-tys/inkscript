"""The restored edition: a page reset in the book's own recovered typeface.

    python make_page.py <built_dir> <stem> --page 2 --font <ttf> [--out FILE]

The third output named in docs/ideas.md and blessed by D14. The faithful PDF draws every occurrence's own ink
and therefore can never be small or reusable — that is its point. This one goes the other way: one embedded
font (experiment 11, voted from up to 15 printings), every word set in it at the place the scan has it. Same
page, same layout, real text, glyphs reused — a file that behaves like a born-digital journal article.

It is NOT evidence and never replaces the faithful PDF (docs/decisions.md, D14).

The text layer is the part that needs care. The font's joining forms (`uni0628.init`, `lamalef`) carry no cmap
entry, so a PDF writer cannot reverse them and the page extracts as junk — the same failure `pdf/fontfix.py`
repairs for the corpus's typeset pages. So after the page is written, the embedded font's ToUnicode is rebuilt
from the glyph NAMES, which do know what each form is.
"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import fitz
from fontTools.ttLib import TTFont

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
DPI = 300


def uni_of(name: str) -> str:
    """The characters a glyph stands for, from its name: `uni0628.medi` -> ب, `lamalef.fina` -> لا."""
    base = name.split(".")[0]
    if base == "lamalef":
        return "لا"
    if base == "space":
        return " "
    m = re.fullmatch(r"uni([0-9A-Fa-f]{4})", base)
    return chr(int(m.group(1), 16)) if m else ""


def tounicode_cmap(ttf: Path) -> tuple[str, int]:
    """A ToUnicode CMap for Identity-H: CID (= glyph id) -> the characters that glyph means."""
    f = TTFont(str(ttf)); order = f.getGlyphOrder()
    pairs = []
    for gid, name in enumerate(order):
        u = uni_of(name)
        if u:
            pairs.append((gid, "".join(f"{ord(c):04X}" for c in u)))
    f.close()
    body = "".join(f"<{gid:04X}> <{u}>\n" for gid, u in pairs)
    cmap = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n")
    # bfchar blocks of at most 100, as the spec requires
    for i in range(0, len(pairs), 100):
        chunk = pairs[i:i + 100]
        cmap += f"{len(chunk)} beginbfchar\n" + "".join(f"<{g:04X}> <{u}>\n" for g, u in chunk) + "endbfchar\n"
    cmap += "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
    return cmap, len(pairs)


def fix_tounicode(path: Path, ttf: Path) -> int:
    """Give our font a ToUnicode built from its glyph names — ONE stream, shared by every font dictionary.
    (Writing a copy per dictionary put 489 KB of identical CMaps in a one-page file.)"""
    cmap, n = tounicode_cmap(ttf)
    doc = fitz.open(path)
    shared = doc.get_new_xref()
    doc.update_object(shared, "<<>>")
    doc.update_stream(shared, cmap.encode("latin-1"), new=True)
    fixed = 0
    for pno in range(doc.page_count):
        for f in doc[pno].get_fonts(full=True):
            xref, base = f[0], f[3]
            if "Inkscript" not in base:
                continue
            doc.xref_set_key(xref, "ToUnicode", f"{shared} 0 R")
            fixed += 1
    # The restored font has no digits or punctuation (docs/typeface.md, known faults), so the layout engine
    # embeds whole fallback faces for them — 464 KB of Noto for a handful of glyphs. Subsetting keeps only
    # what the page uses. The real fix is to give the book's font its own digits.
    try:
        doc.subset_fonts(verbose=False)
    except Exception:
        pass
    tmp = path.with_suffix(".tu.pdf")
    doc.save(str(tmp), garbage=4, deflate=True); doc.close()
    tmp.replace(path)
    return fixed


def dedupe_fonts(path: Path) -> int:
    """`insert_htmlbox` embeds the font again on every call — 290 copies of one face on one page. Identical
    font files are collapsed to one and every descriptor repointed at it."""
    import hashlib
    doc = fitz.open(path)
    first = {}; freed = 0
    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref, compressed=True)
        except Exception:
            continue
        if "/FontFile2" not in obj:
            continue
        m = re.search(r"/FontFile2 (\d+) 0 R", obj)
        if not m:
            continue
        ff = int(m.group(1))
        try:
            data = doc.xref_stream_raw(ff)
        except Exception:
            continue
        h = hashlib.sha1(data).hexdigest()
        if h in first:
            doc.xref_set_key(xref, "FontFile2", f"{first[h]} 0 R"); freed += 1
        else:
            first[h] = ff
    tmp = path.with_suffix(".dedupe.pdf")
    doc.save(str(tmp), garbage=4, deflate=True); doc.close()
    tmp.replace(path)
    return freed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("built"); ap.add_argument("stem")
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--font", default="experiments/11_typeface/out/Inkscript-0582-Restored.ttf")
    ap.add_argument("--out", default=None)
    ap.add_argument("--fill", type=float, default=0.92, help="share of a word's box the type should fill")
    a = ap.parse_args()

    built = Path(a.built); stem = a.stem
    shapes = json.load(open(built / f"{stem}.shapes.json"))
    words = [w for w in shapes["placements"] if w["page"] == a.page]
    if not words:
        sys.exit(f"no words on page {a.page}")

    ref = fitz.open(built / f"{stem}.pdf")                    # the faithful build: same page size
    W, H = ref[a.page - 1].rect.width, ref[a.page - 1].rect.height
    ref.close()
    px_to_pt = 72.0 / DPI

    # A LINE is the unit, set as one run that cannot wrap, at one size, right-aligned on the line's right
    # edge. Three earlier shapes failed and are worth recording: sizing each word to its own box gave the same
    # face in several sizes down a line; letting the engine shrink each word to fit did the same; pinning every
    # word at the scan's x with uniform size made words collide, because the restored face does not set to the
    # same width as the printed one. A typeset page has its own metrics — so match the LINE, not the word, and
    # let the words space themselves. That is what makes it read as typeset rather than traced.
    rest = sorted(words, key=lambda w: w["box"][1]); lines = []
    while rest:
        seed = rest.pop(0); y0, y1 = seed["box"][1], seed["box"][3]; line = [seed]
        for w in list(rest):
            b = w["box"]
            if min(y1, b[3]) - max(y0, b[1]) > 0.4 * min(y1 - y0, max(1, b[3] - b[1])):
                line.append(w); rest.remove(w); y0, y1 = min(y0, b[1]), max(y1, b[3])
        lines.append((y0, y1, sorted(line, key=lambda w: -w["box"][2])))     # right to left: reading order

    doc = fitz.open(); pg = doc.new_page(width=W, height=H)
    arch = fitz.Archive(); arch.add(str(Path(a.font)), "ink.ttf")
    placed = skipped = 0
    for ly0, ly1, line in lines:
        txt = " ".join(w["text"].strip() for w in line if w["text"].strip())
        if not txt:
            continue
        x0 = min(w["box"][0] for w in line) * px_to_pt
        x1 = max(w["box"][2] for w in line) * px_to_pt
        hs = sorted(w["box"][3] - w["box"][1] for w in line)
        h = hs[int(0.7 * (len(hs) - 1))] * px_to_pt
        size = max(3.0, h * a.fill)
        css = (f"@font-face {{font-family: ink; src: url(ink.ttf);}} "
               f"* {{font-family: ink; font-size: {size:.2f}px; margin:0; padding:0; line-height:1.0;}}")
        # the box keeps the line's right edge and its top; it may reach left of the printed line, since the
        # restored face sets to its own width. Height is one line only, so nothing can wrap into the next.
        # left edge: the whole page. The restored face sets wider than the printed one, and a box cut to the
        # printed line's width clipped the ends of long lines instead of letting them run.
        box = fitz.Rect(4, ly0 * px_to_pt - size * 0.25, x1 + 2, ly0 * px_to_pt + size * 1.45)
        esc = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        try:
            rc = pg.insert_htmlbox(box, f'<div dir="rtl" style="text-align:right;white-space:nowrap">{esc}</div>',
                                   css=css, archive=arch, scale_low=0.45)
            ok = rc[1] > 0
        except Exception:
            ok = False
        placed += len(line) if ok else 0; skipped += 0 if ok else len(line)
    out = Path(a.out) if a.out else Path(__file__).parent / "out" / f"{stem}_p{a.page}_restored.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out), garbage=4, deflate=True); doc.close()
    dedupe_fonts(out)
    n = fix_tounicode(out, Path(a.font))
    print(f"{placed} words set, {skipped} not placed -> {out.resolve()}  (ToUnicode rebuilt on {n} font copies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
