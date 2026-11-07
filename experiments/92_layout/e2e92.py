"""Experiment 92, step 7 (c): can our own line boxes replace Azure's?  Line finding against Azure's lines, and the
decisive end-to-end test: the final reader on lines cut from OUR boxes vs from Azure's polygons, letters wrong.

    python3 e2e92.py   -> out/e2e92.json (+ printed), out/e2e92_lines.jsonl (per truth line, for the pictures)

Truth per Azure line (comparison form = experiment 81's agree81.form: no_punct, every letter counted):
- judged: experiment 81's blind-judge truth (est81.truth_of) where the line was in its judged sample;
- agreed: else, Azure's text when the final reader on Azure's own cut reads the same (form).  On these lines the
  Azure cut is right by construction, so they measure only what OUR cut loses.
Only Arabic lines (Arabic letters >= 50% of letters), as experiment 81's frame.
Our reading of a truth line L: every own line is given the Azure line holding most of its area ("home");
- own lines whose home is L and which lie >= 50% inside it, joined right to left -> edit distance to T;
- else an own line covering >= 30% of L (L merged into a neighbour's box) -> the best substring match (semi-global
  edit distance: L's own letters only; the merged neighbour pays for the extra text);
- else missed: every letter of T wrong.
Line finding: own lines matched one-to-one to Azure lines (greedy by IoU, >= 0.5) at conf 0.25, and at 0.1 / 0.4.
95% intervals: 1,000 bootstrap draws of pages.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict

from common92 import E, LABELS, OUT, area, assert_not_locked, inter, iou

sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "77_scratch_reader"))
from agree81 import form  # noqa: E402
from est81 import truth_of  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402

READ = ("r1",)   # the reader ran on round 1's cuts only (round 2's read was stopped to save time; its detection is scored)
AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
LETTER = re.compile(r"[^\W\d_]")


def arabic_share(s: str) -> float:
    L = LETTER.findall(s or "")
    return sum(bool(AR.match(c)) for c in L) / len(L) if L else 0.0


def semiglobal(t: str, p: str) -> int:
    """Edit distance of t to the best-matching substring of p."""
    if not t:
        return 0
    prev = [0] * (len(p) + 1)
    for i, a in enumerate(t, 1):
        cur = [i] + [0] * len(p)
        for j, b in enumerate(p, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a != b))
        prev = cur
    return min(prev)


def match11(own, az, thr=0.5):
    pairs = sorted(((iou(o, a), j, i) for j, o in enumerate(own) for i, a in enumerate(az) if iou(o, a) >= thr),
                   reverse=True)
    uo, ua, n = set(), set(), 0
    for _, j, i in pairs:
        if j not in uo and i not in ua:
            uo.add(j)
            ua.add(i)
            n += 1
    return n


def boot(rows, f_a, f_b, B=1000):
    pages = sorted({r["page"] for r in rows})
    by = defaultdict(list)
    for r in rows:
        by[r["page"]].append(r)
    S = {p: (sum(r[f_a] for r in by[p]), sum(r[f_b] for r in by[p]), sum(r["n"] for r in by[p])) for p in pages}
    rnd = random.Random(92)
    d = []
    for _ in range(B):
        a = b = n = 0
        for p in (rnd.choice(pages) for _ in pages):
            a, b, n = a + S[p][0], b + S[p][1], n + S[p][2]
        d.append(100 * (b - a) / max(1, n))
    d.sort()
    return [round(d[int(0.025 * B)], 3), round(d[int(0.975 * B)], 3)]


def main():
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "pages92.jsonl", encoding="utf-8")}
    refs = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "ref92.jsonl", encoding="utf-8")}
    assert_not_locked(list(pages))
    own = defaultdict(list)
    for l in open(OUT / "own92.jsonl", encoding="utf-8"):
        d = json.loads(l)
        own[(d["page"], d["src"])].append(d)
    rd = {}
    for s in ("az92", "r192"):
        for l in open(OUT / "read" / f"{s}.jsonl", encoding="utf-8"):
            d = json.loads(l)
            rd[d["key"]] = d["pred"]
    S = {d["key"]: d for d in map(json.loads, open(E / "81_heldout_scale/out/judge/sample.jsonl", encoding="utf-8"))}
    ans = {d["key"]: d for d in map(json.loads, open(E / "81_heldout_scale/out/judge/answers.jsonl", encoding="utf-8"))}
    out, rows = {}, []
    det = {m: {c: [0, 0, 0] for c in (0.1, 0.25, 0.4)} for m in ("r1", "r2")}
    Y = {m: json.load(open(OUT / f"yolo92_{m}.json")) for m in ("r1", "r2")}
    for k, ref in refs.items():
        W, H = ref["W"], ref["H"]
        L = [x for x in ref["lines"] if x["box"]]
        azb = [x["box"] for x in L]
        for m in ("r1", "r2"):
            for c in det[m]:
                from score92 import CONF  # noqa: F401
                p = Y[m][k]
                B = sorted(((b[0] * W, b[1] * H, b[2] * W, b[3] * H), s) for b, s in zip(p["boxes"], p["conf"]) if s >= c)
                B.sort(key=lambda x: -x[1])
                keep = []
                for b in B:
                    if all(iou(b[0], q) <= 0.5 for q in keep):
                        keep.append(b[0])
                det[m][c][0] += match11(keep, azb)
                det[m][c][1] += len(keep)
                det[m][c][2] += len(azb)
        for m in READ:
            O = [o for o in own[(k, m)] if o["cut"]]
            home = {}
            for o in O:
                best = max(range(len(L)), key=lambda i: inter(o["box"], L[i]["box"]), default=None)
                if best is not None and inter(o["box"], L[best]["box"]) > 0:
                    home[o["key"]] = (best, inter(o["box"], L[best]["box"]) / max(1e-9, area(o["box"])))
            for i, x in enumerate(L):
                lk = f"{k}_l{x['i']:03d}"
                if arabic_share(x["text"]) < 0.5:
                    continue
                pa = rd.get(lk)
                if pa is None:
                    continue
                if lk in ans and lk in S:
                    T, why = truth_of(S[lk], ans[lk])
                    src = "judged"
                    if T is None:
                        continue
                elif form(x["text"]) == form(pa):
                    T, src = form(x["text"]), "agreed"
                else:
                    continue
                if not T:
                    continue
                G = [o for o in O if home.get(o["key"], (None,))[0] == i and home[o["key"]][1] >= 0.5]
                if G:
                    G.sort(key=lambda o: -o["box"][2])
                    pr = form(" ".join(rd.get(o["key"], "") for o in G))
                    d_own, kind = Levenshtein.distance(pr, T), ("one" if len(G) == 1 else "split")
                else:
                    cov = [(inter(o["box"], x["box"]) / max(1e-9, area(x["box"])), o) for o in O]
                    cov = [c for c in cov if c[0] >= 0.3]
                    if cov:
                        o = max(cov, key=lambda c: c[0])[1]
                        pr = form(rd.get(o["key"], ""))
                        d_own, kind = semiglobal(T, pr), "merged"
                    else:
                        pr, d_own, kind = "", len(T), "missed"
                d_az = Levenshtein.distance(form(pa), T)
                rows.append(dict(page=k, lk=lk, m=m, src=src, kind=kind, n=len(T), d_az=d_az, d_own=d_own,
                                 era=pages[k]["era"], layout=pages[k]["layout"], jcode=pages[k]["jcode"],
                                 truth=T, az=form(pa), own=pr, coarse=x["coarse"]))
    out["line_finding"] = {m: {str(c): dict(recall=round(v[0] / max(1, v[2]), 4), precision=round(v[0] / max(1, v[1]), 4),
                                            own=v[1], azure=v[2]) for c, v in d.items()} for m, d in det.items()}
    res = {}
    for m in READ:
        R = [r for r in rows if r["m"] == m]
        d = {}
        groups = {"all": R, "judged": [r for r in R if r["src"] == "judged"], "agreed": [r for r in R if r["src"] == "agreed"]}
        for g in ("era", "layout"):
            for v in sorted({r[g] for r in R}):
                groups[f"{g}:{v}"] = [r for r in R if r[g] == v and r["src"] == "judged"]
        groups["judged_no0097"] = [r for r in R if r["src"] == "judged" and r["jcode"] != "0097"]
        for g, G in groups.items():
            if not G:
                continue
            n = sum(r["n"] for r in G)
            d[g] = dict(lines=len(G), letters=n, azure_cut=round(100 * sum(r["d_az"] for r in G) / n, 3),
                        our_cut=round(100 * sum(r["d_own"] for r in G) / n, 3),
                        diff_ci=boot(G, "d_az", "d_own"),
                        lines_wrong_azure=round(100 * sum(r["d_az"] > 0 for r in G) / len(G), 2),
                        lines_wrong_ours=round(100 * sum(r["d_own"] > 0 for r in G) / len(G), 2),
                        kinds={kk: sum(r["kind"] == kk for r in G) for kk in ("one", "split", "merged", "missed")},
                        letters_lost_by_kind={kk: round(100 * sum(r["d_own"] - r["d_az"] for r in G if r["kind"] == kk) / n, 3)
                                              for kk in ("one", "split", "merged", "missed")})
        res[m] = d
    out["reader"] = res
    json.dump(out, open(OUT / "e2e92.json", "w"), ensure_ascii=False, indent=1)
    with open(OUT / "e2e92_lines.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(out["line_finding"]))
    for m in res:
        for g in ("all", "judged", "agreed", "judged_no0097"):
            if g in res[m]:
                print(m, g, json.dumps(res[m][g], ensure_ascii=False))
        for g in res[m]:
            if g.startswith(("era", "layout")):
                print("  ", m, g, res[m][g]["lines"], res[m][g]["azure_cut"], res[m][g]["our_cut"], res[m][g]["diff_ci"])
    _ = LABELS


if __name__ == "__main__":
    main()
