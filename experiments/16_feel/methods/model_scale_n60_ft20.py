"""model_scale_n60 with a longer fine-tune (20 passes instead of 10): does a more varied joint model need more of the book's own pages?"""
from methods.model_scale import make, read  # noqa: F401
learn = make(60, dict(steps=12000), dict(epochs=20))
