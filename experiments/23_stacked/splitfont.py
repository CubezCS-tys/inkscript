"""Hand-made test PDFs: chosen letters of one word get their own copy of the line's Type 3 font whose FontBBox is
that letter's own declared box (d1), in their own TJ inside the line's BT ... ET. Chromium 153 draws a highlight's
height from the font's FontBBox (measured: chromium.py), so this is the only way found to give one letter a
highlight that is not the line's full height.

    ../../.venv/bin/python splitfont.py IN.pdf OUT.pdf PAGE WORD K[,K...] [--ink]
      K: letters in reading order (1-based). --ink: also narrow the letter's d1 box to its own ink (x and y).
"""
import sys, re
import fitz
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import glyphs as G


def ink_box(doc, g):
    body = doc.xref_stream(g["proc_xref"]).decode().split("\n")
    pts = [(int(a), int(b)) for a, b in re.findall(r"(-?\d+) (-?\d+) [ml]", "\n".join(body[1:]))]
    return min(x for x, _ in pts), min(y for _, y in pts), max(x for x, _ in pts), max(y for _, y in pts)


def split(doc, pno, run, ks, ink=False, tag="S"):
    pg = doc[pno - 1]; fname = run[0]["font"]; fx = run[0]["font_xref"]; obj = doc.xref_object(fx)
    n = len(run); chosen = [run[n - k] for k in ks]                      # run is left->right; k counts from the right
    res = doc.xref_get_key(pg.xref, "Resources"); rx = int(res[1].split()[0])
    fk = doc.xref_get_key(rx, "Font"); fdx, pre = (int(fk[1].split()[0]), "") if fk[0] == "xref" else (rx, "Font/")
    newnames = {}
    for i, g in enumerate(chosen):
        d1 = g["d1"]
        if ink:
            x0, y0, x1, y1 = ink_box(doc, g); d1 = [d1[0], 0, x0, y0, x1, y1]
            body = doc.xref_stream(g["proc_xref"]).decode().split("\n", 1)
            doc.update_stream(g["proc_xref"], (f"{d1[0]:.0f} 0 {x0} {y0} {x1} {y1} d1\n" + body[1]).encode())
        nobj = re.sub(r"/FontBBox\s*\[[^\]]*\]", f"/FontBBox [{d1[2]:.0f} {d1[3]:.0f} {d1[4]:.0f} {d1[5]:.0f}]", obj)
        nx = doc.get_new_xref(); doc.update_object(nx, nobj); nm = f"{fname}{tag}{i}"
        doc.xref_set_key(fdx, f"{pre}{nm}", f"{nx} 0 R"); newnames[g["code"]] = nm
    for cx in pg.get_contents():
        c = doc.xref_stream(cx).decode("latin1")
        m = re.search(r"BT /%s ([\d.]+) Tf ([-\d. ]+) Tm \[(.*?)\] TJ ET" % re.escape(fname), c, re.S)
        if not m: continue
        size = m.group(1); toks = re.findall(r"<[0-9A-F]{2}>|-?[\d.]+", m.group(3)); out = []; cur = []
        for t in toks:
            if t.startswith("<") and int(t[1:3], 16) in newnames:
                if cur: out.append(f"[{' '.join(cur)}] TJ")
                out.append(f"/{newnames[int(t[1:3], 16)]} {size} Tf [{t}] TJ /{fname} {size} Tf"); cur = []
            else: cur.append(t)
        if cur: out.append(f"[{' '.join(cur)}] TJ")
        new = f"BT /{fname} {size} Tf {m.group(2)} Tm " + " ".join(out) + " ET"
        doc.update_stream(cx, (c[:m.start()] + new + c[m.end():]).encode("latin1")); return new
    raise SystemExit("line not found")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    doc = fitz.open(a[0]); pno = int(a[2]); gl = G.glyphs(doc, pno); run = G.find_word(gl, a[3])[0]
    print(split(doc, pno, run, [int(k) for k in a[4].split(",")], "--ink" in sys.argv)[:300])
    doc.save(a[1])
