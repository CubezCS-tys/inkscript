"""The feeler with stretch-tolerant matching and a neighbourhood rule (experiment 16, direction "warp").

Same feeling, same remembered letters, same chain search and the same three cost constants as feel.py
(feel_v1); three changes in how a stretch of the path is compared with remembered letters (warp_lib.py):

1. Remember every letter the cutter cut on the train pages, not 40 per letter-form (cap 1000 is never reached).
2. The stick's walk (height, heading; 16 samples) is compared by dynamic time warping in a Sakoe-Chiba band of
   2 samples (the trunk outline, 8 pooled bins, keeps the even comparison: warping it did nothing). DTW is
   computed only on the 64 examples nearest by the even distance; it is never larger than the even distance.
3. A letter-form's cost is the mean distance of its 3 nearest examples, and it may compete for a stretch only if
   those 3 are among the 16 examples nearest to the stretch over all letters of that position-form (a k-nearest
   neighbour vote): one lucky example of a scattered letter no longer outbids a letter whose examples crowd round
   the stretch. If no letter qualifies, every letter competes.

Dev (2026-10-06, `bench.py run warp_gate`): mean per-document piece accuracy 53.8% against feel_v1's 43.9%;
see notes/warp.md for per-document numbers and the ablations. Tuned on dev: the gate (16), the walk band (2),
k = 3 nearest. About 30-120 s per document, < 0.5 GB.
"""
import warp_lib as WL
import feel as FE

CFG = dict(band=0, wband=2, knn=3, gate=16, short=64)


def learn(train):
    return WL.Feeler(WL.learn_memory(train, cap=1000), **CFG)


def read(fe, r):
    q = r["q"]; f = FE.feeling(q, r["rise"]); seq, cuts = fe.read(q, f, r["rise"])
    return [k[0] for k in seq], cuts
