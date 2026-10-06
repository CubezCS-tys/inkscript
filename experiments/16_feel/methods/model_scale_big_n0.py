"""Control for model_scale_big: the same wider reader (h192, conv128, batches of 64) on the 4 bench books' train
pages only (0 extra books), 7k steps (~42 passes; half model_scale_big's steps, for time), then the 10-pass fine-tune."""
from methods.model_scale import make, read  # noqa: F401
learn = make(0, dict(steps=7000, h=192, conv=128, bs=64), dict(bs=32))
