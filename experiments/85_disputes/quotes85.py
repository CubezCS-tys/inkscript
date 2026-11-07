"""Experiment 85: «» and (( )) on the owner's 20 pages, with experiment 84's quotes84.py imported unchanged (only its
output folder pointed here).   .venv/bin/python quotes85.py NAME=PRED.jsonl ...  -> out/quotes84.json"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "84_display_fonts"))
import quotes84  # noqa: E402

if __name__ == "__main__":
    quotes84.HERE = HERE
    quotes84.main(sys.argv[1:])
