"""The CTC reader trained on many books (scale_lib), then fine-tuned on each bench book's train pages.

Same reader, features, decoder and fine-tune as model_ctc_ft; the joint step sees N_BOOKS extra scanned books
(random corpus documents, one per journal, up to 8 upright pages each; scale_lib.extracted() order) besides the
four bench books' TRAIN pages, for a fixed number of optimiser steps. Never a bench dev or test page.
Curve variants (model_scale_nXX.py) only change N_BOOKS / CFG. Run with out/torchenv/bin/python.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scale_lib as S
from methods import model_ctc as MC

N_BOOKS = 93                                     # the best (2026-10-06): = model_scale_big
CFG = dict(steps=14000, h=192, conv=128, bs=64)
FT = dict(bs=32)
FINETUNE = True


def make(n_books, cfg=None, ft=None, finetune=True):
    def learn(train):
        if not finetune: return S.joint(n_books, cfg, log=MC._log)
        return S.finetune(n_books, train, cfg, ft, log=MC._log)
    return learn


def learn(train):
    return make(N_BOOKS, CFG, FT, FINETUNE)(train)


read = MC.read
