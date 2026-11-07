"""Experiment 83: experiment 78's eval78.py (copied 2026-11-05), itself experiment 77's eval77.py, unchanged except where
it reads and writes: the test pages are experiment 77's out/test (read only), results go to out/results83.json.

Experiment 77, step 5b: score every reader on the held-out test pages with the lab's scorer.

    python eval77.py [--pred v1=out/pred/test_v1.jsonl --pred v2=out/pred/test_v2.jsonl ...]

Readers on Azure's lines (the same line boxes for all): azure, argon (Azure + Argon's fixes; Azure's text where Argon
gives none), and every --pred file (our models).  Nuqta (experiment 75's existing runs, docs 1-3 only; not re-run) is
scored on its own page text.

Page text of a line reader = its lines in the TRUTH's order (yardstick: the gold's own map from its lines to Azure's;
lab docs: each Azure line placed where its text is found in the truth), so the reading order effect is the same for
every line reader and is not what is measured.  Measures (experiment 75 labocr/evaluation.py, imported):
  letters = CER under `no_punct` (punctuation removed; marks, hamza, ى/ي, digits count);
  words   = order-free word error under `no_punct` (1 - F1 of the word multisets);
  shown apart: CER and words under `faithful` (punctuation counts) and the printed-space-before-punctuation count.
Doc 3 has no truth: disagreement with Argon only.  Writes out/results77.json and out/confusions77.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
OUT77 = E / "77_scratch_reader/out"
sys.path.insert(0, str(OUT77.parent))
from common77 import clean_label  # noqa: E402

sys.path.insert(0, str(E / "75_ocr_lab"))
from labocr.evaluation import POLICIES, recognition  # noqa: E402

RUNS = E / "75_ocr_lab/out/data/runs"
NUQTA = {"nuqta_as_written": {"doc1": "run_nuqta_as_written_4654bb663e", "doc2": "run_nuqta_as_written_054cae37e1",
                              "doc3": "run_nuqta_as_written_065471645a"},
         "nuqta_markdown": {"doc1": "run_nuqta_markdown_26064247d0", "doc2": "run_nuqta_markdown_3413be7247",
                            "doc3": "run_nuqta_markdown_speedfix_d6d1cf701d"}}
SPACE_PUNCT = re.compile(r"\s[،.؛:؟!)»]|[(«]\s")


def nuqta_text(run: str, page_id: str) -> str | None:
    f = RUNS / run / "pred" / f"{page_id}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    bl = sorted(d["result"]["blocks"], key=lambda b: (b.get("order") is None, b.get("order") or 0))
    return "\n".join(b["raw_text"] for b in bl if (b.get("raw_text") or "").strip())


def order_lines(rec: dict) -> list[int]:
    """Azure line numbers in the truth's order (only lines that belong to the truth for the yardstick)."""
    if rec["set"] == "yardstick":
        gp = {int(k): v for k, v in rec["gold_pos"].items()}
        return sorted(gp, key=lambda i: gp[i])
    if rec.get("truth"):
        T = POLICIES["faithful"]("\n".join(rec["truth"]))
        pos = {}
        for r in rec["lines"]:
            t = POLICIES["faithful"](r["azure"])
            al = fuzz.partial_ratio_alignment(t, T) if t else None
            pos[r["i"]] = (al.dest_start if al and al.score >= 60 else 10 ** 6 + r["i"])
        return sorted(pos, key=lambda i: pos[i])
    return [r["i"] for r in rec["lines"]]


def reader_lines(rec: dict, preds: dict[str, dict]) -> dict[str, dict[int, str]]:
    out = {"azure": {}, "argon": {}}
    for r in rec["lines"]:
        out["azure"][r["i"]] = clean_label(r["azure"])
        out["argon"][r["i"]] = clean_label(r["argon"] if r.get("argon") is not None else r["azure"])
        for name, P in preds.items():
            out.setdefault(name, {})[r["i"]] = clean_label(P.get(r["key"], {}).get("pred", ""))
    if not rec.get("argon_available"):
        out.pop("argon")
    return out


def score(hyp: str, ref: str) -> dict:
    r = recognition(hyp, ref)
    sp_h, sp_r = len(SPACE_PUNCT.findall(hyp)), len(SPACE_PUNCT.findall(ref))
    return dict(letters=dict(dist=r["no_punct"]["cer"]["dist"], n=r["no_punct"]["cer"]["ref_len"]),
                words=dict(err=r["no_punct"]["bag"]["errors"], n=r["no_punct"]["bag"]["total"]),
                letters_punct=dict(dist=r["faithful"]["cer"]["dist"], n=r["faithful"]["cer"]["ref_len"]),
                words_punct=dict(err=r["faithful"]["bag"]["errors"], n=r["faithful"]["bag"]["total"]),
                folded=dict(dist=r["folded"]["cer"]["dist"], n=r["folded"]["cer"]["ref_len"]),
                space_punct=dict(hyp=sp_h, ref=sp_r))


