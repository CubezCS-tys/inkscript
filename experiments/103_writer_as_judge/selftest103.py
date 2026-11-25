"""Experiment 103 self-tests (no GPU).

    nice -n 19 ionice -c3 python3 selftest103.py fix      -> out/selftest/fix103.json (+ fix103_fail.jsonl)
    nice -n 19 ionice -c3 python3 selftest103.py score    -> out/selftest/score103.json (score103's bars on fake data)

fix: synthetic lines built from KNOWN logical strings (the convention of fix103): each is laid out by headless
Chromium in an RTL paragraph; the line as seen (Chromium's character positions, clusters left to right) is put
into Azure's order (fix103.azure_style, Azure's habit measured on real lines); the fixer must give back the
original exactly, and Chromium must show the fixer's output as it shows the original.  Kinds: Latin citation,
Latin term, digit groups, percent signs, mixed brackets, plus Arabic-Indic digits.  Do no harm: real pure-Arabic
and pure-Latin lines of M are unchanged, and the fixer is idempotent on every changed M line.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))
from bidi103 import chrome_display, fribidi_display, _mirror, is_mark, chrome_base_order, fribidi_base_order  # noqa: E402
from fix103 import fix_line, azure_style, visual_clusters, AR_LETTER, LAT, DIG  # noqa: E402


def chrome_visual(s: str, xs):
    """The line as seen.  Chromium is the judge of ORDER: the order of every character that is not an Arabic letter
    (Latin, digits, punctuation, brackets) must be the same in Chromium's layout as in fribidi's.  Chromium gives the
    letters of a ligature (lam-alif) one box, so letters inside an Arabic word are taken from fribidi.
    Returns fribidi's clusters left to right, or None if Chromium disagrees."""
    if chrome_base_order(s, xs, True) != fribidi_base_order(s, True):
        return None
    return visual_clusters(s)

OUT = HERE / "out/selftest"
M = E / "102_qwen_line_reader/out/sets/M.jsonl"

NAMES = ["Adin", "Ferri", "Nonaka", "Langer", "Deroy", "Howell", "Braun and Clarke", "Davis & Autin", "Mc Carthy et al.",
         "Shoji et al.", "Comerta & Ogel", "Kyriakides et al.", "van Oers", "Arthur-Nyarko et al.", "Sun et al."]
TERMS = ["STEM", "NCAAA", "Wiki", "Sherrod", "Extreme Gradient Boosting", "Soil Texture", "Blue-collar Workers",
         "Patient Health Questionnaire", "Mobile Learning", "E-Views", "SPSS", "TIFIB", "Research objective"]


def chrome_visual_full(s: str, xs) -> list[str]:
    """Chromium's layout as clusters left to right (base shape + marks; spaces kept).  The mirror of an RTL-level
    bracket comes from fribidi's level: Chromium does not expose levels, and the mirror table is the same."""
    _, _, lev = fribidi_display(s)
    cl = []
    for i, c in enumerate(s):
        if is_mark(c) and cl:
            cl[-1].append(i)
        else:
            cl.append([i])
    cl = [c for c in cl if xs[c[0]][1] > 0 or s[c[0]] == " "]
    cl.sort(key=lambda c: xs[c[0]][0] + xs[c[0]][1] / 2)
    return [(_mirror(s[c[0]]) if lev[c[0]] % 2 else s[c[0]]) + "".join(s[x] for x in c[1:]) for c in cl]


def synth(rng, ar_words):
    """(kind, logical string) pairs, the logical string written by the convention."""
    def ar(n):
        return " ".join(rng.choice(ar_words) for _ in range(n))
    y = lambda: str(rng.randint(1950, 2024))                                 # noqa: E731
    cases = []
    for _ in range(140):
        nm = rng.choice(NAMES)
        form = rng.choice([f"({nm}, {y()})", f"({nm}, {y()}, p. {rng.randint(2, 400)})", f"({nm}, {y()}; {rng.choice(NAMES)}, {y()})",
                           f"{nm} ({y()})"])
        cases.append(("latin_citation", f"{ar(rng.randint(1, 5))} {form} {ar(rng.randint(1, 5))}"))
    for _ in range(60):
        cases.append(("latin_citation", f"{ar(rng.randint(1, 4))} ISSN: {rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"))
    for _ in range(60):
        cases.append(("latin_citation", f"{ar(rng.randint(1, 4))} Python {rng.randint(2, 3)}.{rng.randint(0, 12)}.{rng.randint(0, 9)} {ar(2)}"))
    for _ in range(100):
        t = rng.choice(TERMS)
        form = rng.choice([f"({t})", t, f"{t} ({''.join(w[0] for w in t.split()).upper()})", f"{t}، {rng.choice(TERMS)}"])
        cases.append(("latin_term" if "(" not in form else "mixed_brackets", f"{ar(rng.randint(1, 5))} {form} {ar(rng.randint(0, 4))}".strip()))
    for _ in range(80):
        a = rng.randint(1, 400)
        form = rng.choice([f"{a}-{a + rng.randint(1, 30)}", f"{y()}، {y()}", f"({a})", f"{rng.randint(1, 31)}/{rng.randint(1, 12)}/{y()}",
                           f"{a}.{rng.randint(0, 99)}", f"{rng.randint(1, 99)} {rng.randint(100, 999)}"])
        cases.append(("digit_group", f"{ar(rng.randint(1, 4))} {form} {ar(rng.randint(1, 4))}"))
    for _ in range(60):
        a = rng.choice([str(rng.randint(1, 99)), f"{rng.randint(1, 99)}.{rng.randint(0, 9)}", "٤٥", "١٢٫٥"])
        form = rng.choice([f"{a}%", f"%{a}", f"({a}%)", f"{a} ٪", f"{a}٪"])
        cases.append(("percent", f"{ar(rng.randint(1, 4))} {form} {ar(rng.randint(1, 4))}"))
    for _ in range(40):
        a = "".join(rng.choice("٠١٢٣٤٥٦٧٨٩") for _ in range(rng.randint(1, 4)))
        form = rng.choice([f"({a})", f"{a}-{a}", f"ص{a}", f"{a}م"])
        cases.append(("arabic_indic", f"{ar(rng.randint(1, 4))} {form} {ar(rng.randint(1, 3))}"))
    return cases


