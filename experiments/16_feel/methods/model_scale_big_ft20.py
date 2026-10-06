"""model_scale_big with a 20-pass fine-tune per bench book (batches of 32, lr 5e-4)."""
from methods.model_scale import make, read  # noqa: F401
learn = make(93, dict(steps=14000, h=192, conv=128, bs=64), dict(bs=32, epochs=20))
