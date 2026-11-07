"""Experiment 92, step 4 (d): mastheads / running headers.  The repetition rule (experiment 90's masthead90.py) against
experiment 39's furniture class, with Argon's header/footer blocks as the first reference and a hand check by eye.

    python3 masthead92.py rule    -> out/masthead92_rule.json  {line key: reason}  (every test page's band lines)
    python3 masthead92.py score   -> out/masthead92.json + out/look/masthead_sheet.html (the hand-check sheet)
    python3 masthead92.py hand    -> folds out/masthead92_hand.json (my verdicts) into out/masthead92.json

Rule: masthead90's, unchanged (band = top 12% / bottom 10% of the page; key = folded letters only, >= 4 letters;
rapidfuzz ratio >= 70; on >= 40% of the issue pool's pages (>= 3) or >= 25% of the journal pool's (>= 5)).  The
pools are every page of every held-out article on disk (experiment 76's inventory), not only the test pages; the
journal pool is used for every journal (experiment 90 used it for its locked journals).
Candidates scored: test-page lines with a key of >= 4 letters (page numbers alone are not mastheads).
- rule: the line is a repeated band line;
- r1 / r2: the layout model's label (experiment 39's way) is furniture;
- argon: Argon put the line in a header or footer block.
"""
from __future__ import annotations

import html
import json
import random
import sys
from collections import Counter, defaultdict

from common92 import E, INV, OUT, assert_not_locked, azure_lines, fixpath, heldout_codes, is_locked_any

sys.path.insert(0, str(E / "90_locked_final"))
sys.path.insert(0, str(E / "77_scratch_reader"))
from masthead90 import BOT, TOP, key_of, repeated  # noqa: E402


def band(az: str, p: int):
    lines, W, H = azure_lines(az, p)
    out = []
    for ln in lines:
        if not ln["box"]:
            continue
        if ln["box"][3] / H <= TOP or ln["box"][1] / H >= 1 - BOT:
            k = key_of(ln["text"])
            if len(k) >= 4:
                out.append((p, ln["i"], k))
    return out


def rule():
    from common92 import azure_result
    S = heldout_codes()
    docs = {}
    for l in open(INV, encoding="utf-8"):
        a = json.loads(l)
        if a["jcode"] in S and not is_locked_any(a["stem"]) and a["stem"] not in docs:
            az = fixpath(a["azure"])
            if az.exists():
                docs[a["stem"]] = str(az)
    B, NP = {}, {}
    for s, az in docs.items():
        n = len(azure_result(az)["pages"])
        B[s], NP[s] = [x for p in range(1, n + 1) for x in band(az, p)], n
    issue, journal = defaultdict(list), defaultdict(list)
    for s in docs:
        issue[s[:12]].append(s)
        journal[s[:4]].append(s)
    hits = {}
    for name, pools, share, mn in (("issue", issue, 0.40, 3), ("journal", journal, 0.25, 5)):
        for g, SS in pools.items():
            items = [(s, p, i, k) for s in SS for p, i, k in B[s]]
            for st, p, i in repeated(items, {s: NP[s] for s in SS}, share, mn):
                hits.setdefault(f"{st}_p{p:03d}_l{i:03d}", f"repeated band line ({name} pool)")
            print(name, g, len(items), len(hits), flush=True)
    json.dump(hits, open(OUT / "masthead92_rule.json", "w"), ensure_ascii=False, indent=0)
    print(len(hits), "repeated band lines in", len(docs), "articles")


def candidates():
    hits = json.load(open(OUT / "masthead92_rule.json"))
    rows = [json.loads(l) for l in open(OUT / "lines92.jsonl", encoding="utf-8")]
    out = []
    for r in rows:
        if len(key_of(r["text"])) < 4:
            continue
        lk = f"{r['key'][:-5]}_p{int(r['key'][-3:]):03d}_l{r['i']:03d}"
        out.append(dict(lk=lk, key=r["key"], i=r["i"], text=r["text"], box=r["box"], layout=r["layout"],
                        era=r["era"], jcode=r["jcode"], type=r["type"],
                        rule=lk in hits, r1=r.get("r1_label") == "furniture", r2=r.get("r2_label") == "furniture",
                        argon=r["type"] in ("header", "footer")))
    return out


def prf(C, f, ref="argon"):
    tp = sum(c[f] and c[ref] for c in C)
    fp = sum(c[f] and not c[ref] for c in C)
    fn = sum(c[ref] and not c[f] for c in C)
    P, R = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return dict(tp=tp, fp=fp, fn=fn, precision=round(P, 4), recall=round(R, 4),
                f1=round(2 * P * R / max(1e-9, P + R), 4))


