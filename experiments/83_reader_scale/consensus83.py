"""Experiment 83, step 3 (runs on the GPU host or here): consensus labels.

    python consensus83.py OUTDIR --manifest 'GLOB' ... --pred P.jsonl ... [--only HELD.jsonl] [--tag v3]

A new line is a training label when the reader's reading (P, e.g. v1's) and Azure's agree exactly under the
scorer's `no_punct` policy (experiment 77's common77.POLICIES_NP: faithful, punctuation removed, spaces collapsed;
marks, hamza, ى/ي, digits and the word spaces all count).  The label kept is Azure's own (with its punctuation).
Every other line is held aside: not trained on this round, saved for later rounds.

--only HELD.jsonl: a later round (self-training): only the lines held aside before are looked at again; the ones the
new reader now reads as Azure does become labels, the rest stay held.

Writes OUTDIR/labels_<tag>.jsonl ({key, label: null} for every line NOT to train on; the trainer keeps the tar's label
for every other key), OUTDIR/held_<tag>.jsonl (key, era, year, jcode, azure, reader, cmin) and
OUTDIR/agree_<tag>.json (agreement by era, decade and era x journal, plus the looser rate with spaces ignored).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "x/e77"))
if not os.path.exists(os.path.join(sys.path[0], "common77.py")):
    sys.path[0] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../77_scratch_reader")
from common77 import POLICIES_NP  # noqa: E402

NP = POLICIES_NP["no_punct"]


def decade(y):
    try:
        return int(str(y)[:4]) // 10 * 10
    except ValueError:
        return None


def era(y):
    d = decade(y)
    return "pre2000" if d is not None and d < 2000 else "modern"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--manifest", action="append", default=[])
    ap.add_argument("--pred", action="append", default=[])
    ap.add_argument("--only")
    ap.add_argument("--tag", default="v3")
    a = ap.parse_args()
    pred = {}
    for f in a.pred:
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            pred[d["key"]] = d
    only = None
    if a.only:
        only = {json.loads(l)["key"] for l in open(a.only, encoding="utf-8")}
    st = defaultdict(Counter)
    os.makedirs(a.outdir, exist_ok=True)
    lab_f = open(os.path.join(a.outdir, f"labels_{a.tag}.jsonl"), "w", encoding="utf-8")
    held_f = open(os.path.join(a.outdir, f"held_{a.tag}.jsonl"), "w", encoding="utf-8")
    nman = 0
    for g in a.manifest:
        for mfile in sorted(glob.glob(g)):
            for l in open(mfile, encoding="utf-8"):
                m = json.loads(l)
                nman += 1
                if only is not None and m["key"] not in only:
                    continue
                p = pred.get(m["key"])
                e, dec = m.get("era") or era(m["year"]), decade(m["year"])
                src = "old80" if ("old80" in os.path.basename(mfile) or "o80" in os.path.basename(mfile)) else "new83"
                groups = ("all", f"era:{e}", f"decade:{dec}", f"src:{src}")
                if p is None:
                    for k in groups:
                        st[k]["no_pred"] += 1
                    lab_f.write(json.dumps(dict(key=m["key"], label=None)) + "\n")
                    continue
                az, rd = NP(m["label"]), NP(p["pred"])
                ok = az == rd
                ok_ns = az.replace(" ", "") == rd.replace(" ", "")
                for k in groups:
                    st[k]["lines"] += 1
                    st[k]["agree"] += ok
                    st[k]["agree_nospace"] += ok_ns
                    st[k]["chars"] += len(az)
                    st[k]["agree_chars"] += len(az) if ok else 0
                if not ok:
                    lab_f.write(json.dumps(dict(key=m["key"], label=None)) + "\n")
                    held_f.write(json.dumps(dict(key=m["key"], era=e, year=m["year"], jcode=m["jcode"], azure=m["label"],
                                                 reader=p["pred"], cmin=p.get("cmin"), cmean=p.get("cmean")),
                                            ensure_ascii=False) + "\n")
    lab_f.close()
    held_f.close()
    out = {}
    for k, c in sorted(st.items(), key=lambda kv: str(kv[0])):
        out[k] = dict(c, agree_pct=round(100 * c["agree"] / max(1, c["lines"]), 2),
                      agree_nospace_pct=round(100 * c["agree_nospace"] / max(1, c["lines"]), 2),
                      agree_chars_pct=round(100 * c["agree_chars"] / max(1, c["chars"]), 2))
    out["_info"] = dict(manifest_lines=nman, preds=len(pred), only=len(only) if only is not None else None, tag=a.tag)
    with open(os.path.join(a.outdir, f"agree_{a.tag}.json"), "w") as f:
        json.dump(out, f, indent=1)
    for k in sorted(out):
        if k != "_info":
            v = out[k]
            print(f"{k:16s} lines {v['lines']:9d}  agree {v['agree_pct']:6.2f}%  (spaces ignored {v['agree_nospace_pct']:6.2f}%)")
    print("CONSENSUS_DONE", json.dumps(out["_info"]), flush=True)


if __name__ == "__main__":
    main()
