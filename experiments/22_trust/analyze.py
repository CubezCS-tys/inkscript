"""Which free signals, combined how, mark the words a reader should not trust?

    .venv/bin/python analyze.py        -> out/flag_eval.json (and a table on stdout)

Truth: experiment 19's judged words (2,971 from 139 random scanned documents; the calibrated judge's final verdict and
the agent's by-eye cause). An *error* is a letter error there, minus the one the agent found to be the judge's own
mistake, minus a Persian ی/ک slip that the build now folds (src/inkscript/text.py fold_letters): it is not wrong in
our PDF any more. Rates are weighted like experiment 19's (each judged word stands for N/n words of its document and
stratum), with 95% intervals by bootstrap over documents (2,000 draws).

For each rule:
  flagged     weighted share of words it marks (what a reader is asked to look at)
  caught      weighted share of errors among the marked words (recall)
  per page    flagged words on an average scanned page (578,852 words on the 139 documents' scanned pages)
  left        error rate in the words left unmarked: what "trust the unmarked text" means
  precision   share of marked words that are errors
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
E19 = HERE.parent / "19_azure_map/out"

D = json.load(open(HERE / "out/judged_signals.json")); ROWS = D["rows"]
for r in ROWS:  # the truth
    r["truth"] = bool(r["err"]) and r["cause"] != "judge wrong" and not (r["cause"] == "encoding" and not r["persian"])
POP = json.load(open(E19 / "population.json")); DOCS = json.load(open(E19 / "docs.json"))
WORDS = sum(p["words"] for p in POP.values())
PAGES = sum(DOCS[d]["pages"] - len(p["skipped_pages"]) for d, p in POP.items())
WPP = WORDS / PAGES


from flag import rule, low_conf, persian, quran, speck, ornament, latin, old, hamza, salla, supnum, BASE, SIG_INK, RULES, DEFAULT

# ---------------------------------------------------------------- measures

def measure(rows, flag):
    sw = sw_f = sw_e = sw_fe = 0.0
    for r in rows:
        f = bool(flag(r)); w = r["w"]
        sw += w; sw_e += w * r["truth"]
        if f: sw_f += w; sw_fe += w * r["truth"]
    return dict(flagged=sw_f / sw, caught=sw_fe / sw_e if sw_e else float("nan"),
                left=(sw_e - sw_fe) / (sw - sw_f) if sw > sw_f else float("nan"),
                precision=sw_fe / sw_f if sw_f else float("nan"))


def boot(rows, flag, reps=2000, seed=22):
    by = defaultdict(list)
    for r in rows: by[r["doc"]].append(r)
    docs = list(by); rng = random.Random(seed); keys = ("flagged", "caught", "left", "precision"); vals = {k: [] for k in keys}
    pre = {d: [(r["w"], r["truth"], bool(flag(r))) for r in by[d]] for d in docs}
    vals["caught_unweighted"] = []
    for _ in range(reps):
        sw = sw_f = sw_e = sw_fe = 0.0; ne = nfe = 0
        for d in (rng.choice(docs) for _ in docs):
            for w, t, f in pre[d]:
                sw += w; sw_e += w * t; ne += t; nfe += t and f
                if f: sw_f += w; sw_fe += w * t
        if not sw_e: continue
        vals["flagged"].append(sw_f / sw); vals["caught"].append(sw_fe / sw_e)
        vals["left"].append((sw_e - sw_fe) / (sw - sw_f)); vals["precision"].append(sw_fe / sw_f if sw_f else 0)
        vals["caught_unweighted"].append(nfe / ne)
    out = {}
    for k, v in vals.items():
        v.sort(); out[k] = [v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1]]
    return out


def full(rows, name, flag, ci=True):
    m = measure(rows, flag)
    m.update(name=name, per_page=m["flagged"] * WPP, n_flagged=sum(bool(flag(r)) for r in rows),
             n_caught=sum(bool(flag(r)) and r["truth"] for r in rows), n_errors=sum(r["truth"] for r in rows),
             n_caught_unweighted_share=None)
    m["caught_unweighted"] = m["n_caught"] / m["n_errors"]
    if ci: m["ci"] = boot(rows, flag)
    return m


def curve(rows, extra):
    pts = []
    for t in [0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.98, 0.99, 1.01]:
        m = measure(rows, rule(low_conf(t), *extra)); pts.append(dict(t=t, flagged=m["flagged"], caught=m["caught"], left=m["left"]))
    return pts


if __name__ == "__main__":
    rows = ROWS
    print(f"{len(rows)} words, {sum(r['truth'] for r in rows)} errors; {WORDS} words on {PAGES} scanned pages = {WPP:.0f} words/page")
    res = {"words_per_page": WPP, "n": len(rows), "errors": sum(r["truth"] for r in rows), "rules": []}
    for name, f in RULES.items():
        m = full(rows, name, f); res["rules"].append(m)
        c = m["ci"]
        print(f"{name:58s} flag {m['flagged']:6.2%} [{c['flagged'][0]:.1%}-{c['flagged'][1]:.1%}]  caught {m['caught']:5.1%} "
              f"[{c['caught'][0]:.0%}-{c['caught'][1]:.0%}] ({m['n_caught']}/{m['n_errors']} [{c['caught_unweighted'][0]:.0%}-{c['caught_unweighted'][1]:.0%}])  left {m['left']:.2%} "
              f"[{c['left'][0]:.2%}-{c['left'][1]:.2%}]  prec {m['precision']:.1%}  {m['per_page']:.1f}/page")
    res["curve_conf"] = curve(rows, [])
    res["curve_default"] = curve(rows, [persian, quran, speck, ornament, latin])
    # each signal alone, beyond conf < 0.8
    base = rule(low_conf(0.8))
    alone = {}
    for s in [persian, quran, speck, ornament, latin, old(0.9), hamza, salla, supnum]:
        nm = s(dict(conf=0.0, persian=1, quran="dots", h_rel=0.1, line_n=1, w_rel=0.1, ink=1, latin=1, arabic_page=1,
                    year=1990, hamza_doc=1, hamza=1, salla=1, supnum=1)) or "?"
        fl = [r for r in rows if s(r)]
        new = [r for r in fl if not base(r)]
        alone[nm] = dict(flags=len(fl), flagged=measure(rows, s)["flagged"], errors=sum(r["truth"] for r in fl),
                         new_flags=len(new), new_errors=sum(r["truth"] for r in new),
                         new_flagged_w=measure(rows, lambda r: bool(s(r)) and not base(r))["flagged"],
                         new_causes=dict(Counter(r["cause"] for r in new if r["truth"])))
        print(f"  {nm:40s} alone: {len(fl):4d} words, {alone[nm]['errors']} errors; beyond conf<0.8: +{len(new)} words "
              f"({alone[nm]['new_flagged_w']:.2%} weighted), +{alone[nm]['new_errors']} errors {alone[nm]['new_causes']}")
    res["signals"] = alone
    # what the default misses, and what it catches, by cause
    f = RULES[DEFAULT]
    res["by_cause"] = {c: dict(n=sum(1 for r in rows if r["truth"] and r["cause"] == c),
                               caught=sum(1 for r in rows if r["truth"] and r["cause"] == c and f(r)))
                       for c in sorted({r["cause"] for r in rows if r["truth"]})}
    res["missed"] = [dict(id=r["id"], text=r["text"], judge=r["judge"], conf=r["conf"], cause=r["cause"], w=r["w"])
                     for r in rows if r["truth"] and not f(r)]
    print("by cause", res["by_cause"])
    for m in res["missed"]: print("  missed", m)
    # the Quran check cannot be measured on these words (none of the judged words falls on a differing quotation word):
    # its share of all words of the 139 documents, from quotes.py, and its precision from experiment 20 (20 of 24 by eye)
    Q = json.load(open(HERE / "out/quotes.json"))
    nq = sum(len(o["doc"]) for d in POP for qt in Q.get(d, {}).get("quotes", []) for o in qt["ops"] if o["kind"] in ("dots", "letters", "other"))
    res["quran_all_words"] = dict(differing=nq, words=WORDS, share=nq / WORDS, docs_with_quotes=sum(1 for d in POP if Q.get(d, {}).get("quotes")),
                                  precision_by_eye_exp20="20 of 24")
    print("Quran check over all words of the 139 documents:", res["quran_all_words"])
    # pre-2000 vs later, for the default
    for lab, sel in [("pre-2000", lambda r: r["year"] and r["year"] < 2000), ("2000+", lambda r: r["year"] and r["year"] >= 2000)]:
        sub = [r for r in rows if sel(r)]
        m = full(sub, lab, f); res[lab] = m
        print(f"  default on {lab}: flag {m['flagged']:.2%}, caught {m['caught']:.0%} ({m['n_caught']}/{m['n_errors']}), "
              f"left {m['left']:.2%} [{m['ci']['left'][0]:.2%}-{m['ci']['left'][1]:.2%}], {m['per_page']:.1f}/page")
    # the judged words a reader would see marked, with reasons: kept for the report
    res["examples"] = [dict(id=r["id"], text=r["text"], judge=r["judge"], conf=r["conf"], truth=r["truth"], cause=r["cause"],
                            why=f(r), verdict=r["verdict"]) for r in rows if f(r)]
    res["box_unsure"] = dict(box=sum(1 for r in rows if r["verdict"] == "box"), box_flagged=sum(1 for r in rows if r["verdict"] == "box" and f(r)),
                             unsure=sum(1 for r in rows if r["verdict"] == "unsure"), unsure_flagged=sum(1 for r in rows if r["verdict"] == "unsure" and f(r)))
    print(res["box_unsure"])
    # Paid confirmation, estimated from experiment 19's own verdicts on the flagged words (nothing re-paid):
    # two stages as there: Flash on every flagged word, Pro on those Flash does not call RIGHT; RIGHT clears the flag.
    J = {r["id"]: r for r in json.load(open(E19 / "judged.json"))}
    fl = [r for r in rows if f(r)]
    sw = sum(r["w"] for r in fl)
    flash_not_right = sum(r["w"] for r in fl if J[r["id"]]["flash"] != "right") / sw
    cleared = sum(r["w"] for r in fl if r["verdict"] == "right") / sw
    FLASH_USD, PRO_USD = 3.985533 / 2971, 1.16583 / 283          # experiment 19's measured cost per word (run, run2)
    per_word = FLASH_USD + flash_not_right * PRO_USD
    scanned_docs = 1013912 * 139 / 240                              # experiment 19: 139 of 240 random documents are scans
    archive_words = scanned_docs * WORDS / len(POP)
    flagged_words = archive_words * res["rules"][[x["name"] for x in res["rules"]].index(DEFAULT)]["flagged"]
    res["confirm"] = dict(flash_not_right=flash_not_right, cleared=cleared, flash_usd=FLASH_USD, pro_usd=PRO_USD, per_word=per_word,
                          pro_only_per_word=0.003066554, archive_scanned_docs=scanned_docs, archive_words=archive_words,
                          flagged_words=flagged_words, usd_two_stage=flagged_words * per_word,
                          usd_two_stage_batch=flagged_words * per_word / 2, usd_pro_only=flagged_words * 0.003066554,
                          flags_left=flagged_words * (1 - cleared),
                          flags_left_per_page=(1 - cleared) * res["rules"][[x["name"] for x in res["rules"]].index(DEFAULT)]["per_page"],
                          judge_miss_on_archive_one_mark_changes="3 in 142 (experiment 19 calibration)")
    print("confirm", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["confirm"].items()})
    json.dump(res, open(HERE / "out/flag_eval.json", "w"), ensure_ascii=False, indent=1)
