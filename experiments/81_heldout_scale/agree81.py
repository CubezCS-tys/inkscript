"""Experiment 81, step 3: every reader's reading of every line, the agreement map, and the judge's sample.

    out/venv/bin/python agree81.py map [SIG=p3t]       -> out/readings81.jsonl, out/agree81.json
    out/venv/bin/python agree81.py sample N_DIS N_AGR  -> out/judge/sample.jsonl (stratified by era, seed 81)

Readers per line: azure; argon (Azure + Argon's fixes, only on pages Argon read); v1, v2 (exp 77), s2r (exp 78
syn_then_real); sig (the signal reader alone); fsig = v1's N best re-scored by s77 + 0.2 * s_sig, f78 = the same with
s2r at 1.5 (experiment 79's fuse79.pick with the lambdas its dev split chose, out/fuse/p3t/summary.json).
Comparison form (the experiment-77 headline, `no_punct`): Azure-style cleaning (clean_label), one bidi form
(to_visual), then punctuation removed and spaces collapsed.  Two readings AGREE when these forms are equal.
Frame: lines with at least one Arabic letter and arabic_share >= 0.5 ("arabic"); mostly-Latin lines and lines with
no letter are reported apart and not judged.  Ink type: experiment 79's buckets (fuse79.py), from the signal's
median thickness and blob share, with this set's own tercile thresholds.
AGREE stratum = every reader shown to the judge (azure, argon where present, v1, v2, s2r, fsig, f78) agrees;
DISPUTE stratum = any of them differs.  The signal reader alone is never part of the agreement (it is far weaker).
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "79_signal_reader"))
from common77 import POLICIES_NP, clean_label, to_visual  # noqa: E402

SHOWN = ["azure", "argon", "v1", "v2", "s2r", "fsig", "fsig4", "f78", "v2b", "nuqta"]
LATE = ("v2b", "nuqta", "v3")      # added after the strata were drawn: shown to the judge, never part of the agreement
OURS = ["v1", "v2", "s2r"]
LAM = json.loads((E / "79_signal_reader/out/fuse/p3t/summary.json").read_text())["lambda_"]


def lam_p4r() -> tuple[float, str]:
    """p4r's lambda: experiment 79's own summary if it exists, else the same grid search as fuse79.py on its p4r
    dev file (read only), else p3t's 0.2 (declared)."""
    f = E / "79_signal_reader/out/fuse/p4r/summary.json"
    if f.exists():
        return json.loads(f.read_text())["lambda_"]["ssig"], str(f)
    devs = sorted((E / "79_signal_reader/out").glob("**/fuse*p4r*/dev.jsonl"))
    if devs:
        import fuse79
        dev = fuse79.load(devs[0])
        res = {l: fuse79.cer_lines(dev, "label", lambda r, l=l: fuse79.pick(r, "ssig", l))
               for l in [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5]}
        return min(res, key=res.get), f"grid on {devs[0]}: " + json.dumps({k: round(v, 3) for k, v in res.items()})
    return LAM["ssig"], "no p4r dev scores found: p3t's lambda"


def form(s: str | None) -> str:
    return POLICIES_NP["no_punct"](to_visual(clean_label(s or "")))


def pick(cands, s77, so, lam):
    s77 = np.array([x if x is not None else -1e9 for x in s77])
    if not so or lam == 0:
        return cands[int(np.argmax(s77))]
    ok = [x for x in so if x is not None]
    if not ok:
        return cands[int(np.argmax(s77))]
    worst = min(ok)
    return cands[int(np.argmax(s77 + lam * np.array([x if x is not None else worst for x in so])))]


def ink_bucket(F: np.ndarray, q) -> tuple[str, float, float]:
    F = F.astype(np.float32)
    th, blob = float(np.median(F[:, 11])), float(F[:, 12].mean())
    heavy = th >= q[1] or blob >= 0.02
    thin = th <= q[0] and blob < 0.005
    return ("heavy/spread" if heavy else "thin/crisp" if thin else "even/medium"), th, blob


