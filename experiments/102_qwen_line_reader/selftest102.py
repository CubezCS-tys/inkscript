"""Experiment 102's self-test, without a GPU.

    ../81_heldout_scale/out/venv/bin/python selftest102.py lock      the builder and the trainer refuse locked keys
    python3 selftest102.py faults                                    the scorer on fake exam outputs, faults planted
    ../81_heldout_scale/out/venv/bin/python selftest102.py locked    the locked scorer reproduces experiment 90
Results: out/selftest/*.json.  (The trainer's CPU dry run is a separate command, in the README.)
"""
from __future__ import annotations

import gzip
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out/selftest"


def t_lock():
    import build102 as B
    import guard102 as G
    import train102 as T
    pool = [json.loads(l) for l in gzip.open(HERE / "out/pool/pool102.jsonl.gz", "rt", encoding="utf-8")]
    rng = random.Random(7)
    sample = [r for r in pool if r["part"] == "dev"] + rng.sample([r for r in pool if r["part"] != "dev"], 60000)
    B.SIZES = {"S": 500, "M": 5000, "L": 100000}
    res = {}
    B.build(sample)
    res["clean sample"] = "built"
    base = dict(sample[-1])
    lock = json.loads((E / "84_display_fonts/LOCKED_TEST.json").read_text())["journals"][0]["code"]
    old = json.loads((E / "88_truth_and_lock/LOCKED_OLD_DOCS.json").read_text())["documents"][0]["stem"]
    exam = json.loads((E / "97_extraction_evals/LOCKED_EVAL.json").read_text())["articles"][0]["stem"]
    held = json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"][0]
    cases = {"exam article line": f"{exam}_p003_l004", "locked journal (84)": f"{lock}-001-002-003_p001_l001",
             "locked old document (88)": f"{old}_p002_l010", "held-out journal (76)": f"{held}-010-001-001_p001_l002"}
    for name, key in cases.items():
        bad = dict(base, key=key, stem=key[:16], jcode=key[:4], part="train", title=True)  # titles go into S first
        try:
            B.build(sample + [bad])
            res[f"builder, {name}"] = "NOT REFUSED"
        except AssertionError as e:
            res[f"builder, {name}"] = "refused: " + str(e)[:140]
        try:
            T.guard([bad], HERE / "forbidden102.json")
            res[f"trainer, {name}"] = "NOT REFUSED"
        except SystemExit as e:
            res[f"trainer, {name}"] = "refused: " + str(e)[:100]
    bad = dict(base, label_source="ocria1_exp100", title=True)
    try:
        B.build(sample + [bad])
        res["builder, OCRia-1 label source"] = "NOT REFUSED"
    except AssertionError as e:
        res["builder, OCRia-1 label source"] = "refused: " + str(e)[:120]
    # the real manifests, re-checked
    for f in ("S", "M", "L_local", "dev"):
        rows = [json.loads(l) for l in open(HERE / f"out/sets/{f}.jsonl", encoding="utf-8")]
        res[f"real {f}: keys checked by guard102"] = G.assert_trainable(r["key"] for r in rows)
        res[f"real {f}: checked by train102.guard"] = T.guard(rows, HERE / "forbidden102.json")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "lock.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in res.items():
        print(f"{k}: {v}")
    assert all("NOT REFUSED" not in str(v) for v in res.values())


def plant(kind, truths, keys):
    P, F = {}, {}
    to_ascii = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    to_ar = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
    for n, k in enumerate(keys):
        t = truths[k]
        w = t.split()
        p = t
        if kind in ("invent", "all") and n % 10 == 0:
            p = t + " كلمة مضافة هنا"
        elif kind in ("drop", "all") and n % 10 == 1 and len(w) >= 5:
            p = " ".join(w[:1] + w[3:])
        elif kind in ("loop", "all") and n % 10 == 2 and w:
            p = t + (" " + w[-1]) * 4
            if n % 20 == 2:
                F[k] = "length"
        elif kind in ("digits", "all") and n % 10 == 3 and re.search(r"[0-9٠-٩]", t):
            p = t.translate(to_ascii) if re.search("[٠-٩]", t) else t.translate(to_ar)
        elif kind in ("spelling", "all") and n % 10 == 4:
            p = t.replace("أ", "ا", 1).replace("ى", "ي", 1).replace("ة", "ه", 1)
        elif kind in ("marks", "all") and n % 10 == 5:
            m = re.search("[ء-ي]", t)
            if m:
                p = t[:m.end()] + "َ" + t[m.end():]
        P[k] = p
    return P, F


def t_faults():
    import score102 as SC
    sys.path.insert(0, str(E / "99_liteparse_baseline/scripts"))
    import score99 as S99
    import score97 as S
    use, truth, _ = S99.r1_truth()
    keys = sorted(k for k in use if (truth.get(k) or {}).get("exact"))
    tr = {k: truth[k]["exact"] for k in keys}
    out = {}
    for kind in ("perfect", "invent", "drop", "loop", "digits", "spelling", "marks", "all"):
        P, F = plant(kind, tr, keys)
        rd = S99.r1_rates(P, truth, sorted(use))["folded_no_punct"]
        fs = SC.fault_summary(P, tr, F, keys, S.r1_fold)
        out[kind] = dict(letters_wrong_folded_np=rd["letter_error"], lines_wrong=rd["lines_wrong"],
                         invented_lines=fs["invented"]["lines"], invented_words_per_100=fs["invented"]["words_per_100"],
                         dropped_lines=fs["dropped"]["lines"], dropped_words_per_100=fs["dropped"]["words_per_100"],
                         loop_lines=fs["loop"]["lines"], digit_set_digits=fs["digit_set"]["digits"],
                         digit_set_lines=fs["digit_set"]["lines"], spelling_lines=fs["spelling"]["lines"],
                         spelling_by_class=fs["spelling"]["by_class"], marks_added=fs["marks"]["added"])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "faults.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    cols = ["letters_wrong_folded_np", "invented_lines", "dropped_lines", "loop_lines", "digit_set_lines", "spelling_lines",
            "marks_added"]
    print("variant | " + " | ".join(cols))
    for k, v in out.items():
        print(k, "|", " | ".join(str(v[c]) for c in cols))
    print("lines with an exact truth:", len(keys))


def t_locked():
    import score102 as SC
    sys.path.insert(0, str(E / "90_locked_final"))
    import est90
    rows = est90.jl(est90.OUT / "readings90.jsonl")
    fake = OUT / "locked_fake_final.jsonl"
    OUT.mkdir(parents=True, exist_ok=True)
    with open(fake, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(dict(key=r["key"], adapter=None, text=r["readings"]["final"]), ensure_ascii=False) + "\n")
    R = SC.locked(fake, "q102")
    ref = json.loads((E / "90_locked_final/out/est90.json").read_text())
    a = R["strict"]["all"]
    out = dict(q102_strict=a["q102"]["letters"], final_strict=a["final"]["letters"], azure_strict=a["azure"]["letters"],
               est90_json_final=ref["strict"]["masthead_out"]["all"]["final"]["letters"],
               est90_json_azure=ref["strict"]["masthead_out"]["all"]["azure"]["letters"],
               q102_line=a["q102"]["line"], final_line=a["final"]["line"],
               q102_folded=R["folded"]["all"]["q102"]["letters"], final_folded=R["folded"]["all"]["final"]["letters"],
               by_era_strict={e: (v["q102"]["letters"], v["final"]["letters"]) for e, v in R["strict"]["by_era"].items()})
    (OUT / "locked.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    {"lock": t_lock, "faults": t_faults, "locked": t_locked}[sys.argv[1]]()
