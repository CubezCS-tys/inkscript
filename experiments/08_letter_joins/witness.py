"""The document as witness for a cut.

An alignment gives each letter of a piece an image: its columns of the
main ink plus the dots inside them. If the cuts are right, every image of
"medial ب" in the document looks like the other images of medial ب, and
unlike final ن. So each letter image is compared with the mean image of
its own (letter, form) class — computed without itself — and with the
mean of every other class; a letter is confirmed when its own class is the
nearest, and a word's cuts are accepted when every letter is confirmed and
every class involved has at least three other examples. Nothing is
adopted on the alignment alone.

    python experiments/08_letter_joins/witness.py OUT/native_set <out-dir>
"""
import sys
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np, cv2
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, "src")
from align import aligned_pieces, STEM, SCAN

O = Path(sys.argv[1]); OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else None
SIZE = 24


def letter_images(units, cuts, crop, F):
    """One normalised image per letter: the ink in its column interval (main + dots), drawn on a fixed box with the baseline at 60% height."""
    W = F["W"]; H = crop.shape[0]; bounds = [0] + list(cuts) + [W]
    main = F["main"]; dots_mask = crop & ~main
    imgs = []
    for k in range(len(units)):
        # units are in reading order (right to left): unit 0 is the rightmost interval
        a, b = bounds[len(units) - 1 - k], bounds[len(units) - k]
        m = np.zeros_like(crop); m[:, a:b] = main[:, a:b] | dots_mask[:, a:b]
        ys, xs = np.where(m)
        if len(xs) == 0:
            imgs.append(None); continue
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        sub = m[y0:y1, x0:x1].astype(np.uint8) * 255
        # scale by the piece's stroke-relative height so bold titles and body type compare: height 2.5x the line's stroke band -> fixed
        scale = SIZE / max(sub.shape[0], sub.shape[1])
        rs = cv2.resize(sub, (max(1, int(sub.shape[1] * scale)), max(1, int(sub.shape[0] * scale))), interpolation=cv2.INTER_AREA)
        box = np.zeros((SIZE, SIZE), np.float32); oy = (SIZE - rs.shape[0]) // 2; ox = (SIZE - rs.shape[1]) // 2
        box[oy:oy + rs.shape[0], ox:ox + rs.shape[1]] = rs / 255.0
        imgs.append(dict(img=box, aspect=(x1 - x0) / max(1, y1 - y0), rel_top=(F["b0"] - y0) / max(1, F["stroke"]), rel_bot=(y1 - F["b1"]) / max(1, F["stroke"])))
    return imgs


def form(k, n):
    return "iso" if n == 1 else "init" if k == 0 else "fin" if k == n - 1 else "med"


