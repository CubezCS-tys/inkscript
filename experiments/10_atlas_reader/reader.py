"""Can a document's own alphabet read its own words?

The atlas (experiment 09: the mean picture of every letter-form, learned from the document's ink with the
OCR's text as the label) is learned on some pages. On a held-out page every connected piece is then read
BLIND — no text, not even the number of letters: along the piece's pen path, the best sequence of atlas letters
is chosen (shape likeness + the hard facts: dots, tall stroke, bowl + usual length), under the script's grammar
(initial, medials, final; or one isolated letter). The reading is compared with the OCR's.

    python reader.py <azure.json> <scan.pdf> <train pages e.g. 1,2,3,4> <test pages e.g. 5> <out.png>
"""
import sys, json, os
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np, cv2, fitz
from inkscript.geometry import penpath as P
from inkscript.geometry.letters import line_geometry, ASC, DESC_ANY, DESC_END, DOTS_ABOVE, DOTS_BELOW
from inkscript.text import MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word

LIKE0 = 0.45                                                          # a letter pays its way only above this likeness, with every fact in order


def pieces_of(azure, scan, pages):
    words, _, dims = load_azure(Path(azure)); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
    doc = fitz.open(scan)
    for pn in pages:
        pw = [w for w in words if w["page"] == pn]; pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
        W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
        for L in lines:
            bl = [b for w in L if w["blobs"] for b in w["blobs"]]
            if not bl: continue
            lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
            for w in L:
                if not w["blobs"] or MARKS.search(w["text"]): continue
                for pc in split_word(w, lh):
                    uf = P.units_forms(pc["text"].strip())
                    if uf and len(set(uf[1]) & {"iso"}) <= 1 and uf[1].count("init") <= 1: yield pn, pc, uf, lg     # one joined run (or one letter)


def label_facts(G, lab, a, b):
    c, f = lab; last = f in ("fin", "iso"); tol = G["stroke"]
    want_asc = c in ASC or c.startswith("ل"); asc_ok = G["asc"][a:b].sum() >= 1 if want_asc else G["tall"][a:b].sum() < 2
    want_desc = c in DESC_ANY or (last and c in DESC_END); desc_ok = G["desc"][a:b].sum() >= 1 if want_desc else G["deep"][a:b].sum() < 2
    wa = DOTS_ABOVE.get(c[0], 0); wb = DOTS_BELOW.get(c[0], 0)
    cnt = lambda above, want: sum(1 for x, ab in G["dots"] if ab == above and ((a - tol <= x < b + tol) if want else (a + tol <= x < b - tol)))
    da = cnt(True, wa > 0); db = cnt(False, wb > 0 or c == "ي")
    if c == "ي" and last: wb = db if db in (0, 2) else 2
    near = lambda got, want: got == want or (want >= 2 and 1 <= got <= want)
    return (1.5 if asc_ok else -6.0) + (1.0 if desc_ok else -2.0) + (2.0 if near(da, wa) else -5.0) + (2.0 if near(db, wb) else -5.0)


