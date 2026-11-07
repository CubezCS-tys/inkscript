"""Experiment 77, step 4a: v2's labels from Gemini's verdicts -> out/labels_v2.jsonl (key -> label, null = drop).

Rules (lines where v1 and Azure disagree in letters/words, punctuation ignored, and not only in the order of a
left-to-right run):
  judged "azure" or "both"  keep Azure's label;
  judged "v1"               v1's reading becomes the label;
  judged "neither"          Gemini's reading becomes the label when it is close to one of the two readings
                            (letters/words distance <= max(3, 15% of the line)), else the line is dropped;
  judged "unreadable"       dropped;
  not judged                dropped (on judged disputes Azure was right only about a quarter of the time).
Every other line keeps Azure's label (as in v1).
"""
from __future__ import annotations

import glob
import json
from collections import Counter

from rapidfuzz.distance import Levenshtein

from common77 import OUT, POLICIES_NP, clean_label, to_visual

NP = POLICIES_NP["no_punct"]


def main():
    M = {}
    for f in glob.glob(str(OUT / "shards/manifest-train-*.jsonl")):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            M[d["key"]] = d["label"]
    P = {d["key"]: d["pred"] for d in map(json.loads, open(OUT / "pred/train_v1.jsonl", encoding="utf-8"))}
    A = {d["key"]: d for d in map(json.loads, open(OUT / "judge/answers.jsonl", encoding="utf-8"))}
    st = Counter()
    out = {}
    for k, lab in M.items():
        v = P.get(k, "")
        if NP(v) == NP(lab) or to_visual(v) == to_visual(lab):
            continue
        st["disputes"] += 1
        a = A.get(k)
        if a is None:
            out[k] = None
            st["unjudged_dropped"] += 1
            continue
        w = a["winner"]
        st[f"judged_{w}"] += 1
        if w in ("azure", "both"):
            continue
        if w == "v1":
            out[k] = clean_label(v)
        elif w == "neither":
            g = clean_label(a.get("reading") or "")
            d = min(Levenshtein.distance(NP(g), NP(lab)), Levenshtein.distance(NP(g), NP(v)))
            if g and d <= max(3, 0.15 * len(NP(lab))):
                out[k] = g
                st["neither_gemini_reading_used"] += 1
            else:
                out[k] = None
                st["neither_dropped_far"] += 1
        else:
            out[k] = None
    st["lines"] = len(M)
    st["replaced"] = sum(1 for v in out.values() if v is not None)
    st["dropped"] = sum(1 for v in out.values() if v is None)
    with open(OUT / "labels_v2.jsonl", "w", encoding="utf-8") as f:
        for k, v in out.items():
            f.write(json.dumps(dict(key=k, label=v), ensure_ascii=False) + "\n")
    (OUT / "labels_v2_stats.json").write_text(json.dumps(dict(st), indent=1))
    print(json.dumps(dict(st), indent=1))


if __name__ == "__main__" and len(__import__("sys").argv) == 1:
    main()


def old80():
    """v2b: v2's labels, plus experiment 80's old print (Azure's labels) with every v1-vs-Azure dispute dropped
    (the same rule as an unjudged dispute; none of these were judged)."""
    st = Counter()
    rows = [l for l in open(OUT / "labels_v2.jsonl", encoding="utf-8")]
    M = {}
    for f in glob.glob(str(OUT / "shards/manifest-old80-*.jsonl")):
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            M[d["key"]] = d["label"]
    for d in map(json.loads, open(OUT / "pred/old80_v1.jsonl", encoding="utf-8")):
        lab, v = M[d["key"]], d["pred"]
        st["lines"] += 1
        if NP(v) == NP(lab) or to_visual(v) == to_visual(lab):
            st["agree"] += 1
            continue
        st["disputes_dropped"] += 1
        rows.append(json.dumps(dict(key=d["key"], label=None)) + "\n")
    with open(OUT / "labels_v2b.jsonl", "w", encoding="utf-8") as f:
        f.writelines(rows)
    (OUT / "labels_v2b_old80_stats.json").write_text(json.dumps(dict(st), indent=1))
    print(dict(st))


if __name__ == "__main__" and len(__import__("sys").argv) > 1 and __import__("sys").argv[1] == "old80":
    old80()
