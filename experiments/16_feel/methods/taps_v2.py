"""taps_v1 + the loose parts a bridged piece lost (a hamza over or under an alef), felt again as taps; no prior.

When a piece's ink falls apart (an alef and its hamza), the cutter BRIDGES it into one body, and the hamza is no
longer a mark: it is felt only as a slightly taller alef, so ا/أ/إ were the commonest tap confusion left after
taps_v1. Here every loose part of the original ink is a tap again (`taps_lib.dot_marks`, kind "b"), and each
side's tap cell also says whether such a part sits there; learned per letter-form like the dots.
"""
import taps_lib as T

TAP_W = 0.5                                            # as taps_v1 (chosen on held-out train pages)


def learn(train):
    return dict(mem=T.learn_memory(train, T.Memory(T.doc_unit(train), TAP_W, bridged=True)))


def read(model, r):
    q = r["q"]; f = T.FE.feeling(q, r["rise"])
    ks, cuts, _, _ = T.chain(q, f, model["mem"], r["rise"])
    q.pop("_sv", None)
    return [k[0] for k in ks], cuts
