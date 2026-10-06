"""model_ctc_doc with another seed (1): run-to-run variation of the per-document training."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from methods import model_ctc as MC


def learn(train): return MC.learn(train, joint=False, cfg=dict(seed=1))


read = MC.read
