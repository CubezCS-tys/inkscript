"""Pictures for the report (out/rep/*.png): stacked words before/after, one piece explained, font glyph pairs."""
import sys, json, pickle
from common import *
import font25 as F
OUT = HERE / "out/rep"; OUT.mkdir(parents=True, exist_ok=True)
W = words()
# a paler, theme-neutral palette for the report (reading order)
PAL = [(214, 120, 40), (60, 150, 60), (60, 60, 210), (170, 150, 0), (170, 60, 170), (0, 140, 200), (120, 120, 120)]


def draw(p, sc=6, path=True):
    ink = p["ink_s"]; H, Wd = ink.shape; img = np.full((H, Wd, 3), 255, np.uint8)
    for k, (a, b) in enumerate(P.intervals(p)): img[P._mask(p, a, b, owner=k) > 0] = PAL[k % len(PAL)]
    img = cv2.resize(img, (Wd * sc, H * sc), interpolation=cv2.INTER_NEAREST)
    if path:
        pts = np.array([(x * sc + sc // 2, y * sc + sc // 2) for y, x in p["trunk"]], np.int32)
        cv2.polylines(img, [pts], False, (30, 30, 30), max(1, sc // 3))
        for c in p["cuts"]: y, x = p["trunk"][c]; cv2.circle(img, (x * sc + sc // 2, y * sc + sc // 2), sc, (0, 0, 0), -1); cv2.circle(img, (x * sc + sc // 2, y * sc + sc // 2), sc - 2, (255, 255, 255), -1)
    return cv2.copyMakeBorder(img, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255))


def piece(wid, variant, units=None):
    s, w = W[wid]
    for k, (idx, p) in match(w, variant).items():
        if units is None or "".join(p["units"]) == units: return p


WORDS = [("0772-27-16-0", "لو"), ("0772-16-13-6", "جنو"), ("0772-23-7-6", "تو"), ("0772-16-8-4", "هو"), ("1036-10-3-0", "طو"),
         ("0772-14-51-11", "لقو"), ("0772-18-6-8", "خلق"), ("0772-20-45-4", "بتطو"), ("0772-23-3-0", "مليو"), ("0772-20-52-3", "لمئو")]
STILL = [("0772-18-12-1", "مسئو"), ("0618-16-9-15", None), ("0772-27-2-2", "بق")]
meta = {"pairs": [], "still": []}
for wid, u in WORDS + STILL:
    a, b = piece(wid, "today", u), piece(wid, "lumpfoot", u)
    if a is None or b is None: print("missing", wid, u); continue
    name = f"{wid}_{''.join(a['units'])}"
    cv2.imwrite(str(OUT / f"b_{wid}.png"), draw(a)); cv2.imwrite(str(OUT / f"a_{wid}.png"), draw(b))
    (meta["pairs"] if (wid, u) in WORDS else meta["still"]).append(dict(wid=wid, text=W[wid][1]["text"], piece="".join(a["units"]), letters=a["units"]))
# one piece explained: هو, today, with the head's root marked
import patch25
p = piece("0772-16-8-4", "today"); q = piece("0772-16-8-4", "lumpfoot")
for tag, pp in (("b", p), ("a", q)):
    img = draw(pp, 10); L = patch25.lumps(dict(pp, lumps=None) if False else {k: v for k, v in pp.items() if k != "lumps"})
    for s in L:
        y, x = pp["trunk"][s]; cv2.circle(img, (x * 10 + 13, y * 10 + 13), 16, (0, 0, 230), 3)
    cv2.imwrite(str(OUT / f"explain_{tag}.png"), img)
meta["explain_lumps"] = patch25.lumps({k: v for k, v in p.items() if k != "lumps"}); meta["explain_cuts"] = [p["cuts"], q["cuts"]]
# font glyph pairs
VERDICT = {"0772": {("و", "fin"): "better", ("ق", "fin"): "better", ("ل", "med"): "better", ("ط", "init"): "better", ("ئ", "med"): "better"},
           "0582": {("ق", "fin"): "better", ("ج", "med"): "better"},
           "1036": {("و", "fin"): "better", ("ض", "fin"): "better", ("ط", "med"): "better", ("ل", "fin"): "worse"}}
meta["font"] = {}
for doc in ("0582", "0772", "1036"):
    A = pickle.load(open(HERE / f"out/font/today_{doc}.pkl", "rb")); B = pickle.load(open(HERE / f"out/font/lumpfoot_{doc}.pkl", "rb")); rows = []
    for kk in sorted(set(A) & set(B), key=lambda kk: (F.ORDER.find(kk[0][-1]) if kk[0][-1] in F.ORDER else 99, kk[0], F.FORMS.index(kk[1]))):
        v = F.iou(A[kk], B[kk])
        if v >= 0.85: continue
        n = f"f_{doc}_{ord(kk[0][0]):04x}_{kk[1]}"
        cv2.imwrite(str(OUT / f"{n}_b.png"), F.tile(A[kk], 180)); cv2.imwrite(str(OUT / f"{n}_a.png"), F.tile(B[kk], 180))
        rows.append(dict(letter=kk[0], form=kk[1], iou=round(v, 2), img=n, verdict=VERDICT[doc].get(kk, "same")))
    meta["font"][doc] = dict(forms=len(A), changed=rows)
json.dump(meta, open(OUT / "meta.json", "w"), ensure_ascii=False, indent=1); print("ok", len(meta["pairs"]), len(meta["still"]))