def yard_truth() -> dict[str, str]:
    pages = json.loads((E / "77_scratch_reader/out/test/pages.json").read_text(encoding="utf-8"))
    out = {}
    for P in pages:
        if P["set"] != "yardstick":
            continue
        gp = {int(k): v for k, v in (P.get("gold_pos") or {}).items()}
        for r in P["lines"]:
            if r["i"] in gp:
                out[r["key"]] = P["truth"][gp[r["i"]]]
    return out


def build_map(sig_name: str = "p3t"):
    L = [json.loads(l) for l in open(OUT / "lines81.jsonl", encoding="utf-8")]
    img = {d["key"]: d for d in map(json.loads, open(OUT / "read/image.jsonl", encoding="utf-8"))}
    sg = {d["key"]: d for d in map(json.loads, open(OUT / f"read/signal_{sig_name}.jsonl", encoding="utf-8"))}
    f4 = OUT / "read/signal_p4r.jsonl"
    sg4 = {d["key"]: d for d in map(json.loads, open(f4, encoding="utf-8"))} if f4.exists() else {}
    lam4, lam4_src = lam_p4r()
    vf = OUT / "read/image_v3.jsonl"
    v3 = {d["key"]: d["v3"] for d in map(json.loads, open(vf, encoding="utf-8"))} if vf.exists() else {}
    bf = OUT / "read/image_v2b.jsonl"
    v2b = {d["key"]: d["v2b"] for d in map(json.loads, open(bf, encoding="utf-8"))} if bf.exists() else {}
    nf = OUT / "read/nuqta81.jsonl"
    nq = {d["key"]: d["nuqta"] for d in map(json.loads, open(nf, encoding="utf-8"))} if nf.exists() else {}
    sig = {}
    for f in sorted((OUT / "sig").glob("*.npz")):
        z = np.load(f)
        for k in z.files:
            if len(z[k]) >= 4:
                sig[k] = z[k]
    q = np.quantile([float(np.median(v[:, 11].astype(np.float32))) for v in sig.values()], [1 / 3, 2 / 3])
    yt = yard_truth()
    rows, c = [], Counter()
    for r in L:
        c["lines"] += 1
        if not r["cut"] or r["key"] not in img:
            c["not_cut_or_unread"] += 1
            continue
        s = r["arabic_share"]
        kind = "no_letters" if s is None else "mostly_latin" if s < 0.5 else "arabic"
        d, g = img[r["key"]], sg.get(r["key"])
        R = dict(azure=r["azure"], v1=d["v1"], v2=d["v2"], s2r=d["s2r"])
        if r["argon_page"]:
            R["argon"] = r["argon"] if r["argon"] is not None else r["azure"]
        R["f78"] = pick(d["cands"], d["s77"], d["s78"], LAM["s78"])
        R["fsig"] = pick(d["cands"], d["s77"], g["ssig"] if g else None, LAM["ssig"])
        R["sig"] = g["gsig"] if g else ""
        g4 = sg4.get(r["key"])
        if sg4:
            R["fsig4"] = pick(d["cands"], d["s77"], g4["ssig"] if g4 else None, lam4)
            R["sig4"] = g4["gsig"] if g4 else ""
        if r["key"] in v2b:
            R["v2b"] = v2b[r["key"]]
        if r["key"] in v3:
            R["v3"] = v3[r["key"]]
        if r["key"] in nq:
            R["nuqta"] = " ".join(nq[r["key"]].split())
        ink, th, blob = ink_bucket(sig[r["key"]], q) if r["key"] in sig else ("none", None, None)
        F = {k: form(v) for k, v in R.items()}
        shown = [k for k in SHOWN if k in R and k not in LATE]
        agree_all = len({F[k] for k in shown}) == 1
        row = dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], jcode=r["jcode"], year=r["year"],
                   era=r["era"], kind=kind, ink=ink, thick=th, blob=blob, yard=r["yard"], readings=R,
                   agree_all=agree_all, ours_vs_azure={k: F[k] == F["azure"] for k in OURS + ["fsig", "fsig4", "f78", "v2b", "v3", "sig", "sig4", "nuqta"] if k in F},
                   cmin77=d["cmin77"], truth=yt.get(r["key"]), azure_len=len(F["azure"]))
        if "argon" in R:
            row["ours_vs_azure"]["argon"] = F["argon"] == F["azure"]
        rows.append(row)
    with open(OUT / "readings81.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # ---- the agreement map
    A = [r for r in rows if r["kind"] == "arabic"]

    def pattern(r):
        o = r["ours_vs_azure"]
        n = sum(o[k] for k in OURS)
        F = {k: form(r["readings"][k]) for k in OURS}
        if n == 3:
            return "v1=v2=s2r=Azure"
        if n == 0:
            return "ours agree, Azure differs" if len(set(F.values())) == 1 else "ours split, none = Azure"
        return f"{n} of 3 ours = Azure"

    def summ(R):
        n = len(R)
        out = dict(lines=n)
        pc = Counter(pattern(r) for r in R)
        out["patterns_pct"] = {k: round(100 * v / n, 2) for k, v in pc.most_common()}
        out["agree_with_azure_pct"] = {k: round(100 * sum(r["ours_vs_azure"][k] for r in R) / n, 2)
                                       for k in OURS + ["fsig", "fsig4", "f78", "v2b", "v3", "sig", "sig4"] if k in R[0]["ours_vs_azure"]}
        ar = [r for r in R if "argon" in r["ours_vs_azure"]]
        if ar:
            out["agree_with_azure_pct"]["argon"] = round(100 * sum(r["ours_vs_azure"]["argon"] for r in ar) / len(ar), 2)
            out["argon_lines"] = len(ar)
        out["all_shown_agree_pct"] = round(100 * sum(r["agree_all"] for r in R) / n, 2)
        return out
    res = dict(lambda_p3t=LAM, lambda_p4r=lam4, lambda_p4r_source=lam4_src, counts=dict(c), kinds=dict(Counter(r["kind"] for r in rows)), ink_thresholds=[float(x) for x in q],
               all=summ(A), by_era={e: summ([r for r in A if r["era"] == e]) for e in sorted({r["era"] for r in A})},
               by_ink={e: summ([r for r in A if r["ink"] == e]) for e in sorted({r["ink"] for r in A})},
               by_journal={j: summ([r for r in A if r["jcode"] == j]) for j in sorted({r["jcode"] for r in A})},
               mostly_latin=summ([r for r in rows if r["kind"] == "mostly_latin"]),
               no_letters=summ([r for r in rows if r["kind"] == "no_letters"]))
    (OUT / "agree81.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: res[k] for k in ("counts", "kinds", "all", "by_era", "by_ink")}, ensure_ascii=False, indent=1))


def shown_of(r: dict, rng: random.Random):
    """Distinct readings (comparison form) of the shown readers, in random order; display text = the first reader
    with that form, in SHOWN order (Azure's punctuation first)."""
    seen = {}
    for k in SHOWN:
        if k in r["readings"]:
            fm = form(r["readings"][k])
            seen.setdefault(fm, clean_label(r["readings"][k]))
    sh = list(seen.values())
    rng.shuffle(sh)
    return sh


QUOTA_DIS = {"pre-1950": 0.16, "1950-1999": 0.50, "2000+": 0.34}
QUOTA_AGR = {"pre-1950": 0.2, "1950-1999": 0.4, "2000+": 0.4}


def sample(n_dis: int, n_agr: int):
    rows = [json.loads(l) for l in open(OUT / "readings81.jsonl", encoding="utf-8")]
    A = [r for r in rows if r["kind"] == "arabic"]
    rng = random.Random(81)
    out, frame = [], {}
    for stratum, n, Q in (("dispute", n_dis, QUOTA_DIS), ("agree", n_agr, QUOTA_AGR)):
        pools = {e: [r for r in A if r["era"] == e and (not r["agree_all"]) == (stratum == "dispute")] for e in Q}
        alloc = {e: min(len(pools[e]), int(round(n * share))) for e, share in Q.items()}
        left = n - sum(alloc.values())            # an era with too few lines gives its quota to the others
        for e in sorted(Q, key=lambda e: -len(pools[e])):
            add = min(left, len(pools[e]) - alloc[e])
            alloc[e] += add
            left -= add
        for e in Q:
            pool = pools[e]
            k = alloc[e]
            pick_ = rng.sample(pool, k)
            frame[f"{stratum}|{e}"] = dict(frame=len(pool), sampled=k)
            for r in pick_:
                out.append(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], era=e, stratum=stratum,
                                shown=shown_of(r, rng)))
    rng.shuffle(out)
    (OUT / "judge").mkdir(exist_ok=True)
    with open(OUT / "judge/sample.jsonl", "w", encoding="utf-8") as f:
        for s in out:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    (OUT / "judge/frame.json").write_text(json.dumps(frame, indent=1))
    print(json.dumps(frame, indent=1), len(out))


