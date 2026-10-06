"""Record, for one document, every call the build makes to penpath.plan (units, blobs, line, forms) in build order,
with each piece's page and word, by running `inkscript native` in this process and stopping it right after the first
pass (before any PDF is written). The cutter can then be replayed offline, patched or not, exactly as the build
cuts: the first 1,500 pieces teach the atlas (solve), every later piece is cut against it (apply).

    ../../.venv/bin/python capture.py DOC...        -> out/cap/<doc>.pkl
"""
import sys, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "experiments/21_better_boxes"))
from inkscript.geometry import penpath
from inkscript import cli
from build import DOCS


class Stop(Exception):
    pass


def main():
    for doc in sys.argv[1:]:
        d = DOCS[doc]; rec = []
        orig_plan, orig_solve = penpath.plan, penpath.solve

        def plan(units, blobs, line, forms=None):
            rec.append(dict(units=units, blobs=blobs, line=line, forms=forms, word=blobs[0].get("word") if blobs else None))
            return None

        def solve(plans, rounds=4):
            raise Stop()
        penpath.plan, penpath.solve = plan, solve
        try:
            cli.main(["native", *d["args"], "--out", str(HERE / "out/cap_tmp" / doc), "--only", d["stem"]])
        except Stop:
            pass
        finally:
            penpath.plan, penpath.solve = orig_plan, orig_solve
        (HERE / "out/cap").mkdir(parents=True, exist_ok=True)
        pickle.dump(rec, open(HERE / "out/cap" / f"{doc}.pkl", "wb"))
        print(doc, "pieces recorded:", len(rec), flush=True)


if __name__ == "__main__":
    main()
