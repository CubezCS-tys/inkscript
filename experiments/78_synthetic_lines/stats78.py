"""Experiment 78: geometry of line crops (real or synthetic), to match the synthetic lines to experiment 77's crops.

    python stats78.py SHARD_GLOB [N]   -> JSON: ink top/bottom rows, darkest row (baseline), pixels per character,
                                          background and ink grey levels (medians and quartiles)
"""
import glob, io, json, sys, tarfile
import numpy as np, cv2


def crops(pattern, n):
    out = []
    for f in sorted(glob.glob(pattern)):
        with tarfile.open(f) as t:
            lab = {}
            imgs = {}
            for m in t:
                k, ext = m.name.rsplit(".", 1)
                b = t.extractfile(m).read()
                if ext == "jpg":
                    imgs[k] = cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_GRAYSCALE)
                else:
                    lab[k] = b.decode()
                if len(imgs) >= n and len(lab) >= n:
                    break
            for k in imgs:
                if k in lab:
                    out.append((imgs[k], lab[k]))
        if len(out) >= n:
            break
    return out[:n]


def stats(items):
    top, bot, base, ppc, bg, ink, hgt = [], [], [], [], [], [], []
    for img, lab in items:
        _, b = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        prof = (b > 0).mean(1)
        rows = np.where(prof > 0.01)[0]
        if len(rows) == 0 or not lab:
            continue
        top.append(rows[0]); bot.append(rows[-1]); base.append(int(prof.argmax()))
        ppc.append(img.shape[1] / max(1, len(lab)))
        bg.append(np.percentile(img, 90)); ink.append(np.percentile(img, 3))
    q = lambda a: [round(float(x), 1) for x in np.percentile(a, [25, 50, 75])]
    return dict(n=len(top), ink_top=q(top), ink_bottom=q(bot), darkest_row=q(base), px_per_char=q(ppc),
                paper_p90=q(bg), ink_p3=q(ink))


if __name__ == "__main__":
    print(json.dumps(stats(crops(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2000))))
