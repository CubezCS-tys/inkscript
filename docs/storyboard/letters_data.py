"""Data for the storyboard's letter, atlas, scale and typeface chapters, from the pipeline's own objects.

Called by build.py. Everything here is read out of the real cutter (`inkscript.geometry.penpath`), the real
runs' coverage files and the real fonts — nothing is drawn by hand.
"""
import base64, json, sys, importlib.util
from collections import defaultdict
from pathlib import Path
import numpy as np, cv2, fitz

HERE = Path(__file__).parent; ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "src"))
from inkscript.geometry import penpath as P
from inkscript.geometry.letters import line_geometry, piece_mask, analyse
from inkscript.text import MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word


def b64(a: bytes) -> str: return base64.b64encode(a).decode()


def png(img: np.ndarray) -> str: return b64(cv2.imencode(".png", img)[1].tobytes())


def pieces(azure: Path, scan: Path, pages):
    """Every joined piece of the given pages with its line geometry."""
    words, _, dims = load_azure(Path(azure)); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
    doc = fitz.open(scan)
    for pn in pages:
        pw = [w for w in words if w["page"] == pn]
        if not pw or pn not in dims: continue
        pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
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
                    if uf and len(uf[0]) >= 2: yield pn, w["text"], pc, uf, lg


def owner_map(p) -> np.ndarray:
    """Which letter (reading order, 1-based; 0 = no ink) every pixel belongs to, marks included."""
    own = np.zeros(p["ink_s"].shape, np.uint8)
    for k, (a, b) in enumerate(P.intervals(p)): own[P._mask(p, a, b, owner=k)] = k + 1
    return own


def pen_piece(p, word: str, note: str) -> dict:
    """Everything the 'follow the pen' stepper draws, in the piece's own pixel grid."""
    F, G = p["F"], p["G"]; H, W = p["ink_s"].shape; ink = (p["ink_s"] >= 0) if p.get("real") is None else p["real"]
    every = ink | np.isin(F["lab"], [m[2] for m in G["marks"]]) if G.get("marks") else ink
    sk = P.thin(F["main"]); S = G["W"]; bounds = [0] + list(p["cuts"]) + [S]
    trunk = [[int(x), int(y)] for y, x in p["trunk"]][::-1]                       # from the pen's start (right) to its end (left)
    xs = np.where(p["ink_s"] >= 0)[1]; X = lambda s: int(xs.min()) if s <= 0 else int(xs.max()) + 1 if s >= S else int(p["trunk"][s][1])
    bx = [X(s) for s in bounds]
    if any(b - a < 2 for a, b in zip(bx, bx[1:])): bx = [int(round(bx[0] + (bx[-1] - bx[0]) * s / S)) for s in bounds]
    n = p["n"]; cells = [[bx[n - 1 - k], bx[n - k]] for k in range(n)]           # reading order
    s32 = p["ink_s"].astype(np.int32); s16 = np.where(s32 >= 0, s32, 65535).astype("<u2")
    return dict(word=word, text="".join(p["units"]), units=p["units"], note=note, w=W, h=H, S=int(S), base=int(p["base"]),
                ink=png((every * 255).astype(np.uint8)), skeleton=png((sk * 255).astype(np.uint8)), smap=b64(s16.tobytes()),
                owner=png(owner_map(p)), trunk=trunk, cand=[[int(p["trunk"][c][1]), int(p["trunk"][c][0])] for c in p["cand"]],
                cuts=[[int(p["trunk"][c][1]), int(p["trunk"][c][0])] for c in p["cuts"]], cells=cells,
                xmin=int(xs.min()), xmax=int(xs.max()) + 1)


def atlas_rounds(plans, rounds=4):
    """The document's atlas before any round and after each: [{key: png}], and how many pieces were re-cut."""
    snaps = []; ref = P.build_atlas(plans); packs = P.pack(ref); snaps.append(dict(ref)); recut = []
    for _ in range(rounds):
        changed = 0
        for p in plans:
            c = P.best_cuts(p, packs)
            if c is not None and c != p["cuts"]: p["cuts"] = c; changed += 1
        new = P.build_atlas(plans, packs); ref = {k: 0.5 * ref[k] + 0.5 * v if k in ref else v for k, v in new.items()}; packs = P.pack(ref)
        snaps.append(dict(ref)); recut.append(changed)
    counts = defaultdict(int)
    for p in plans:
        for k in range(p["n"]): counts[P.key(p, k)] += 1
    keys = sorted(snaps[-1], key=lambda k: (k[0], ["iso", "init", "med", "fin"].index(k[1])))
    enc = lambda im: png((255 - np.clip(im / max(1e-6, im.max()), 0, 1) * 255).astype(np.uint8))
    return dict(keys=[dict(letter=k[0], form=k[1], n=counts[k]) for k in keys], rounds=[[enc(s[k]) if k in s else None for k in keys] for s in snaps],
                recut=recut, base_row=P.BASE, size=P.C), dict(ref=ref, packs=packs)