def sample_calib():
    """The owner's yardstick lines not already in the main sample (judge-vs-owner calibration): every disputed one
    and an equal number of agreed ones."""
    rows = [json.loads(l) for l in open(OUT / "readings81.jsonl", encoding="utf-8")]
    have = {json.loads(l)["key"] for l in open(OUT / "judge/sample.jsonl", encoding="utf-8")}
    Y = [r for r in rows if r["truth"] is not None and r["kind"] == "arabic" and r["key"] not in have]
    rng = random.Random(8181)
    dis = [r for r in Y if not r["agree_all"]]
    agr = [r for r in Y if r["agree_all"]]
    pick_ = dis + rng.sample(agr, min(len(agr), len(dis)))
    with open(OUT / "judge/calib.jsonl", "w", encoding="utf-8") as f:
        for r in pick_:
            f.write(json.dumps(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], era=r["era"],
                                    stratum="calib_" + ("dispute" if not r["agree_all"] else "agree"),
                                    shown=shown_of(r, rng)), ensure_ascii=False) + "\n")
    print("calib", len(dis), "disputed +", len(pick_) - len(dis), "agreed")


def nuqta_list(n_extra: int):
    """Lines Nuqta reads: the judged sample, the calibration lines, and n_extra more AGREE-stratum lines (era quotas
    of the agree sample, seed 8182): a two-phase sample for Nuqta's agreement with the consensus where every other
    reader agrees (most of the frame), whose conditional error the 500 judged agree lines measure."""
    rows = [json.loads(l) for l in open(OUT / "readings81.jsonl", encoding="utf-8")]
    have = [json.loads(l)["key"] for f in ("sample", "calib") for l in open(OUT / f"judge/{f}.jsonl", encoding="utf-8")]
    hs = set(have)
    rng = random.Random(8182)
    extra = []
    for e, share in QUOTA_AGR.items():
        pool = [r for r in rows if r["kind"] == "arabic" and r["agree_all"] and r["era"] == e and r["key"] not in hs]
        for r in rng.sample(pool, min(len(pool), int(round(n_extra * share)))):
            extra.append(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], era=e, stratum="nuqta_extra",
                              shown=[]))
    with open(OUT / "judge/nuqta_extra.jsonl", "w", encoding="utf-8") as f:
        for x in extra:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    (OUT / "nuqta_lines.txt").write_text("\n".join(have + [x["key"] for x in extra]) + "\n")
    print("nuqta lines", len(have) + len(extra), "extra", len(extra))


