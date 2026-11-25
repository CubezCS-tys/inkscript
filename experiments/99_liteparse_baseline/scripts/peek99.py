"""Print the headline numbers of out/scores/liteparse_scorecard.json (a quick look; the full table is the .md)."""
import json
d = json.load(open("/home/appuser/inkscript/experiments/99_liteparse_baseline/out/scores/liteparse_scorecard.json"))
for m in d["modes"]:
    s = d["structure"][m]; P = s["PAGE"]
    print("==", m, "P1", P["P1"]["accuracy"], "restr", P["P1_restricted"]["accuracy"], "noblock", P["lines_in_no_block"],
          "P2", P["P2"]["f1"], "P3", {k: (v["pairs"], v["share"]) for k, v in P["P3"].items()})
    print("  conf", list(P["P1"]["confusion"].items())[:8])
    T = s["TAB"]; print("  TAB found", T.get("P7.found"), "shape", T.get("P7.shape"), "cells", {k: T.get("P7.cells", {}).get(k) for k in ("n", "exact", "folded")})
    print("  REFS", s["REFS"].get("P9.boundaries"), " para", s["REFS_para"].get("P9.boundaries"))
    print("  cost", d["cost"].get(m))
R = d["R1"]
for w in ["witness_azure", "witness_t91"] + d["modes"]:
    x = R.get(w)
    if not x:
        continue
    if "as_returned" in x:
        print(w, {k: (v["letter_error"], v["word_error"], v["lines"]) for k, v in x["as_returned"].items()},
              "\n   rtl", {k: (v["letter_error"], v["word_error"]) for k, v in x["items_reordered_right_to_left"].items()}, "\n   order", x["order"], "empty", x["empty_lines"])
    else:
        print(w, {k: (v["letter_error"], v["word_error"], v["lines"]) for k, v in x.items()})
print({k: v["n_network"] for k, v in d.get("network", {}).items()})
