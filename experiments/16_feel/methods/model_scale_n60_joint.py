"""Growth-curve point, joint step only (no fine-tune): model_scale with 60 extra books, 12k steps."""
from methods.model_scale import make, read  # noqa: F401
learn = make(60, dict(steps=12000), finetune=False)
