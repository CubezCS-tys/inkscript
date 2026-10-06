"""model_scale_n93 with a 20-pass fine-tune instead of 10."""
from methods.model_scale import make, read  # noqa: F401
learn = make(93, dict(steps=12000), dict(epochs=20))
