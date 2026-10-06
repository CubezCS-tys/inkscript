"""Build documents exactly as `inkscript native ... --vector --verify` (cli.main in this process) with the cutter
patched (patch25 variant) — src/ is never edited.   ../../.venv/bin/python build25.py VARIANT DOC...  -> out/build_<variant>/<doc>"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO / "experiments/21_better_boxes"))
from inkscript import cli
from build import DOCS
import patch25

if __name__ == "__main__":
    variant = sys.argv[1]; patch25.use(variant)
    for doc in sys.argv[2:]:
        d = DOCS[doc]
        cli.main(["native", *d["args"], "--out", str(HERE / "out" / f"build_{variant}" / doc), "--only", d["stem"], "--vector", "--verify"])
        print("built", doc, flush=True)