def reshow():
    """After Nuqta's readings are in readings81.jsonl: recompute the candidates shown for the sample and the
    calibration lines (Nuqta's reading added where it is a new form).  Only before judging."""
    assert not (OUT / "judge/answers.jsonl").exists(), "judging has started: the candidates are fixed"
    rows = {d["key"]: d for d in map(json.loads, open(OUT / "readings81.jsonl", encoding="utf-8"))}
    rng = random.Random(8183)
    for f in ("sample", "calib"):
        S = [json.loads(l) for l in open(OUT / f"judge/{f}.jsonl", encoding="utf-8")]
        n = 0
        for s in S:
            s["shown"] = shown_of(rows[s["key"]], rng)
            n += "nuqta" in rows[s["key"]]["readings"]
        with open(OUT / f"judge/{f}.jsonl", "w", encoding="utf-8") as fo:
            for s in S:
                fo.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f, len(S), "with nuqta", n, "mean candidates", round(sum(len(s["shown"]) for s in S) / len(S), 2))


def v3extra():
    """Judged lines where v3 (exp 83, added after judging) reads something no shown candidate and not the judge's
    truth: asked again (the same two calls) with v3's reading among the candidates; used for v3 only."""
    sys.path.insert(0, str(HERE))
    from est81 import truth_of
    rows = {d["key"]: d for d in map(json.loads, open(OUT / "readings81.jsonl", encoding="utf-8"))}
    ans = {d["key"]: d for d in map(json.loads, open(OUT / "judge/answers.jsonl", encoding="utf-8"))}
    rng = random.Random(8184)
    out = []
    for f in ("sample", "calib"):
        for s in map(json.loads, open(OUT / f"judge/{f}.jsonl", encoding="utf-8")):
            r = rows[s["key"]]
            if s["key"] not in ans or "v3" not in r["readings"]:
                continue
            T, _ = truth_of(s, ans[s["key"]])
            fv = form(r["readings"]["v3"])
            if T is None or fv == T or fv in {form(x) for x in s["shown"]}:
                continue
            sh = s["shown"] + [clean_label(r["readings"]["v3"])]
            rng.shuffle(sh)
            out.append(dict(s, shown=sh, stratum=s["stratum"]))
    with open(OUT / "judge/v3extra.jsonl", "w", encoding="utf-8") as fo:
        for s in out:
            fo.write(json.dumps(s, ensure_ascii=False) + "\n")
    print("v3extra", len(out))


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "map":
        build_map(sys.argv[2] if len(sys.argv) > 2 else "p3t")
    elif c == "sample":
        sample(int(sys.argv[2]), int(sys.argv[3]))
    elif c == "calib":
        sample_calib()
    elif c == "nuqta":
        nuqta_list(int(sys.argv[2]))
    elif c == "reshow":
        reshow()
    elif c == "v3extra":
        v3extra()


