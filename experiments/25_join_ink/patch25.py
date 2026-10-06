"""Proposed changes to penpath, as patched copies applied to the imported module in this process only (src/ is never
edited; the same change as a diff against src: penpath.patch).

"lump": a HEAD — a filled loop, the round head of و, the head of ف/ق, the eye of م/ه — hangs from ONE point of the pen
path (the pen arrives from the previous letter, circles the head, and leaves into the tail from the same point, so
the shortest path skips the circle). Whoever owns that point owns the whole head. Today nothing stops the previous
letter from owning it, and the document's atlas then learns that a final و is a bare tail and confirms it in every
copy. A new hard fact: a letter that has no head (ا د ر ل ن ب ت ي ى س …) must not own one; a letter that has one is
rewarded for owning it. A head is found as a point of the path whose own ink is much thicker than a stroke.
"""
import numpy as np, cv2
from inkscript.geometry import penpath as P

ORIG = {k: getattr(P, k) for k in ("unroll", "letter_blobs", "_mask", "best_cuts", "plan", "_on_path", "_facts_score", "stem_foot")}

HEADED = set("وؤفقمهةصضطظ")                     # a closed head in every form
HEADED_JOINING = set("عغ")                       # closed only where the letter joins on its left (initial, medial)
HEADLESS = set("اأإآدذرزلكبتثنيىسشئ")
LUMP = 1.6                                       # a head: ink at least this many times a stroke's thickness
W_OWN, W_STOLEN = 1.5, 4.0
CFG = dict(lump=LUMP, own=W_OWN, stolen=W_STOLEN)


def lumps(p):
    """Path positions whose own ink is a lump: its thickest point at least LUMP x the piece's usual stroke."""
    if "lumps" in p: return p["lumps"]
    ink = p["ink_s"]; S = p["G"]["W"]; main = (ink >= 0).astype(np.uint8)
    dt = cv2.distanceTransform(np.pad(main, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    ys, xs = np.where(ink >= 0); s = ink[ys, xs]; m = np.zeros(S); np.maximum.at(m, s, dt[ys, xs])
    st = float(np.median(m[m > 0])) if (m > 0).any() else 1.0
    p["lumps"] = [int(i) for i in range(S) if m[i] >= CFG["lump"] * st]
    return p["lumps"]


def headed(c, form):
    return c in HEADED or (c in HEADED_JOINING and form in ("init", "med"))


def _facts_score(p, k, a, b):
    v = ORIG["_facts_score"](p, k, a, b)
    c = P._base(p["units"][k]); has = any(a <= x < b for x in lumps(p))
    if headed(c, p["forms"][k]): v += CFG["own"] if has else 0.0
    elif c in HEADLESS and has: v -= CFG["stolen"]
    return v


def stem_foot(trunk, rise) -> int:
    """penpath.stem_foot, also when the stem wiggles or carries a flag at its top (a hamza's alef, a serif): the walk
    down the stem stopped at the first pixel step to the right, so the stem was not recognised and a final أ kept
    the whole stroke back to its neighbour. Here the walk looks a quarter of a rise ahead and stops only where the
    path ahead runs more across than down; the foot is the lowest point just after."""
    j = ORIG["stem_foot"](trunk, rise)
    if j: return j
    t = np.array(trunk); y, x = t[:, 0], t[:, 1]; n = len(t); w = max(3, int(0.25 * rise)); j = 0
    while j + 1 < n:
        e = min(j + w, n - 1); dy, dx = y[e] - y[0 if False else j], abs(x[e] - x[j])
        if dy <= 0 or dx > dy: break
        j += 1
    e = min(j + w, n - 1); j = j + int(np.argmax(y[j:e + 1]))
    drop = y[j] - y[0]; base = np.median(y[j:])
    if drop >= 0.6 * rise and abs(int(x[j]) - int(x[0])) <= 0.5 * drop and y[j] >= base - 0.2 * rise and j < n - 6:
        return j
    return 0


W_FOOT = 2.0


def _facts_score_foot(p, k, a, b):
    """…and a joining lam keeps its foot: the bend at the bottom of its stem where the pen turns towards the next
    letter. Its stem hangs from one point of the path; a cut right at that point gave the foot to the next letter,
    and the lam's own ink was a bare stem (experiment 23: a lam highlighted over its own ink missed the letter)."""
    v = _facts_score(p, k, a, b)
    if P._base(p["units"][k]) == "ل" and p["forms"][k] in ("init", "med"):
        asc = np.where(p["G"]["asc"][a:b])[0]
        if len(asc):
            foot = asc[0]; want = max(2, p["G"]["stroke"])
            if foot < want: v -= W_FOOT * (1 - foot / want)
    return v


VARIANTS = {"today": {}, "lump": {"_facts_score": _facts_score}, "foot": {"stem_foot": stem_foot}, "lumpfoot": {"_facts_score": _facts_score, "stem_foot": stem_foot},
            "lamfoot": {"_facts_score": _facts_score_foot, "stem_foot": stem_foot}}


def use(name):
    for k, v in ORIG.items(): setattr(P, k, v)
    for k, v in VARIANTS[name].items(): setattr(P, k, v)
