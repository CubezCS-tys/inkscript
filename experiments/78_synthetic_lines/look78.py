"""Experiment 78: contact sheets, synthetic beside real (experiment 77's crops), for looking.

    python look78.py REAL_SHARD_GLOB SYN_SHEET.png OUT.png [N]
Two columns of N/2 rows each side: left = synthetic, right = real (random, seed 78); a second file OUT_mixed.png
interleaves them unlabelled (the key in OUT_mixed.key.txt) for a blind look.
"""
import glob, random, sys, tarfile
import cv2, numpy as np

pat, syn, out = sys.argv[1], sys.argv[2], sys.argv[3]
n = int(sys.argv[4]) if len(sys.argv) > 4 else 100
rng = random.Random(78)
fs = sorted(glob.glob(pat))
real = []
for f in rng.sample(fs, min(len(fs), 10)):
    with tarfile.open(f) as t:
        ms = [m for m in t.getmembers() if m.name.endswith(".jpg")]
        for m in rng.sample(ms, min(len(ms), n // 10 + 1)):
            real.append(cv2.imdecode(np.frombuffer(t.extractfile(m).read(), np.uint8), cv2.IMREAD_GRAYSCALE))
real = real[:n]
S = cv2.imread(syn, cv2.IMREAD_GRAYSCALE)
synl = [S[48 * k:48 * k + 48] for k in range(S.shape[0] // 48)][:n]
W = 1100
def strip(c):
    c = c[:, -W:] if c.shape[1] > W else c
    o = np.full((48, W), 255, np.uint8); o[:, W - c.shape[1]:] = c; return o
def trim(c):  # synthetic sheet rows are right-aligned in 1400 px: drop the white left part
    cols = np.where((c < 250).any(0))[0]
    return c[:, max(0, cols[0] - 5):] if len(cols) else c
synl = [trim(c) for c in synl]
rows = []
for k in range(min(len(real), len(synl)) // 2):
    rows.append(np.hstack([strip(synl[k]), np.full((48, 20), 0, np.uint8), strip(real[k])]))
cv2.imwrite(out, np.vstack(rows))
mix = [(c, "syn") for c in synl[:n // 2]] + [(c, "real") for c in real[:n // 2]]
rng.shuffle(mix)
rows = [np.hstack([strip(mix[2 * k][0]), np.full((48, 20), 0, np.uint8), strip(mix[2 * k + 1][0])]) for k in range(len(mix) // 2)]
cv2.imwrite(out.replace(".png", "_mixed.png"), np.vstack(rows))
open(out.replace(".png", "_mixed.key.txt"), "w").write("\n".join(f"{k}: {mix[2*k][1]} | {mix[2*k+1][1]}" for k in range(len(mix) // 2)))