def extras():
    """Judge-free numbers: each reader's letter distance to Azure (a disagreement, not an error) by era; Nuqta's
    agreement with the consensus on the agree stratum (500 judged + 2,000 extra lines) and with Azure on its lines."""
    from rapidfuzz.distance import Levenshtein
    rows = [json.loads(l) for l in open(OUT / "readings81.jsonl", encoding="utf-8")]
    A = [r for r in rows if r["kind"] == "arabic"]
    out = {"distance_to_azure_letters_pct": {}, "nuqta": {}}
    for e in ("all", "pre-1950", "1950-1999", "2000+"):
        R = [r for r in A if e == "all" or r["era"] == e]
        d = {}
        for k in ("v1", "v2", "v2b", "v3", "s2r", "fsig", "fsig4", "f78", "sig", "sig4", "argon", "nuqta"):
            L = [r for r in R if k in r["readings"]]
            if L:
                az = [form(r["readings"]["azure"]) for r in L]
                d[k] = dict(lines=len(L), letters=round(100 * sum(Levenshtein.distance(form(r["readings"][k]), a)
                                                                  for r, a in zip(L, az)) / max(1, sum(map(len, az))), 3))
        out["distance_to_azure_letters_pct"][e] = d
        ag = [r for r in R if r["agree_all"] and "nuqta" in r["readings"]]
        out["nuqta"][e] = dict(agree_lines_read=len(ag),
                               nuqta_eq_consensus_pct=round(100 * sum(form(r["readings"]["nuqta"]) == form(r["readings"]["azure"])
                                                                      for r in ag) / max(1, len(ag)), 2))
    (OUT / "extras81.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__" and sys.argv[1] == "extras":
    extras()