def read(p, packs, length):
    """Best sequence of atlas letters along the pen path: [(letter, form), ...] in reading order, and its score."""
    G = p["G"]; pos = [0] + p["cand"] + [G["W"]]; m = len(pos); rise = RISE_OF[id(p)]
    memo = {}
    def s(lab, a, b):
        it = P.letter_img(p, a, b)
        if it is None or lab not in packs: return -1e9
        if (a, b) not in memo:
            # the mean picture shortlists; the stored examples decide: a mean washes out exactly the small marks
            # (a hamza, one dot or two) that tell letters apart, an individual example keeps them
            mean = {l: P.likeness(it, packs[l]) for l in packs}; top = sorted(mean, key=mean.get, reverse=True)[:8]
            memo[(a, b)] = {l: max([P.likeness(it, e) for e in EXAMPLES.get(l, [])] + [mean[l]]) for l in top}
        lk = memo[(a, b)].get(lab)
        if lk is None: return -1e9
        mu = length.get(lab); w = -0.8 * np.log(max(b - a, 1) / rise / mu) ** 2 if mu else 0.0
        return P.ATLAS * (lk - LIKE0) + (label_facts(G, lab, a, b) - 6.5) + w
    labs = list(packs); best_iso = max(((s(l, 0, G["W"]), [l]) for l in labs if l[1] == "iso"), default=(-1e9, []), key=lambda t: t[0])
    # from the left end: the final letter, then medials, then the initial letter reaching the right end
    NEG = -1e9; fin = {}; 
    for bi in range(1, m - 1):
        v, l = max(((s(l, 0, pos[bi]), l) for l in labs if l[1] == "fin"), default=(NEG, None), key=lambda t: t[0]); fin[bi] = (v, [l])
    state = dict(fin)                                                  # state[bi] = best (score, labels from the left) covering [0, pos[bi]) ending in fin/med
    for bi in range(2, m - 1):
        for ai in range(1, bi):
            if ai not in state or state[ai][0] <= NEG / 2 or pos[bi] - pos[ai] < 3: continue
            v, l = max(((s(l, pos[ai], pos[bi]), l) for l in labs if l[1] == "med"), default=(NEG, None), key=lambda t: t[0])
            if state[ai][0] + v > state[bi][0]: state[bi] = (state[ai][0] + v, state[ai][1] + [l])
    best = best_iso
    for ai, (v0, seq) in state.items():
        if v0 <= NEG / 2 or G["W"] - pos[ai] < 3: continue
        v, l = max(((s(l, pos[ai], G["W"]), l) for l in labs if l[1] == "init"), default=(NEG, None), key=lambda t: t[0])
        if v0 + v > best[0]: best = (v0 + v, seq + [l])
    return best[1][::-1], best[0]


def edit(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1): prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[-1]