def agg(rows: list[dict]) -> dict:
    s = defaultdict(lambda: [0, 0])
    sp = [0, 0]
    for r in rows:
        for k in ("letters", "letters_punct", "folded"):
            s[k][0] += r[k]["dist"]
            s[k][1] += r[k]["n"]
        for k in ("words", "words_punct"):
            s[k][0] += r[k]["err"]
            s[k][1] += r[k]["n"]
        sp[0] += r["space_punct"]["hyp"]
        sp[1] += r["space_punct"]["ref"]
    out = {k: round(100 * v[0] / v[1], 2) if v[1] else None for k, v in s.items()}
    out["word_errors_approx"] = round(s["words"][0] / 2)
    out["space_before_punct"] = dict(reader=sp[0], truth=sp[1])
    out["pages"] = len(rows)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", action="append", default=[])
    ap.add_argument("--out", default=str(OUT / "results83.json"))
    a = ap.parse_args()
    preds = {}
    for p in a.pred:
        name, f = p.split("=", 1)
        preds[name] = {d["key"]: d for d in map(json.loads, open(f, encoding="utf-8"))}
    pages = json.loads((OUT77 / "test/pages.json").read_text(encoding="utf-8"))
    per = defaultdict(lambda: defaultdict(list))      # set -> reader -> page rows
    page_rows = []
    line_exact = defaultdict(Counter)
    conf = defaultdict(Counter)
    conf_ex = defaultdict(dict)
    for rec in pages:
        RL = reader_lines(rec, preds)
        order = order_lines(rec)
        if rec.get("truth"):
            ref = "\n".join(rec["truth"])
            sets = ["yardstick"] if rec["set"] == "yardstick" else [f"lab_{rec['lab']}"]
            if rec["set"] == "lab" and rec["lab"] in ("doc1", "doc2"):
                sets.append("lab_docs12")
        else:
            ref = "\n".join(RL["argon"][i] for i in order)
            sets = ["doc3_vs_argon"]
        row = dict(page_id=rec["page_id"], set=rec["set"], lab=rec.get("lab"), decade=rec.get("decade"), readers={})
        for name, L in RL.items():
            if name == "argon" and sets == ["doc3_vs_argon"]:
                continue
            hyp = "\n".join(L[i] for i in order)
            sc = score(hyp, ref)
            row["readers"][name] = sc
            for s in sets:
                per[s][name].append(sc)
        if rec["set"] == "lab":
            for nn, runs in NUQTA.items():
                t = nuqta_text(runs[rec["lab"]], rec["page_id"])
                if t is not None:
                    sc = score(t, ref)
                    row["readers"][nn] = sc
                    for s in sets:
                        per[s][nn].append(sc)
        # line level (yardstick: the gold maps its lines to Azure's one to one)
        if rec["set"] == "yardstick":
            gp = {int(k): v for k, v in rec["gold_pos"].items()}
            keys = {r["i"]: r["key"] for r in rec["lines"]}
            for i, pos in gp.items():
                T = rec["truth"][pos]
                for name, L in RL.items():
                    h = L[i]
                    line_exact[name]["lines"] += 1
                    line_exact[name]["faithful"] += POLICIES["faithful"](h) == POLICIES["faithful"](T)
                    line_exact[name]["no_punct"] += POLICIES["no_punct"](h) == POLICIES["no_punct"](T)
                    if name in preds or name == "azure":
                        hf, tf = POLICIES["faithful"](h), POLICIES["faithful"](T)
                        for op in Levenshtein.editops(tf, hf):
                            x = tf[op.src_pos] if op.tag in ("replace", "delete") else "∅"
                            y = hf[op.dest_pos] if op.tag in ("replace", "insert") else "∅"
                            k = f"{x}>{y}"
                            conf[name][k] += 1
                            conf_ex[name].setdefault(k, dict(key=keys[i], truth=T, reader=h))
        page_rows.append(row)
    res = dict(sets={s: {n: agg(v) for n, v in R.items()} for s, R in per.items()},
               line_exact={n: dict(c, faithful_pct=round(100 * c["faithful"] / c["lines"], 1),
                                   no_punct_pct=round(100 * c["no_punct"] / c["lines"], 1)) for n, c in line_exact.items()},
               pages=page_rows)
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    cj = {n: [dict(pair=k, count=v, example=conf_ex[n][k]) for k, v in c.most_common(25)] for n, c in conf.items()}
    (Path(a.out).parent / (Path(a.out).stem.replace("results", "confusions") + ".json")).write_text(
        json.dumps(cj, ensure_ascii=False, indent=1), encoding="utf-8")
    for s, R in res["sets"].items():
        print(f"\n== {s}")
        print(f"{'reader':18s} {'letters':>8s} {'words':>8s} | {'let+p':>7s} {'wrd+p':>7s} {'folded':>7s} ~wrong  sp(reader/truth)")
        for n, v in sorted(R.items(), key=lambda kv: kv[1]["letters"] if kv[1]["letters"] is not None else 999):
            print(f"{n:18s} {v['letters']:8.2f} {v['words']:8.2f} | {v['letters_punct']:7.2f} {v['words_punct']:7.2f} "
                  f"{v['folded']:7.2f} {v['word_errors_approx']:6d}  {v['space_before_punct']['reader']}/{v['space_before_punct']['truth']}")
    print("\nline exact (yardstick):", {n: (v["faithful_pct"], v["no_punct_pct"]) for n, v in res["line_exact"].items()})


if __name__ == "__main__":
    main()
