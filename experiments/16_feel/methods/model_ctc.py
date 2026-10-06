"""A trained feeler: the whole piece's feeling read by a small conv + BiLSTM with CTC (online-handwriting style).

What it does. Each piece's feeling (model_lib.raw: the pen's height, ink above/below, heading, ink mass, the
stick's excursions up each branch, the dots as taps, the cutter's geometric facts, candidate cut places) is laid
out in reading order at 20 frames per rise. A 2-layer BiLSTM over two 1-D convolutions emits, per frame, a
letter-form (base + init/med/fin/iso) or blank (CTC); a second head, trained on the letter cutter's cuts of the
train pages, scores each frame as a boundary. Reading: CTC prefix beam search constrained to the script's
grammar; cuts: between consecutive letters' emission frames, the frame most likely to be a boundary, snapped to
the nearest candidate cut place.

Training. JOINT = True (default here): one model on the TRAIN pages of all four bench documents together (four
typefaces), cached in out/models/ and reused for every document; JOINT = False: one model per document.
"""
import sys, hashlib, json
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(HERE))
import torch
import model_lib as ML

JOINT = True
CFG = dict(rate=20, epochs=40, seed=0, bs=32, lr=2e-3, cut_w=0.5, h=128, conv=96, layers=2, drop=0.2, stretch=0.15)
JOINT_CFG = dict(epochs=20)          # four times the data: half the passes
DOCS = ("0582", "0618", "1036", "0772")
MODELS = HERE / "out" / "models"


def _log(s): print("   ", s, flush=True)


def learn(train, joint=None, cfg=None):
    joint = JOINT if joint is None else joint; cfg = dict(CFG, **(JOINT_CFG if joint else {}), **(cfg or {}))
    doc = train[0]["doc"]
    tag = hashlib.md5(json.dumps([joint, cfg], sort_keys=True).encode()).hexdigest()[:8]
    MODELS.mkdir(parents=True, exist_ok=True)
    path = MODELS / (f"joint_{tag}.pt" if joint else f"{doc}_{tag}.pt")
    items = [it for d in DOCS for it in ML.doc_train_raw(d)] if joint else ML.from_records(train)
    vocab = ML.vocab_of(items)
    if path.exists():
        m = ML.Reader(len(vocab), h=cfg["h"], conv=cfg["conv"], layers=cfg["layers"], drop=cfg["drop"])
        m.load_state_dict(torch.load(path)); m.eval(); m.vocab = vocab; m.rate = cfg["rate"]
        _log(f"loaded {path.name}")
    else:
        m = ML.train(items, vocab, log=_log, **cfg)
        torch.save(m.state_dict(), path)
        _log(f"trained {path.name}: {sum(p.numel() for p in m.parameters())} parameters, {len(items)} pieces")
    return m


def read(m, r):
    x = ML.raw(r)
    seq, cuts = ML.decode(m, x, r["rise"], r["q"]["cand"], r["q"]["G"]["W"])
    return [k[0] for k in seq], cuts