def test_fix():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(103)
    rows = [json.loads(l) for l in open(M, encoding="utf-8")]
    ar_words = sorted({w for r in rows[:20000] for w in r["label"].split()
                       if AR_LETTER.search(w) and all(AR_LETTER.match(c) or is_mark(c) for c in w)})
    cases = synth(rng, ar_words)
    xs = chrome_display([t for _, t in cases])
    res, fails = Counter(), []
    pairs = []
    for (kind, t), x in zip(cases, xs):
        vis = chrome_visual(t, x)
        res[f"{kind}_n"] += 1
        if vis is None:
            res[f"{kind}_chrome_disagrees"] += 1
            fails.append(dict(kind=kind, original=t, why="chromium and fribidi order differ"))
            pairs.append((t, t))
            continue
        az = azure_style("".join(vis))
        from fix103 import display_key
        if display_key(az) != display_key(t):
            # Azure's habit applied to this layout changes what is SHOWN (two Latin terms joined by «،» become one
            # left-to-right run): not an order case, no fixer can know the original; counted apart
            res[f"{kind}_azure_style_changes_display"] += 1
            pairs.append((t, t))
            continue
        new, info = fix_line(az)
        pairs.append((t, new))
        ok = new == t
        res[f"{kind}_back"] += ok
        res[f"{kind}_azure_differs"] += az != t
        if not ok:
            fails.append(dict(kind=kind, original=t, azure_style=az, fixed=new, why=info["why"]))
    # Chromium shows the fixer's output as it shows the original (the order of runs and punctuation)
    flat = [s for p in pairs for s in p]
    xs2 = chrome_display(flat)
    same = sum([a[i] for i in chrome_base_order(a, xa, True)] == [b[i] for i in chrome_base_order(b, xb, True)]
               for (a, b), xa, xb in zip(pairs, xs2[0::2], xs2[1::2]))
    res["chrome_same_display"] = same
    res["cases"] = len(cases)
    res["back_total"] = sum(v for k, v in res.items() if k.endswith("_back"))
    res["valid_cases"] = len(cases) - sum(v for k, v in res.items() if k.endswith("_azure_style_changes_display") or k.endswith("_chrome_disagrees"))
    # do no harm, on real lines
    pure_ar = [r["label"] for r in rows if AR_LETTER.search(r["label"]) and not LAT.search(r["label"]) and not DIG.search(r["label"])]
    pure_lat = [r["label"] for r in rows if LAT.search(r["label"]) and not AR_LETTER.search(r["label"])]
    res["pure_arabic_lines"] = len(pure_ar)
    res["pure_arabic_unchanged"] = sum(fix_line(s)[0] == s for s in pure_ar)
    res["pure_latin_lines"] = len(pure_lat)
    res["pure_latin_unchanged"] = sum(fix_line(s)[0] == s for s in pure_lat)
    ch = [json.loads(l) for l in open(HERE / "out/diag/changed_M.jsonl", encoding="utf-8")]
    res["changed_M"] = len(ch)
    res["idempotent"] = sum(fix_line(r["new"])[0] == r["new"] for r in ch)
    res["changed_M_letters_kept"] = sum(sorted(r["new"].replace(" ", "")) == sorted(r["old"].replace(" ", "")) or
                                        _same_but_mirror(r["old"], r["new"]) for r in ch)
    (OUT / "fix103.json").write_text(json.dumps(dict(res), indent=1))
    with open(OUT / "fix103_fail.jsonl", "w", encoding="utf-8") as f:
        for x in fails:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(json.dumps(dict(res), indent=1))
    for x in fails[:12]:
        print(x)


def _same_but_mirror(a, b):
    fold = lambda s: sorted(_mirror(c) if c in ")]}>»›" else c for c in s.replace(" ", ""))   # noqa: E731
    return fold(a) == fold(b)


