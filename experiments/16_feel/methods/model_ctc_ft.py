"""BEST trained feeler (2026-10-06): the joint CTC reader, then fine-tuned on the document's own train pages.

What it does. model_ctc's reader (two 1-D convs + 2-layer BiLSTM, 714k parameters, CTC over letter-forms
base+init/med/fin/iso, plus a boundary head trained on the letter cutter's cuts) is first trained on the TRAIN
pages of all four bench documents together (four typefaces, 10.9k pieces, 20 passes), then fine-tuned for 10
passes at lr 5e-4 on this document's own train pages: the shared hand first, the document's typeface second.
It reads the feeling only (model_lib.raw: pen height, ink above/below, heading, ink mass, branch excursions,
dots as taps, the cutter's geometric facts, candidate cut places) — never the picture. Reading: CTC prefix beam
search under the script's grammar; cuts: the boundary head's best frame between two letters, snapped to the
nearest candidate cut place.

Dev score (bench.py, 2026-10-06): mean per-document piece accuracy 77.0% (feel_v1 44.1%); letters 85.2%.
Per document: 0582 81.6, 0618 73.5, 1036 72.4, 0772 80.6. A second fine-tune seed: 76.8%.
Cuts within one stroke of the cutter's, on pieces read right: 71-82% (feel_v1 ~95%, but on far fewer pieces).

How to train. Nothing to do by hand: `bench.py run model_ctc_ft` trains the joint model once (~28 min, 4 CPU
threads, < 1 GB), caches it in out/models/joint_<hash>.pt, then fine-tunes per document (2-6 min each) into
out/models/ft_<doc>_<hash>.pt. Delete those files to retrain. Interpreter: out/torchenv/bin/python (CPU torch).
"""
import sys, hashlib, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import torch
from methods import model_ctc as MC
import model_lib as ML

FT = dict(epochs=10, lr=5e-4)


def learn(train):
    base = MC.learn(train, joint=True)
    doc = train[0]["doc"]; cfg = dict(MC.CFG, **MC.JOINT_CFG)
    tag = hashlib.md5(json.dumps([cfg, FT], sort_keys=True).encode()).hexdigest()[:8]
    path = MC.MODELS / f"ft_{doc}_{tag}.pt"
    if path.exists():
        base.load_state_dict(torch.load(path)); base.eval(); return base
    items = ML.from_records(train)
    m = ML.train(items, base.vocab, model=base, log=MC._log, **dict(cfg, **FT))
    torch.save(m.state_dict(), path)
    return m


read = MC.read
