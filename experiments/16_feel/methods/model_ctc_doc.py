"""model_ctc trained per document (its own train pages only). See model_ctc for the method."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from methods import model_ctc as MC


def learn(train): return MC.learn(train, joint=False)


read = MC.read
