"""Build documents exactly as `inkscript native ... --vector --verify` does, in this process, with the cutter
patched (patch.py) or not, and keep the pen-path plans of chosen pages for offline study.

    ../../.venv/bin/python build.py orig|new DOC [DOC...]      -> out/build_<variant>/<doc dir>, out/plans/<variant>_<doc>.pkl

src/ is never edited: the patch is applied to the imported module (penpath) in this process only.
"""
import sys, pickle, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(HERE))
from inkscript.geometry import penpath
from inkscript import cli

TRY = REPO / "experiments/14_vs_azure/out/tryout_2026-10-05"
FIX = REPO / "tests/fixtures/0582-004-009-012"
DOCS = {"0582": dict(stem="0582-004-009-012", args=["--azure-dir", str(FIX / "azure"), "--scan-dir", str(FIX / "input"), "--frontpage-dir", str(FIX / "frontpage")], pages=[1, 2, 3, 4, 5]),
        "0618": dict(stem="0618-021-002-004", args=["--azure-dir", str(TRY / "azure")], pages=[1, 16]),
        "1036": dict(stem="1036-010-038-007", args=["--azure-dir", str(TRY / "azure")], pages=[1, 10]),
        "0772": dict(stem="0772-033-037-005", args=["--azure-dir", str(TRY / "azure")], pages=[6, 14, 16, 18, 20, 23, 25, 27])}

KEEP = []


def strip(p, word):
    G = p["G"]
    return dict(units=p["units"], forms=p["forms"], n=p["n"], cuts=list(p["cuts"]), ink_s=p["ink_s"], trunk=p["trunk"], off=p["off"],
                G=dict(W=G["W"], marks=G["marks"], dots=G["dots"], stroke=G["stroke"], thin=G["thin"], asc=G["asc"], tall=G["tall"], desc=G["desc"], deep=G["deep"], has=G["has"]),
                F=dict(lab=p["F"]["lab"].astype(np.int32)), real=p.get("real"), conn=p["conn"], base=p["base"], sc=p["sc"],
                page=word.get("page") if word else None, wbox=(word.get("x0"), word.get("y0"), word.get("x1"), word.get("y1")) if word else None,
                text=word.get("text") if word else None, verdict=penpath.verdict(p))


def main():
    variant, docs = sys.argv[1], sys.argv[2:]
    if variant == "new":
        import patch; patch.apply()
    for doc in docs:
        d = DOCS[doc]; KEEP.clear()
        from inkscript.ocr.azure import load_azure
        az = Path(d["args"][1]) / d["stem"] / f"{d['stem']}.json"
        page_of = {w["off"]: w["page"] for w in load_azure(az)[0] if w["page"] in d["pages"]}
        orig_fin = penpath.finalize

        def fin(p, word=None):
            if word is not None and word.get("off") in page_of: KEEP.append(strip(p, dict(word, page=page_of[word["off"]])))
            return orig_fin(p, word)
        penpath.finalize = fin
        out = HERE / "out" / f"build_{variant}" / doc
        cli.main(["native", *d["args"], "--out", str(out), "--only", d["stem"], "--vector", "--verify"])
        penpath.finalize = orig_fin
        (HERE / "out/plans").mkdir(parents=True, exist_ok=True)
        pickle.dump(KEEP, open(HERE / "out/plans" / f"{variant}_{doc}.pkl", "wb"))
        print(doc, "kept plans:", len(KEEP), flush=True)


if __name__ == "__main__":
    main()
