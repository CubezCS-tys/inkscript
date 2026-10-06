"""A book's typeface (experiment 11's make_font: collect + choose — each letter-form restored from its best printings)
under a variant of the cutter, kept as glyph outlines; and a sheet comparing two variants glyph by glyph.

    ../../.venv/bin/python font25.py build VARIANT DOC        -> out/font/<variant>_<doc>.pkl
    ../../.venv/bin/python font25.py sheet DOC VA VB          -> out/font_<doc>_<va>_<vb>.png (+ .json: changed forms)
"""
import sys, pickle, json, importlib.util
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("mf", REPO / "experiments/11_typeface/make_font.py"); mf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mf)
sys.path.insert(0, str(REPO / "experiments/16_feel")); import bench
FULL = "--full" in sys.argv
ORDER = "ابتثجحخدذرزسشصضطظعغفقكلمنهوىيةئءأإآؤ"
FORMS = ("iso", "init", "med", "fin")


def build(variant, doc):
    import patch25; patch25.use(variant)
    cfg = bench.SUITE[doc]; plans, iso = mf.collect(str(cfg["azure"]), str(cfg["scan"]))
    forms = mf.choose(plans, iso)
    out = {kk: dict(paths=[np.asarray(p) for p in g["paths"]], holes=g["holes"], cell=g["cell"], n=g["n"]) for kk, g in forms.items()}
    (HERE / "out/font").mkdir(parents=True, exist_ok=True); pickle.dump(out, open(HERE / f"out/font/{variant}_{doc}.pkl", "wb"))
    print(variant, doc, len(out), "forms", flush=True)


def raster(g):
    im = np.zeros((mf.CH, mf.CW), np.uint8)
    for path, hole in sorted(zip(g["paths"], g["holes"]), key=lambda t: t[1]):
        cv2.fillPoly(im, [np.round(np.asarray(path)).astype(np.int32)], 0 if hole else 1)
    return im


def tile(g, w=150):
    im = raster(g)[mf.CBASE - 2 * mf.HI + 20:mf.CBASE + mf.HI - 10, mf.XR - 4 * mf.HI:mf.XR + 30]
    t = np.full(im.shape + (3,), 255, np.uint8); t[im > 0] = (40, 40, 40)
    t[mf.HI * 2 - 20, :] = (210, 210, 210)
    return cv2.resize(t, (w, int(w * t.shape[0] / t.shape[1])), interpolation=cv2.INTER_AREA)


def iou(a, b):
    A, B = raster(a) > 0, raster(b) > 0; return float((A & B).sum() / max(1, (A | B).sum()))


def sheet(doc, va, vb):
    import fitz
    def text_img(t, size=22, w=78, h=40):
        doc = fitz.open(); pg = doc.new_page(width=w, height=h); pg.insert_text((4, h - 10), t, fontsize=size, fontfile="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", fontname="dj")
        pix = pg.get_pixmap(); return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3][:, :, ::-1].copy()
    A = pickle.load(open(HERE / f"out/font/{va}_{doc}.pkl", "rb")); B = pickle.load(open(HERE / f"out/font/{vb}_{doc}.pkl", "rb"))
    keys = sorted(set(A) | set(B), key=lambda kk: (ORDER.find(kk[0][-1]) if kk[0][-1] in ORDER else 99, kk[0], FORMS.index(kk[1])))
    rows = []; info = {}
    for kk in keys:
        a, b = A.get(kk), B.get(kk); v = iou(a, b) if a and b else 0.0; info[f"{kk[0]} {kk[1]}"] = round(v, 3)
        if v >= 0.85 and not FULL: continue                                          # unchanged (a vote of 15 printings moves a little)
        ta = tile(a) if a else np.full((96, 150, 3), 255, np.uint8); tb = tile(b) if b else np.full_like(ta, 255)
        rows.append((kk, ta, tb, v))
    per = 4; th = rows[0][1].shape[0] if rows else 96; cw = 2 * 150 + 90
    img = np.full((30 + th * ((len(rows) + per - 1) // per) + 10, per * cw, 3), 255, np.uint8)
    cv2.putText(img, f"{doc}: changed letter-forms (left {va}, right {vb}); unchanged not shown", (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    for i, (kk, ta, tb, v) in enumerate(rows):
        x, y = (i % per) * cw, 30 + (i // per) * th
        img[y:y + th, x + 80:x + 230] = ta[:th]; img[y:y + th, x + 230:x + 380] = tb[:th]
        t = text_img(kk[0]); img[y + 5:y + 5 + t.shape[0], x:x + t.shape[1]] = t
        cv2.putText(img, f"{kk[1]} {v:.2f}", (x + 4, y + 62), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (90, 90, 90), 1)
    cv2.imwrite(str(HERE / f"out/font_{doc}_{va}_{vb}{'_full' if FULL else ''}.png"), img); json.dump(info, open(HERE / f"out/font_{doc}_{va}_{vb}.json", "w"), ensure_ascii=False, indent=0)
    print(len(rows), "changed of", len(keys))


if __name__ == "__main__":
    if sys.argv[1] == "build": build(sys.argv[2], sys.argv[3])
    else: sheet(*[a for a in sys.argv[2:] if a != "--full"][:3])
