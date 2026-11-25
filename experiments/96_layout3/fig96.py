"""Experiment 96, goal 3: the reader test of our line cuts (experiment 94's line finder and e2e94 rows, unchanged),
reported on all judged lines and with figure text excluded.

    python fig96.py [LAY_PRED] [LINES TAG]  -> out/fig96[TAG].json   LINES: an e2e94-style _lines.jsonl (default:
                                                                    experiment 94's e2e94_lines.jsonl)

Figure text (pre-registered): truth lines whose Argon block type is `figure` (ref94.jsonl).  Secondary (upper bound):
also every line the layout model types caption on its Azure box (LAY_PRED, default experiment 94's pred94_lay.json).
Paired difference ours - Azure in points of letters, 95% interval from experiment 92's page bootstrap (1,000).
"""
from __future__ import annotations

import json
import sys

from common96 import E, O94, OUT

sys.path.insert(0, str(E / "92_layout"))
sys.path.insert(0, str(E / "94_layout2"))
from e2e92 import boot  # noqa: E402
from score94 import lay_label  # noqa: E402


def summary(G):
    n = sum(r["n"] for r in G)
    return dict(lines=len(G), letters=n, azure_cut=round(100 * sum(r["d_az"] for r in G) / n, 3),
                our_cut=round(100 * sum(r["d_own"] for r in G) / n, 3),
                diff=round(100 * sum(r["d_own"] - r["d_az"] for r in G) / n, 3), diff_ci=boot(G, "d_az", "d_own"),
                missed=sum(r["kind"] == "missed" for r in G),
                lost_by_kind={k: round(100 * sum(r["d_own"] - r["d_az"] for r in G if r["kind"] == k) / n, 3)
                              for k in ("one", "split", "merged", "missed")})


def main(lay=None, lines=None, tag=""):
    lay = lay or str(O94 / "pred94_lay.json")
    lines = lines or str(O94 / "e2e94_lines.jsonl")
    PL = json.load(open(lay))
    typ, cap = {}, {}
    for l in open(O94 / "ref94.jsonl", encoding="utf-8"):
        r = json.loads(l)
        for x in r["lines"]:
            lk = f"{r['key']}_l{x['i']:03d}"
            typ[lk] = x["type"]
            if x["box"] and r["key"] in PL:
                cap[lk] = lay_label(PL[r["key"]], r["W"], r["H"], x["box"]) == "caption"
    rows = [json.loads(l) for l in open(lines, encoding="utf-8")]
    out = {}
    for src in ("judged", "agreed"):
        R = [r for r in rows if r["src"] == src]
        nofig = [r for r in R if typ.get(r["lk"]) != "figure"]
        nocap = [r for r in nofig if not cap.get(r["lk"])]
        out[src] = dict(all=summary(R), figure_excluded=summary(nofig), figure_and_caption_excluded=summary(nocap),
                        figure_lines=len(R) - len(nofig))
        out[src]["figure_lines_missed"] = sum(r["kind"] == "missed" for r in R if typ.get(r["lk"]) == "figure")
    out["lay_pred"], out["lines"] = lay, lines
    json.dump(out, open(OUT / f"fig96{tag}.json", "w"), indent=1)
    for src, d in out.items():
        if isinstance(d, dict):
            for k in ("all", "figure_excluded", "figure_and_caption_excluded"):
                print(src, k, d[k]["lines"], d[k]["diff"], d[k]["diff_ci"], d[k]["missed"], d[k]["lost_by_kind"])


if __name__ == "__main__":
    main(*sys.argv[1:])
