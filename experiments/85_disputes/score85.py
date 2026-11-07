"""Experiment 85, step 4b: new readers on experiment 81's held-out lines, scored with experiment 81's judged truths.

    experiments/81_heldout_scale/out/venv/bin/python experiments/85_disputes/score85.py NAME[=FILE] ...
        -> out/est85_heldout.json  (EST81_FOLD=1: the folded form, -> out/est85_heldout_folded.json)

Experiment 84's est84.py imported unchanged (est81's stratified estimator, the two-phase estimate for late readers,
coverage, paired differences against Azure and v3, the 2000+ buckets); only its output folder is pointed here, so
nothing in experiment 84's or 81's folders is written.  NAME=FILE: {key, NAME} readings (default out/read/image_NAME.jsonl).
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "84_display_fonts"))
import est84  # noqa: E402

if __name__ == "__main__":
    est84.OUT = HERE / "out"
    os.environ.setdefault("EST84_OUT", "est85_heldout_folded.json" if os.environ.get("EST81_FOLD") == "1"
                          else "est85_heldout.json")
    est84.main(sys.argv[1:])
