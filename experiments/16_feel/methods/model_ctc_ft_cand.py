"""model_ctc_ft, with cuts chosen among the candidate cut places between two letters (the one the boundary head
likes best) instead of the best boundary frame snapped to the nearest candidate. Same models, same reading."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from methods import model_ctc_ft as FT
import model_lib as ML

learn = FT.learn


def read(m, r):
    seq, cuts = ML.decode(m, ML.raw(r), r["rise"], r["q"]["cand"], r["q"]["G"]["W"], cut_mode="cand")
    return [k[0] for k in seq], cuts
