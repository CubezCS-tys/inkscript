"""Experiment 102's scorer: letters / words wrong, and the faults that matter for stage 2 and for trust.

    python3 score102.py exam PRED.jsonl [--name NAME] [--rate USD_PER_H]   -> out/scores/exam_<NAME>.json
    python3 score102.py dev  PRED.jsonl [--name NAME]                       -> out/scores/dev_<NAME>.json
    python3 score102.py baselines                                            -> out/scores/exam_azure.json, exam_t91.json
PRED.jsonl: eval102.py's output, one {key, text, finish, out_tokens, ...} per line (several adapters may share one file:
--adapter picks one).

Reading, the exam (experiment 97's R1, 584 lines with a truth): experiment 99's r1_truth and r1_rates imported
unchanged (the construction of score97.score_r1; Azure 0.53% / t91 0.71% letters wrong folded without punctuation
through this count, 0.79% / 1.20% exact).  Headline = folded, punctuation ignored.
DEV: the line's training-style label is the truth (Azure-derived, see README "What the targets are"); the same three
modes (exact; folded = score97.r1_fold; folded + punctuation ignored).

Faults (fixed before any model output; each counted on its own, per line and per 100 truth words / 1,000 letters):
  invented   output words aligned to no truth word (word-level edit alignment, folded); a line is "invented" when it
             has 2+ such words in a row, or 30%+ more letters than the truth, and is not a loop (a loop line is counted
             as a loop only; its extra words still count in invented words per 100);
  dropped    truth words aligned to no output word; a line is "dropped" when 2+ truth words in a row are missing;
  loop       the answer stopped at the token limit (finish = length), or a word 1-4-gram repeats 3+ times in a row in
             the output but not in the truth;
  digit set  a digit replaced by the same value in another digit set (0-9 / ٠-٩ / ۰-۹), raw text;
  spelling   letter substitutions inside a spelling class, raw text with vowel marks removed: hamza on alif
             (ا أ إ آ ٱ), hamza seats (ء ؤ ئ and the bare letter), ى/ي, ة/ه, both directions (a reader that "corrects"
             spelling shows up here; so does one that misreads these pairs: the measure cannot tell them apart);
  marks      vowel marks (tashkeel) added where the truth has none at that letter, and printed marks dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "97_extraction_evals"))
sys.path.insert(0, str(E / "99_liteparse_baseline/scripts"))
OUT = HERE / "out/scores"

DIGITS = {**{chr(0x30 + i): ("ascii", i) for i in range(10)}, **{chr(0x660 + i): ("arabic", i) for i in range(10)},
          **{chr(0x6F0 + i): ("persian", i) for i in range(10)}}
CLASSES = {"alif_hamza": set("اأإآٱ"), "ya_alif_maqsura": set("يى"), "ta_marbuta_ha": set("ةه"),
           "hamza_seat_waw": set("ؤو"), "hamza_seat_ya": set("ئي"), "hamza_alone": set("ءا")}


def is_mark(ch):
    return unicodedata.category(ch) == "Mn"


def ws(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def align(a, b):
    """Levenshtein alignment of two sequences -> list of (op, x, y) with op in = sub del ins (del: in a only)."""
    n, m = len(a), len(b)
    D = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        D[i][0] = i
    for j in range(m + 1):
        D[0][j] = j
    for i in range(1, n + 1):
        ai, Di, Dp = a[i - 1], D[i], D[i - 1]
        for j in range(1, m + 1):
            Di[j] = min(Dp[j] + 1, Di[j - 1] + 1, Dp[j - 1] + (ai != b[j - 1]))
    ops, i, j = [], n, m
    while i or j:
        if i and j and D[i][j] == D[i - 1][j - 1] + (a[i - 1] != b[j - 1]):
            ops.append(("=" if a[i - 1] == b[j - 1] else "sub", a[i - 1], b[j - 1]))
            i, j = i - 1, j - 1
        elif i and D[i][j] == D[i - 1][j] + 1:
            ops.append(("del", a[i - 1], None))
            i -= 1
        else:
            ops.append(("ins", None, b[j - 1]))
            j -= 1
    return ops[::-1]


def runs(ops, kind):
    best = cur = 0
    for o in ops:
        cur = cur + 1 if o[0] == kind else 0
        best = max(best, cur)
    return best


def loop_in(text, truth):
    w = text.split()
    for n in range(1, 5):
        for i in range(0, len(w) - 3 * n + 1):
            g = w[i:i + n]
            if w[i + n:i + 2 * n] == g and w[i + 2 * n:i + 3 * n] == g:
                if " ".join(g * 3) not in truth:
                    return True
    return False


def faults(pred: str, truth: str, finish: str | None, fold) -> dict:
    """Fault counts for one line. truth/pred raw (exact) text; fold = the R1 folding for the word measures."""
    f = Counter()
    pw, tw = fold(pred).split(), fold(truth).split()
    wops = align(tw, pw)
    f["truth_words"] = len(tw)
    f["invented_words"] = sum(o[0] == "ins" for o in wops)
    f["dropped_words"] = sum(o[0] == "del" for o in wops)
    lt, lp = len(fold(truth).replace(" ", "")), len(fold(pred).replace(" ", ""))
    f["line_loop"] = int(finish == "length" or loop_in(ws(pred), ws(truth)))
    f["line_invented"] = int((runs(wops, "ins") >= 2 or (lt > 0 and lp >= 1.3 * lt)) and not f["line_loop"])
    f["line_dropped"] = int(runs(wops, "del") >= 2)
    # raw character alignment for digits / spelling / marks
    t, p = unicodedata.normalize("NFC", ws(truth)), unicodedata.normalize("NFC", ws(pred))
    f["truth_letters"] = sum(1 for ch in t if not ch.isspace())
    cops = align(t, p)
    for op, x, y in cops:
        if op == "sub" and x in DIGITS and y in DIGITS and DIGITS[x][1] == DIGITS[y][1] and DIGITS[x][0] != DIGITS[y][0]:
            f["digit_set_changed"] += 1
        if op == "ins" and y and is_mark(y):
            f["marks_added"] += 1
        if op == "del" and x and is_mark(x):
            f["marks_dropped"] += 1
        if op == "sub" and is_mark(x) and is_mark(y):
            f["marks_changed"] += 1
    f["line_digit_set"] = int(f["digit_set_changed"] > 0)
    t2 = "".join(ch for ch in t if not is_mark(ch))
    p2 = "".join(ch for ch in p if not is_mark(ch))
    for op, x, y in align(t2, p2):
        if op == "sub":
            for name, cl in CLASSES.items():
                if x in cl and y in cl:
                    f[f"spelling_{name}"] += 1
                    f["spelling_all"] += 1
                    break
    f["line_spelling"] = int(f["spelling_all"] > 0)
    f["line_marks_added"] = int(f["marks_added"] > 0)
    return f


def fault_summary(preds: dict, truths: dict, finishes: dict, keys, fold) -> dict:
    tot, n = Counter(), 0
    for k in keys:
        if k not in truths or truths[k] is None:
            continue
        n += 1
        tot.update(faults(preds.get(k) or "", truths[k], finishes.get(k), fold))
    W, Lt = max(1, tot["truth_words"]), max(1, tot["truth_letters"])
    return dict(lines=n,
                invented=dict(words_per_100=round(100 * tot["invented_words"] / W, 3), lines=tot["line_invented"]),
                dropped=dict(words_per_100=round(100 * tot["dropped_words"] / W, 3), lines=tot["line_dropped"]),
                loop=dict(lines=tot["line_loop"]),
                digit_set=dict(digits=tot["digit_set_changed"], lines=tot["line_digit_set"]),
                spelling=dict(per_1000_letters=round(1000 * tot["spelling_all"] / Lt, 3), lines=tot["line_spelling"],
                              by_class={c: tot[f"spelling_{c}"] for c in CLASSES}),
                marks=dict(added=tot["marks_added"], dropped=tot["marks_dropped"], changed=tot["marks_changed"],
                           lines_with_added=tot["line_marks_added"]),
                raw=dict(tot))


def read_pred(path, adapter=None):
    P, F, meta = {}, {}, Counter()
    for l in open(path, encoding="utf-8"):
        if not l.strip():
            continue
        d = json.loads(l)
        if adapter is not None and d.get("adapter") != adapter:
            continue
        P[d["key"]] = d.get("text") or ""
        F[d["key"]] = d.get("finish")
        meta["out_tokens"] += d.get("out_tokens") or 0
        meta["prompt_tokens"] += d.get("prompt_tokens") or 0
        meta["n"] += 1
    return P, F, meta


def exam(pred_path=None, name="model", adapter=None, rate=None, texts=None):
    import score97 as S
    import score99 as S99
    use, truth, extra = S99.r1_truth()
    keys = sorted(use)
    if texts is None:
        P, F, meta = read_pred(pred_path, adapter)
    else:
        P, F, meta = texts, {}, Counter()
    res = dict(name=name, lines=len(keys), with_truth=sum(k in truth for k in keys), **extra)
    res["reading"] = S99.r1_rates(P, truth, keys)
    ex = {k: (truth.get(k) or {}).get("exact") for k in keys}
    res["faults"] = fault_summary(P, ex, F, keys, S.r1_fold)
    res["faults"]["note"] = "on lines with an exact truth (%d)" % sum(1 for k in keys if ex.get(k))
    # t91 trained on some exam lines (experiment 77's pages): report the split for every reader
    seen = t91_seen_keys()
    res["reading_t91_unseen_lines"] = S99.r1_rates(P, truth, [k for k in keys if k not in seen])
    res["reading_t91_seen_lines"] = S99.r1_rates(P, truth, [k for k in keys if k in seen])
    res["t91_seen_lines"] = sum(k in seen for k in keys)
    res["missing_predictions"] = sum(1 for k in keys if k not in P)
    if meta.get("n"):
        res["tokens"] = dict(mean_prompt=round(meta["prompt_tokens"] / meta["n"], 1), mean_out=round(meta["out_tokens"] / meta["n"], 1))
    return res


def t91_seen_keys() -> set:
    """Exam line ids that are in experiment 77's training manifests (t91, v7-28M, v3 trained on those pages)."""
    import glob
    ex = set()
    for l in open(E / "97_extraction_evals/out/reading/lines.jsonl", encoding="utf-8"):
        r = json.loads(l)
        ex.add(f"{r['stem']}_p{r['page']:03d}_l{r['line']:03d}")
    stems = {k[:16] for k in ex}
    seen = set()
    for f in glob.glob(str(E / "77_scratch_reader/out/shards/manifest-train-*.jsonl")) + \
            glob.glob(str(E / "77_scratch_reader/out/shards/manifest-old80-*.jsonl")):
        for l in open(f, encoding="utf-8"):
            k = l[9:l.index('"', 9)]                     # {"key": "<key>", ...
            if k[:16] in stems and k in ex:
                seen.add(k)
    return seen


