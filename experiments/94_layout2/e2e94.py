"""Experiment 94, goal 3: can our own line finder replace Azure's lines?  experiment 92's e2e92.py test, unchanged in
substance (truth, matching, letters wrong, page bootstrap), on the line finder's cuts.

    python e2e94.py test [VARIANT]  -> out/e2e94{V}.json, out/e2e94{V}_lines.jsonl
    python e2e94.py dev  [VARIANT]  -> out/e2e94dev{V}.json   (DEV pages; truth = agreed lines only)

Truth per Azure line (Arabic lines only, experiment 81's comparison form): judged (experiment 81's blind judge) where
it exists, else agreed (Azure's text = the reader on Azure's cut).  Our reading of a truth line: own lines whose home
is that line and lie >= 50% inside it, joined right to left; else an own line covering >= 30% of it (merged: best
substring); else missed (every letter wrong).  Line finding: one-to-one IoU >= 0.5 matching at conf 0.1 / 0.25 / 0.4.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from common94 import E, E92, OUT, area, assert_not_locked, azure_lines, inter, iou

sys.path.insert(0, str(E / "92_layout"))
sys.path.insert(0, str(E / "81_heldout_scale"))
sys.path.insert(0, str(E / "77_scratch_reader"))
from agree81 import form  # noqa: E402
from e2e92 import arabic_share, boot, match11, semiglobal  # noqa: E402
from est81 import truth_of  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from cut94 import dev_pages, own_boxes  # noqa: E402


def load_reads(*names):
    rd = {}
    for s in names:
        f = OUT / "read" / f"{s}.jsonl"
        if not f.exists():
            f = E92 / "read" / f"{s}.jsonl"
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            rd[d["key"]] = d["pred"]
    return rd


def main(which="test", var=""):
    if which == "test":
        pages = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")}
        refs = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "ref92.jsonl", encoding="utf-8")}
        pred = json.load(open(OUT / "pred94_line.json"))
        meta, rd = OUT / f"own94{var}.jsonl", load_reads("az92", f"ln94{var}")
        S = {d["key"]: d for d in map(json.loads, open(E / "81_heldout_scale/out/judge/sample.jsonl", encoding="utf-8"))}
        ans = {d["key"]: d for d in map(json.loads, open(E / "81_heldout_scale/out/judge/answers.jsonl", encoding="utf-8"))}
        tag = f"e2e94{var}"
    else:
        P = dev_pages()
        pages = {p["key"]: dict(p, era="dev", layout="dev", jcode=p["key"][:4]) for p in P}
        refs = {}
        for p in P:
            L, W, H = azure_lines(p["azure"], p["page"])
            refs[p["key"]] = dict(key=p["key"], W=W, H=H, lines=L)
        pred = json.load(open(OUT / "pred94_line_val.json"))
        meta, rd = OUT / f"own94dev{var}.jsonl", load_reads("az", f"ln94{var}")
        S, ans, tag = {}, {}, f"e2e94dev{var}"
    assert_not_locked(list(pages))
    own = defaultdict(list)
    for l in open(meta, encoding="utf-8"):
        d = json.loads(l)
        own[d["page"]].append(d)
    det = {c: [0, 0, 0] for c in (0.1, 0.25, 0.4)}
    rows = []
    for k, ref in refs.items():
        if k not in pred or k not in own:
            continue
        W, H = ref["W"], ref["H"]
        L = [x for x in ref["lines"] if x["box"]]
        azb = [x["box"] for x in L]
        for c in det:
            keep = [b for b, _, _ in own_boxes(pred[k], W, H, conf=c)]
            det[c][0] += match11(keep, azb)
            det[c][1] += len(keep)
            det[c][2] += len(azb)
        O = [o for o in own[k] if o["cut"]]
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
                T, _ = truth_of(S[lk], ans[lk])
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
                cov = [cc for cc in cov if cc[0] >= 0.3]
                if cov:
                    o = max(cov, key=lambda cc: cc[0])[1]
                    pr = form(rd.get(o["key"], ""))
                    d_own, kind = semiglobal(T, pr), "merged"
                else:
                    pr, d_own, kind = "", len(T), "missed"
            d_az = Levenshtein.distance(form(pa), T)
            pg = pages[k]
            rows.append(dict(page=k, lk=lk, src=src, kind=kind, n=len(T), d_az=d_az, d_own=d_own, era=pg["era"],
                             layout=pg["layout"], jcode=pg["jcode"], truth=T, az=form(pa), own=pr))
    out = dict(line_finding={str(c): dict(recall=round(v[0] / max(1, v[2]), 4), precision=round(v[0] / max(1, v[1]), 4),
                                          own=v[1], azure=v[2]) for c, v in det.items()})
    groups = {"all": rows, "judged": [r for r in rows if r["src"] == "judged"],
              "agreed": [r for r in rows if r["src"] == "agreed"],
              "judged_no0097": [r for r in rows if r["src"] == "judged" and r["jcode"] != "0097"]}
    for g in ("era", "layout"):
        for v in sorted({r[g] for r in rows}):
            groups[f"{g}:{v}"] = [r for r in rows if r[g] == v and r["src"] == "judged"]
    res = {}
    for g, G in groups.items():
        if not G:
            continue
        n = sum(r["n"] for r in G)
        res[g] = dict(lines=len(G), letters=n, azure_cut=round(100 * sum(r["d_az"] for r in G) / n, 3),
                      our_cut=round(100 * sum(r["d_own"] for r in G) / n, 3), diff_ci=boot(G, "d_az", "d_own"),
                      diff=round(100 * sum(r["d_own"] - r["d_az"] for r in G) / n, 3),
                      lines_wrong_azure=round(100 * sum(r["d_az"] > 0 for r in G) / len(G), 2),
                      lines_wrong_ours=round(100 * sum(r["d_own"] > 0 for r in G) / len(G), 2),
                      missed_share=round(100 * sum(r["kind"] == "missed" for r in G) / len(G), 3),
                      kinds={kk: sum(r["kind"] == kk for r in G) for kk in ("one", "split", "merged", "missed")},
                      letters_lost_by_kind={kk: round(100 * sum(r["d_own"] - r["d_az"] for r in G if r["kind"] == kk) / n, 3)
                                            for kk in ("one", "split", "merged", "missed")})
    out["reader"] = res
    json.dump(out, open(OUT / f"{tag}.json", "w"), ensure_ascii=False, indent=1)
    with open(OUT / f"{tag}_lines.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(out["line_finding"]))
    for g in ("all", "judged", "agreed", "judged_no0097"):
        if g in res:
            print(g, json.dumps(res[g], ensure_ascii=False))
    for g in res:
        if g.startswith(("era", "layout")):
            print("  ", g, res[g]["lines"], res[g]["azure_cut"], res[g]["our_cut"], res[g]["diff_ci"])


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["test"]))
