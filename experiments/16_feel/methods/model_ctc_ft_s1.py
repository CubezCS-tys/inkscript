"""model_ctc_ft with the fine-tuning pass seeded 1 (same joint model): run-to-run variation of the fine-tune."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from methods import model_ctc_ft as FT

FT.FT = dict(FT.FT, seed=1)
learn, read = FT.learn, FT.read