def font_vote(azure: Path, scan: Path, letter: str, form: str):
    """The printings behind one letter-form and the restored letter they vote into (experiment 11)."""
    spec = importlib.util.spec_from_file_location("mf", ROOT / "experiments" / "11_typeface" / "make_font.py"); mf = importlib.util.module_from_spec(spec); spec.loader.exec_module(mf)
    plans, iso = mf.collect(str(azure), str(scan)); P2 = mf.P; P2.solve([p for p, _, _ in plans]); body = float(np.median([lg["rise"] for _, _, lg in plans])); pool = defaultdict(list)
    for p, pc, lg in plans:
        if not P2.accepted(p) or abs(lg["rise"] / body - 1) > 0.15: continue
        lb = P2.letter_blobs(p, pc["blobs"])
        if len(lb) != p["n"]: continue
        for k, s in enumerate(p["scores"]):
            if s is not None and P2.key(p, k) == (letter, form):
                b = lb[k][0]; pool[(letter, form)].append(dict(score=s, paths=b["paths"], holes=b["holes"], base=lg["baseline"], rise=lg["rise"], cell=b["cell"]))
    ex = pool[(letter, form)]; w = np.array([(e["cell"][1] - e["cell"][0]) / e["rise"] for e in ex]); med = float(np.median(w))
    ex = sorted([e for e, x in zip(ex, w) if abs(x / med - 1) <= 0.2], key=lambda e: -e["score"])[:mf.TOP]
    band = mf.join_band(pool); out = mf.restore(ex, form, band); x0 = mf.XR - int(1.6 * mf.HI); crop = lambda im: im[int(0.6 * mf.HI):int(2.7 * mf.HI), x0:mf.XR + 12]
    final = np.zeros((mf.CH, mf.CW), np.uint8)
    for path, hole in sorted(zip(out["paths"], out["holes"]), key=lambda t: t[1]): cv2.fillPoly(final, [np.round(path).astype(np.int32)], 0 if hole else 1)
    stack = np.mean([mf.render(e, med) for e in ex], 0)
    return dict(letter=letter, form=form, n=len(ex), printings=[png(255 - 255 * crop(mf.render(e, med))) for e in ex],
                stack=png((255 - 255 * crop(stack)).astype(np.uint8)), restored=png(255 - 255 * crop(final)))


def scale(first: Path, second: Path) -> dict:
    a = {r["stem"]: r for r in json.load(open(first))}; b = {r["stem"]: r for r in json.load(open(second))}; rows = []
    for stem, r in b.items():
        if r["words"] >= 50 and stem in a and a[stem]["words"] >= 50:
            rows.append(dict(stem=stem, pages=r["pages"], words=r["words"], first=round(100 * a[stem]["cut"] / a[stem]["words"], 1), second=round(100 * r["cut"] / r["words"], 1)))
    return dict(docs=sorted(rows, key=lambda r: r["second"]))


def build(fixture: Path, doc_kaf: tuple, doc_fi: tuple, cov_first: Path, cov_second: Path, fonts: dict) -> dict:
    S = "0582-004-009-012"; az = fixture / "azure" / S / f"{S}.json"; scan = fixture / "input" / f"{S}.pdf"
    plans = []; meta = []
    for pn, word, pc, (units, forms), lg in pieces(az, scan, range(1, 6)):
        p = P.plan(units, pc["blobs"], lg, forms)
        if p: plans.append(p); meta.append((pn, word))
    atlas, state = atlas_rounds(plans)
    for p in plans: P.score_plan(p, state["packs"], {})
    want = [("لمعجم", "An underlined word: the underline is ink, but it is not a dot"), ("كا", "The pair the owner first caught being sliced in half"),
            ("على", "A tail that sweeps back under its neighbours"), ("لمشر", "Tooth letters: the dots decide which tooth is which"), ("خلال", "Two runs that touch in the ink — cut along one path")]
    pens = []
    for text, note in want:
        hit = next((i for i, p in enumerate(plans) if "".join(p["units"]) == text and P.accepted(p)), None)
        if hit is None: hit = next((i for i, p in enumerate(plans) if "".join(p["units"]) == text), None)
        if hit is not None: pens.append(pen_piece(plans[hit], meta[hit][1], note))
    for (azj, pdf, pages, texts, note) in (doc_kaf, doc_fi):
        loc = []
        for pn, word, pc, (units, forms), lg in pieces(azj, pdf, pages):
            if "".join(units) in texts:
                p = P.plan(units, pc["blobs"], lg, forms)
                if p: loc.append((p, word, pc, units, forms, lg))
            if len(loc) >= 40: break
        if not loc: continue
        P.solve([x[0] for x in loc]); p, word = loc[0][0], loc[0][1]; pens.append(pen_piece(p, word, note))
    # the في story: the same piece cut from the baseline start and from the body start
    fi = None
    for pn, word, pc, (units, forms), lg in pieces(doc_fi[0], doc_fi[1], doc_fi[2]):
        if "".join(units) == "في":
            mask, off = piece_mask(pc["blobs"]); F = analyse(mask, lg, off[1])
            if F is None: continue
            a = P._on_path(units, forms, F, lg, off, None, "baseline"); b = P._on_path(units, forms, F, lg, off, None, "upper")
            if a and b and P._facts_sum(b) > P._facts_sum(a) + 3:
                fi = dict(before=pen_piece(a, word, "path started on the ya's tail"), after=pen_piece(b, word, "path started on the fa's body")); break
    return dict(pens=pens, atlas=atlas, fi=fi, scale=scale(cov_first, cov_second),
                vote=font_vote(az, scan, "ع", "med"), fonts={k: b64(Path(v).read_bytes()) for k, v in fonts.items()})