def dev(pred_path, name="model", adapter=None, rows=None, texts=None):
    import score97 as S
    import score99 as S99
    rows = rows or [json.loads(l) for l in open(HERE / "out/sets/dev.jsonl", encoding="utf-8")]
    keys = [r["key"] for r in rows]
    truth = {r["key"]: dict(exact=ws(r["label"]), folded=S.r1_fold(ws(r["label"]))) for r in rows}
    if texts is None:
        P, F, meta = read_pred(pred_path, adapter)
    else:
        P, F, meta = texts, {}, Counter()
    res = dict(name=name, adapter=adapter, lines=len(keys), reading=S99.r1_rates(P, truth, keys), by_era={})
    for e in ("2000+", "1980-1999", "1950-1979", "pre-1950"):
        ks = [r["key"] for r in rows if r["era"] == e]
        res["by_era"][e] = S99.r1_rates(P, truth, ks)["folded_no_punct"]
    res["faults"] = fault_summary(P, {k: truth[k]["exact"] for k in keys}, F, keys, S.r1_fold)
    res["missing_predictions"] = sum(1 for k in keys if k not in P)
    return res


def locked(pred_path, name="q102", adapter=None):
    """Experiment 90's locked test, scored exactly as experiment 90 scored v7-28M and Azure: est90.run (est81's
    stratified estimator, judged truths, 1,000 page-bootstrap draws), strict and folded, mastheads in and out, by era
    and set, paired against Azure and against v7-28M ("final").  The new reading is added as one more reader, like
    experiment 90's v7 reference: it was never shown to the judge, so a judged line where it reads something no
    candidate had counts against it (coverage reported)."""
    sys.path.insert(0, str(E / "90_locked_final"))
    import est90
    P, F, _ = read_pred(pred_path, adapter)
    orig_jl = est90.jl

    def jl(p):
        rows = orig_jl(p)
        if str(p).endswith("readings90.jsonl"):
            for r in rows:
                r["readings"][name] = P.get(r["key"], "")
        return rows
    est90.jl = jl
    est90.READERS = ["azure", "final", "v3", "v6r", "v7", name]
    est90.OURS = ["final", name]
    R = {m: est90.run(m) for m in ("strict", "folded")}
    keep = {}
    for m in ("strict", "folded"):
        o = R[m]["masthead_out"]
        keep[m] = dict(all={k: o["all"][k] for k in ("azure", "final", name)},
                       by_era={e: {k: v[k] for k in ("azure", "final", name)} for e, v in o["by_era"].items()},
                       by_set={e: {k: v[k] for k in ("azure", "final", name)} for e, v in o["by_set"].items()},
                       paired_vs_azure=o["paired_vs_azure"].get(name),
                       titles={k: R[m]["titles"]["all"][k] for k in ("azure", "final", name)} if "titles" in R[m] else None)
        js = R[m]["judge_consistency"]
        keep[m]["coverage_T_eq"] = {k: v for k, v in js.items() if k.endswith(f"T_eq_{name}")}
    keep["missing_predictions"] = sum(1 for r in orig_jl(est90.OUT / "readings90.jsonl") if r["key"] not in P)
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["exam", "dev", "baselines", "locked"])
    ap.add_argument("pred", nargs="?")
    ap.add_argument("--name", default="model")
    ap.add_argument("--adapter", default=None)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.what == "baselines":
        import score99 as S99
        use, _, _ = S99.r1_truth()
        for w in ("azure", "t91"):
            r = exam(name=w, texts={k: use[k].get(w) or "" for k in use})
            (OUT / f"exam_{w}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
            print(w, json.dumps(r["reading"]["folded_no_punct"]), json.dumps(r["faults"], ensure_ascii=False)[:600])
        return
    if a.what == "locked":
        r = locked(a.pred, a.name, a.adapter)
    else:
        r = exam(a.pred, a.name, a.adapter) if a.what == "exam" else dev(a.pred, a.name, a.adapter)
    (OUT / f"{a.what}_{a.name}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    print(json.dumps(r, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
