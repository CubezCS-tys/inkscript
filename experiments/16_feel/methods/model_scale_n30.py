"""Growth-curve point: model_scale with 30 extra books (+ the 4 bench books' train pages), 12k steps, then fine-tuned."""
from methods.model_scale import make, read  # noqa: F401
learn = make(30, dict(steps=12000))
