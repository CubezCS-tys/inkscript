"""Growth-curve point: model_scale with 0 extra books (+ the 4 bench books' train pages), 12k steps, then fine-tuned."""
from methods.model_scale import make, read  # noqa: F401
learn = make(0, dict(steps=12000))
