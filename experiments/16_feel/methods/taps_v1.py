"""Taps felt by size, no word prior (experiment 16, taps direction).

feel_v1, except the taps: each letter-form's dots are felt as the dot-INK mass tapped above and below its stretch,
in units of the document's own single dot, scored by a likelihood learned per letter-form on the train pages
(`taps_lib.Taps`) instead of |count - usual count|. A merged two-dot blob now says "two", not "one".
Also caches the stretch's feeling across letter-forms (same result, faster).
"""
import taps_lib as T

TAP_W = 0.5                            # chosen on held-out TRAIN pages (0582 p3, 1036 p6) from {0.5, 1, 2}


def learn(train):
    unit = T.doc_unit(train)
    return dict(mem=T.learn_memory(train, T.Memory(unit, TAP_W)))


def read(model, r):
    q = r["q"]; f = T.FE.feeling(q, r["rise"])
    ks, cuts, _, _ = T.chain(q, f, model["mem"], r["rise"])
    q.pop("_sv", None)
    return [k[0] for k in ks], cuts