RISE_OF = {}; EXAMPLES = {}
def main(azure, scan, train, test, out):
    tr = []
    for pn, pc, (units, forms), lg in pieces_of(azure, scan, train):
        if len(units) < 2: continue
        p = P.plan(units, pc["blobs"], lg, forms)
        if p: tr.append(p); RISE_OF[id(p)] = lg["rise"]
    atlas = P.solve(tr); packs = atlas["packs"]; ln = defaultdict(list)
    for p in tr:
        for k, (a, b) in enumerate(P.intervals(p)): ln[P.key(p, k)].append((b - a) / RISE_OF[id(p)])
    # isolated letters never go through `plan` (nothing to cut): their pictures are learned here
    iso = defaultdict(list)
    for pn, pc, (units, forms), lg in pieces_of(azure, scan, train):
        if len(units) == 1 and lg and lg["rise"] >= 10:
            q = blind(pc, lg)
            if q:
                it = P.letter_img(q, 0, q["G"]["W"])
                if it is not None: iso[(P._base(units[0]), "iso")].append(P.canvas_of(it)); ln[(P._base(units[0]), "iso")].append(q["G"]["W"] / lg["rise"])
    packs = dict(packs); packs.update(P.pack({k: np.mean(np.stack(v), 0) for k, v in iso.items() if len(v) >= 3}))
    length = {k: float(np.median(v)) for k, v in ln.items()}
    import random; random.seed(1); ex = defaultdict(list)
    for p in tr:
        for k, (a, b) in enumerate(P.intervals(p)):
            it = P.letter_img(p, a, b)
            if it is not None and p["scores"][k] is not None and p["scores"][k] >= 0.45: ex[P.key(p, k)].append(P.canvas_of(it))
    for k, v in iso.items(): ex[k] += v
    for k, v in ex.items():
        EXAMPLES[k] = [pk for pk in P.pack({i: c for i, c in enumerate(random.sample(v, min(30, len(v))))}).values()]
    print("isolated forms learned:", sorted((k[0], len(v)) for k, v in iso.items()))
    print(f"learned on pages {train}: {len(tr)} joined pieces, {len(packs)} letter-forms in the atlas ({sum(1 for k in packs if k[1] == 'iso')} isolated)")
    n = ok = ch = err = unread = 0; wrong = []; by_len = Counter(); ok_len = Counter()
    for pn, pc, (units, forms), lg in pieces_of(azure, scan, test):
        truth = [P._base(u) for u in units]
        if not lg or lg["rise"] < 10: continue
        q = blind(pc, lg); n += 1; by_len[min(len(truth), 5)] += 1
        if q is None: unread += 1; ch += len(truth); err += len(truth); continue
        seq, score = read(q, packs, length); got = [l[0] for l in seq]
        e = edit(got, truth); ch += len(truth); err += e
        if e == 0: ok += 1; ok_len[min(len(truth), 5)] += 1
        else: wrong.append(("".join(truth), "".join(got), q))
    print(f"read blind on pages {test}: {n} pieces; same as the OCR: {ok} ({100 * ok / n:.1f}%); letters right {100 * (1 - err / ch):.1f}%; no pen path {unread}")
    print("by piece length (letters: agree/total):", {k: f"{ok_len[k]}/{by_len[k]}" for k in sorted(by_len)})
    print("confusions (OCR -> ours):", [(t, g) for t, g, _ in wrong[:40]])
    tiles = []
    for t, g, q in wrong[:60]:
        m = q["F"]["main"]; im = cv2.cvtColor((255 - m.astype(np.uint8) * 255), cv2.COLOR_GRAY2BGR); im = cv2.resize(im, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
        tiles.append(cv2.copyMakeBorder(im, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    if tiles:
        h = max(t.shape[0] for t in tiles); rows = []; row = []; ws = 0
        for t in tiles:
            t = cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            if ws + t.shape[1] > 2200 and row: rows.append(np.hstack(row)); row = []; ws = 0
            row.append(t); ws += t.shape[1]
        rows.append(np.hstack(row)); wm = max(r.shape[1] for r in rows); os.makedirs(os.path.dirname(out), exist_ok=True)
        cv2.imwrite(out, np.vstack([cv2.copyMakeBorder(r, 0, 0, 0, wm - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]))


def blind(pc, lg):
    """A piece on its pen path with its candidate cut points — no text involved. (The geometry half of `penpath.plan`.)"""
    from inkscript.geometry.letters import piece_mask, analyse, joins
    mask, off = piece_mask(pc["blobs"])
    if mask.shape[1] < 4 or mask.shape[1] > 1500: return None
    F = analyse(mask, lg, off[1]); real = None
    if F is None:
        jn = P.bridge(mask, 1.5 * lg["rise"])
        if jn is None: return None
        F = analyse(jn, lg, off[1]); real = mask
        if F is None: return None
    r = P.unroll(F, lg, off[1])
    if r is None: return None
    G, ink_s, trunk = r; S = G["W"]; stroke = G["stroke"]
    mass = np.bincount(ink_s[ink_s >= 0], minlength=S).astype(float); sm = np.convolve(mass, np.ones(3) / 3, mode="same")
    mins = [i for i in range(3, S - 3) if sm[i] <= sm[i - 1] and sm[i] <= sm[i + 1] and sm[i] <= 1.6 * stroke]; kept = []
    for c in sorted(set(joins(G)) | set(mins)):
        if kept and c - kept[-1] < 3:
            if sm[c] < sm[kept[-1]]: kept[-1] = c
        else: kept.append(c)
    if len(kept) > 14: kept = sorted(sorted(kept, key=lambda c: sm[c])[:14])
    conn = np.zeros(S, bool); x = 0; th = G["thin"]
    while x < S:
        if th[x]:
            j = x
            while j < S and th[j]: j += 1
            if j - x >= 4 * stroke: conn[x + stroke:j - stroke] = True
            x = j
        else: x += 1
    q = dict(kind="pen", F=F, G=G, ink_s=ink_s.astype(np.int16), trunk=trunk, off=off, cand=[c for c in kept if 0 < c < S], conn=conn, real=real,
             sc=P.RISE / lg["rise"], base=lg["baseline"] - off[1], cache={}, units=[], forms=[], n=0)
    RISE_OF[id(q)] = lg["rise"]; return q


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [int(x) for x in sys.argv[3].split(",")], [int(x) for x in sys.argv[4].split(",")], sys.argv[5])