# Skeleton groups: letters that share one shape and differ by dots (the
# alignment already checked the dots), and forms whose shapes coincide.
GROUPS = ["بتثنيئ", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق", "ك", "ل", "م", "هة", "و", "اأإآ", "ىي", "لا"]
def group(letter, f):
    if letter == "ي" and f == "fin": letter = "ى"
    if letter in "ىي" and f != "fin": letter = "ب"
    for g in GROUPS:
        if letter in g or letter == g: return g
    return letter


def feat(im):
    return np.concatenate([im["img"].ravel(), [im["aspect"] * 2, im["rel_top"] * 0.5, im["rel_bot"] * 0.5]])


pieces_ = aligned_pieces(O / f"{STEM}.shapes.json", SCAN)
samples = defaultdict(list)                                  # (letter, form) -> [(piece index, k, feature)]
for pi, (p, units, cuts, crop, F, flags) in enumerate(pieces_):
    for k, im in enumerate(letter_images(units, cuts, crop, F)):
        if im is None: continue
        samples[(units[k][0] if units[k][:2] not in ("لا", "لأ", "لإ", "لآ") else "لا", form(k, len(units)))].append((pi, k, feat(im)))
classes = {c: np.stack([f for _, _, f in v]) for c, v in samples.items()}
means = {c: m.mean(0) for c, m in classes.items()}
confirmed = Counter(); total = Counter(); confusions = Counter(); word_ok = {}
for c, v in samples.items():
    m = classes[c]
    for j, (pi, k, f) in enumerate(v):
        if len(v) < 4:
            word_ok.setdefault(pi, []).append(None); continue
        own = (m.sum(0) - f) / (len(v) - 1)                          # leave-one-out
        d_own = np.abs(f - own).mean()
        others = [(np.abs(f - means[o]).mean(), o) for o in means if o != c and len(samples[o]) >= 4]
        d_oth, o = min(others) if others else (1e9, None)
        ok = d_own <= d_oth or (o is not None and group(o[0], o[1]) == group(c[0], c[1]))   # a same-skeleton neighbour is no contradiction
        total[c] += 1; confirmed[c] += ok
        if not ok and o: confusions[(c, o)] += 1
        word_ok.setdefault(pi, []).append(ok)
n_conf = sum(confirmed.values()); n_tot = sum(total.values())
accepted = sum(1 for pi, oks in word_ok.items() if oks and all(o is True for o in oks) and len(oks) == len(pieces_[pi][1]))
consistent = [pi for pi, (p, units, cuts, crop, F, flags) in enumerate(pieces_) if all(all(f) for f in flags)]
# --- the document's own structural signatures: what each (letter, form) shows in this typeface, by majority
from align import observe
obs = defaultdict(list)
for pi, (p, units, cuts, crop, F, flags) in enumerate(pieces_):
    for k, o in enumerate(observe(units, F, cuts)):
        obs[(units[k][0] if units[k][:2] not in ("لا", "لأ", "لإ", "لآ") else "لا", form(k, len(units)))].append(o)
def sig(o):
    return (o["asc"] > 0.1, o["desc"] > 0.1, min(o["da"], 3), min(o["db"], 3))
majority = {c: Counter(sig(o) for o in v).most_common(1)[0] for c, v in obs.items() if len(v) >= 5}
share = {c: m[1] / len(obs[c]) for c, m in majority.items()}
learned_ok = []
for pi, (p, units, cuts, crop, F, flags) in enumerate(pieces_):
    verdicts = []
    for k, o in enumerate(observe(units, F, cuts)):
        c = (units[k][0] if units[k][:2] not in ("لا", "لأ", "لإ", "لآ") else "لا", form(k, len(units)))
        verdicts.append(None if c not in majority else sig(o) == majority[c][0])
    learned_ok.append(verdicts)
acc = [pi for pi, v in enumerate(learned_ok) if v and all(x is True for x in v)]
known = [pi for pi, v in enumerate(learned_ok) if v and all(x is not None for x in v)]
print(f"document-learned signatures ({len(majority)} letter-forms with >= 5 examples; mean majority share {100 * np.mean(list(share.values())):.0f}%): "
      f"{len(acc)} of {len(known)} fully-known words agree with every letter's usual signature ({100 * len(acc) / max(1, len(known)):.1f}%), {len(pieces_) - len(known)} words involve a rare letter-form")
lowest = sorted(share.items(), key=lambda x: x[1])[:6]; print("least stable letter-forms:", [(f"{c[0]}-{c[1]}", f"{100 * s:.0f}%", majority[c][0]) for c, s in lowest])
print(f"alignment consistent with every letter's signatures (asc/desc/dots/thin cut): {len(consistent)} of {len(pieces_)} words ({100 * len(consistent) / len(pieces_):.1f}%)")
print(f"{len(pieces_)} aligned words, {n_tot} letter images judged: {n_conf} confirmed ({100 * n_conf / max(1, n_tot):.1f}%); "
      f"words with every letter confirmed: {accepted} ({100 * accepted / len(pieces_):.1f}%)")
worst = sorted(((confirmed[c] / total[c], c, total[c]) for c in total if total[c] >= 8))[:8]
print("least confirmed classes:", [(f"{c[0]}-{c[1]}", f"{100 * r:.0f}%", n) for r, c, n in worst])
print("top confusions:", [(f"{a[0]}-{a[1]}", f"{b[0]}-{b[1]}", n) for (a, b), n in confusions.most_common(8)])
if OUT:
    tiles = []
    for pi, (p, units, cuts, crop, F, flags) in enumerate(pieces_[:400]):
        oks = word_ok.get(pi, [])
        acc = oks and all(o is True for o in oks) and len(oks) == len(units)
        if len(tiles) >= 24 or len(units) < 3: continue
        im = cv2.cvtColor((255 - crop.astype(np.uint8) * 255), cv2.COLOR_GRAY2BGR)
        for c in cuts: cv2.line(im, (c, 0), (c, im.shape[0] - 1), (0, 160, 0) if acc else (0, 0, 255), 1)
        tiles.append(cv2.copyMakeBorder(im, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(180, 180, 180)))
    h = max(t.shape[0] for t in tiles); rows = []
    for k in range(0, len(tiles), 6):
        row = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255)) for t in tiles[k:k + 6]]; rows.append(np.hstack(row))
    w = max(r.shape[1] for r in rows); rows = [cv2.copyMakeBorder(r, 0, 0, 0, w - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]
    cv2.imwrite(str(OUT / "witness.png"), np.vstack(rows))