def test_bsets():
    """pool103's B-set builder on a FAKE reading of the held-out pool (no GPU): 85% read as Azure, 12% one letter
    changed, 3% two words dropped; the builder must find the planted gross lines as B1 candidates, give 300 J lines,
    and write every file the host and the blind readers need (into out/selftest/b, never out/b)."""
    import os
    import subprocess
    rng = random.Random(7)
    rows = [json.loads(l) for l in open(HERE / "out/sets/heldout.jsonl", encoding="utf-8")]
    fake, truth_gross = [], set()
    for r in rows:
        t, u = r["label"], rng.random()
        ws = t.split()
        if u < 0.03 and len(ws) >= 5:
            t = " ".join(ws[:1] + ws[3:])
            truth_gross.add(r["key"])
        elif u < 0.15:
            ch = [i for i, c in enumerate(t) if AR_LETTER.match(c)]
            if ch:
                i = rng.choice(ch)
                t = t[:i] + ("ب" if t[i] != "ب" else "ت") + t[i + 1:]
        fake.append(dict(key=r["key"], adapter="fake", text=t, finish="stop", lp_mean=-rng.random() * 0.1,
                         lp_min=-rng.random() * 3, n_tok=10))
    OUT.mkdir(parents=True, exist_ok=True)
    fp = OUT / "fake_read.jsonl"
    with open(fp, "w", encoding="utf-8") as f:
        for d in fake:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    env = dict(os.environ, B103_OUT=str(OUT / "b"))
    r = subprocess.run([sys.executable, str(HERE / "pool103.py"), "b", str(fp)], env=env, capture_output=True, text=True)
    print(r.stdout[-1500:], r.stderr[-1500:])
    summ = json.loads((OUT / "b/b_summary.json").read_text())
    jobs = [json.loads(l) for l in open(OUT / "b/writer_jobs.jsonl", encoding="utf-8")]
    disp = [json.loads(l) for l in open(OUT / "b/disputes.jsonl", encoding="utf-8")]
    priv = {json.loads(l)["id"]: json.loads(l) for l in open(OUT / "b/private/witnesses.jsonl", encoding="utf-8")}
    far = {j["key"] for j in jobs if j["kind"] == "real_reader"}
    elig_gross = {k for k in truth_gross if k in {d["key"] for d in fake}}
    res = dict(summary=summ, planted_gross=len(truth_gross), found_as_b1=len(far & truth_gross),
               b1_candidates_not_planted=len(far - truth_gross), writer_jobs=len(jobs), disputes=len(disp),
               candidates_shuffled=sum(1 for d in disp if not d["control"] and priv[d["id"]]["witnesses"]["0"] == "azure"),
               no_origin_in_disputes=all("reader" not in json.dumps(d) and "azure" not in json.dumps(d) for d in disp),
               wtext_on_every_job=all("wtext" in j for j in jobs))
    (OUT / "bsets103.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


def test_repair():
    """score103.repair end to end on FAKE readings (no GPU): M reads every line as its Azure-order label; checkpoint
    "run_R/ckpt-50" reads the fixed targets but drops a word on 3% of DEV lines (worse on DEV: not eligible);
    "run_R/ckpt-100" reads the fixed targets.  Expected: ckpt-100 chosen, REPAIR PASS."""
    import subprocess
    rng = random.Random(5)
    sets = HERE / "out/sets"
    dev = [json.loads(l) for l in open(sets / "dev103.jsonl", encoding="utf-8")]
    dm = [json.loads(l) for l in open(sets / "devmix.jsonl", encoding="utf-8")]
    def rows_for(rows, ad):
        out = []
        for r in rows:
            t = r.get("label_azure", r["label"]) if ad == "M" else r["label"]
            if ad.endswith("ckpt-50") and rng.random() < 0.03 and len(t.split()) > 3:
                t = " ".join(t.split()[1:])
            out.append(dict(key=r["key"], adapter=ad, text=t, finish="stop", prompt_tokens=1, out_tokens=1))
        return out
    for name, rows in (("dev", dev), ("devmix", dm)):
        with open(OUT / f"fake_{name}.jsonl", "w", encoding="utf-8") as f:
            for ad in ("M", "run_R/ckpt-50", "run_R/ckpt-100"):
                for d in rows_for(rows, ad):
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
    py = str(E / "81_heldout_scale/out/venv/bin/python")
    r = subprocess.run([py, str(HERE / "score103.py"), "repair", str(OUT / "fake_dev.jsonl"), str(OUT / "fake_devmix.jsonl"),
                        "--base_adapter", "M"], capture_output=True, text=True)
    print(r.stdout[-2500:], r.stderr[-2000:])
    res = json.loads((HERE / "out/scores/repair.json").read_text())
    (HERE / "out/scores/repair.json").rename(OUT / "repair_fake.json")
    print("chosen", res.get("chosen"), res.get("REPAIR"))


if __name__ == "__main__":
    if sys.argv[1] == "fix":
        test_fix()
    elif sys.argv[1] == "score":
        import score103
        score103.selftest(OUT)
    elif sys.argv[1] == "bsets":
        test_bsets()
    elif sys.argv[1] == "repair":
        test_repair()