def score():
    C = candidates()
    assert_not_locked([c["key"] for c in C])
    out = dict(candidates=len(C), argon_positive=sum(c["argon"] for c in C),
               vs_argon={f: prf(C, f) for f in ("rule", "r1", "r2")})
    for f in ("rule", "r1"):
        out["vs_argon"][f + "_by_journal"] = {j: prf([c for c in C if c["jcode"] == j], f)
                                              for j in sorted({c["jcode"] for c in C})}
    out["union_rule_r1"] = prf([dict(c, u=c["rule"] or c["r1"]) for c in C], "u")
    # hand-check sample: per pattern of (rule, r1, argon), up to 12 lines
    rnd = random.Random(92)
    pat = defaultdict(list)
    for c in C:
        pat[(c["rule"], c["r1"], c["argon"])].append(c)
    out["patterns"] = {str(k): len(v) for k, v in sorted(pat.items())}
    sample = []
    for k, v in sorted(pat.items()):
        if k == (False, False, False):
            pass                                       # negatives are sampled too
        rnd.shuffle(v)
        sample += v[:12]
    json.dump(sample, open(OUT / "masthead92_sample.json", "w"), ensure_ascii=False, indent=0)
    json.dump(out, open(OUT / "masthead92.json", "w"), ensure_ascii=False, indent=1)
    sheet(sample)
    print(json.dumps({k: out[k] for k in ("candidates", "argon_positive", "patterns", "union_rule_r1")}))
    print(json.dumps({f: out["vs_argon"][f] for f in ("rule", "r1", "r2")}))


def sheet(sample):
    """Each sampled line: the top or bottom quarter of its page with the line boxed, for the eye."""
    import cv2
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "pages92.jsonl", encoding="utf-8")}
    refs = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "ref92.jsonl", encoding="utf-8")}
    d = OUT / "look/masthead"
    d.mkdir(parents=True, exist_ok=True)
    cells = []
    for n, c in enumerate(sample):
        img = cv2.imread(str(OUT / "pages" / f"{c['key']}.jpg"), cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        W, H = refs[c["key"]]["W"], refs[c["key"]]["H"]
        x0, y0, x1, y1 = c["box"]
        X0, Y0, X1, Y1 = int(x0 / W * w), int(y0 / H * h), int(x1 / W * w), int(y1 / H * h)
        cv2.rectangle(img, (X0 - 3, Y0 - 3), (X1 + 3, Y1 + 3), (0, 0, 255), 2)
        top = max(0, Y0 - int(0.12 * h))
        crop = img[top:min(h, Y1 + int(0.12 * h))]
        f = d / f"{n:03d}.jpg"
        cv2.imwrite(str(f), crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
        cells.append(f'<div><b>{n:03d}</b> {c["lk"]} rule={int(c["rule"])} r1={int(c["r1"])} argon={int(c["argon"])} '
                     f'({html.escape(str(c["type"]))})<br><img src="masthead/{f.name}" width="640"></div>')
    (OUT / "look/masthead_sheet.html").write_text("<meta charset=utf-8>" + "\n".join(cells), encoding="utf-8")
    _ = pages


def hand():
    out = json.load(open(OUT / "masthead92.json"))
    S = json.load(open(OUT / "masthead92_sample.json"))
    V = json.load(open(OUT / "masthead92_hand.json"))      # {"000": true/false (a running header / masthead)}
    for n, c in enumerate(S):
        c["truth"] = V.get(f"{n:03d}")
    S = [c for c in S if c["truth"] is not None]
    out["hand"] = dict(n=len(S), **{f: prf(S, f, "truth") for f in ("rule", "r1", "r2", "argon")})
    # per pattern: how often the line was truly a masthead -> corrected estimate on every candidate
    C = [dict(c, **{"rule|r1": c["rule"] or c["r1"], "rule|r2": c["rule"] or c["r2"]}) for c in candidates()]
    share = defaultdict(list)
    for c in S:
        share[(c["rule"], c["r1"], c["argon"])].append(c["truth"])
    est = {}
    for f in ("rule", "r1", "r2", "argon", "rule|r1", "rule|r2"):
        tp = fp = fn = 0.0
        for c in C:
            v = share.get((c["rule"], c["r1"], c["argon"]))
            p = sum(v) / len(v) if v else float(c["argon"])
            tp += c[f] * p
            fp += c[f] * (1 - p)
            fn += (not c[f]) * p
        P, R = tp / max(1e-9, tp + fp), tp / max(1e-9, tp + fn)
        est[f] = dict(precision=round(P, 4), recall=round(R, 4), f1=round(2 * P * R / max(1e-9, P + R), 4))
    out["hand_weighted_estimate"] = est
    out["hand_by_pattern"] = {str(k): [sum(v), len(v)] for k, v in sorted(share.items())}
    json.dump(out, open(OUT / "masthead92.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out["hand"]), json.dumps(est), json.dumps(out["hand_by_pattern"]))


if __name__ == "__main__":
    {"rule": rule, "score": score, "hand": hand}[sys.argv[1]]()
