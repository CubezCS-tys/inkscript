"""model_scale grown a little: all 93 extra books + the 4 bench books' train pages, a wider reader (LSTM 192 per
direction, convs 128; ~1.5M parameters), 14k steps of 64 pieces; then the 10-pass fine-tune per bench book
(batches of 32, lr 5e-4, as model_ctc_ft)."""
from methods.model_scale import make, read  # noqa: F401
CFG = dict(steps=14000, h=192, conv=128, bs=64)
learn = make(93, CFG, dict(bs=32))
