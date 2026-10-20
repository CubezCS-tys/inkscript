"""Experiment 43: score the judge on the calibration pages (judge_truth43.json) — per problem type caught / missed /
false alarms, and how its confidence lines up with being right. No model calls.

    python3 judge_calib43.py [--dirs gemini-3.8-flash gemini-4-argon ...]   -> out/judge/calib.json + table on stdout

A finding counts as catching a known problem when its type is one of the problem's types, or when
judge_verdicts43.json says so (a finding with another label whose evidence names the problem, checked on the
picture). A finding that catches nothing is "new, real" / "debatable" / a false alarm by judge_verdicts43.json
(looked at on the scan beside our page); a finding nobody looked at is counted as a false alarm.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
J = HERE / "out" / "judge"
MIN_CONF = 0.5


def load(d: str, run: str, page: str):
    s, p = page.rsplit(":", 1)
    f = J / "answers" / d / run / f"{s}_p{int(p):03d}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


def score(d: str, truth: dict, verdicts: dict) -> dict:
    caught, missed, fa, new, deb = Counter(), Counter(), Counter(), Counter(), Counter()
    conf_bins = defaultdict(lambda: [0, 0])          # bin -> [right, all]
    pages_none_ok = pages_none = 0
    rows, usd, n = [], 0.0, 0
    for t in truth["pages"]:
        rec = load(d, t["run"], t["page"])
        if rec is None:
            continue
        n += 1
        usd += rec.get("usd") or 0
        probs = [(k, x) for k, x in enumerate((rec["answer"] or {}).get("problems") or [], 1)
                 if float(x.get("confidence") or 0) >= MIN_CONF]
        used = set()
        for i, tp in enumerate(t["problems"]):
            hit = [k for k, x in probs if x["type"] in tp["types"]]
            hit += [k for k, x in probs if verdicts.get(f"{d}|{t['page']}|{k}", {}).get("catches") == i]
            key = tp["types"][0]
            if hit:
                caught[key] += 1
                used |= set(hit)
            else:
                missed[key] += 1
        for k, x in probs:
            v = verdicts.get(f"{d}|{t['page']}|{k}", {})
            b = "≥0.9" if x["confidence"] >= 0.9 else "0.7–0.9" if x["confidence"] >= 0.7 else "0.5–0.7"
            right = k in used or v.get("verdict") == "real"
            conf_bins[b][0] += right
            conf_bins[b][1] += 1
            if k in used:
                continue
            {"real": new, "debatable": deb}.get(v.get("verdict"), fa)[x["type"]] += 1
            rows.append(dict(page=t["page"], n=k, type=x["type"], conf=x["confidence"], verdict=v.get("verdict", "false"),
                             note=v.get("note", ""), evidence=x.get("evidence", "")[:160]))
        if not t["problems"]:
            pages_none += 1
            pages_none_ok += not probs
    return dict(dir=d, pages=n, usd=round(usd, 4), usd_page=round(usd / max(n, 1), 4), caught=dict(caught),
                missed=dict(missed), false_alarms=dict(fa), new_real=dict(new), debatable=dict(deb),
                clean_pages_said_none=f"{pages_none_ok}/{pages_none}",
                confidence={b: f"{r}/{a} right" for b, (r, a) in sorted(conf_bins.items())}, unmatched=rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", default=["gemini-3.8-flash", "gemini-4-argon"])
    a = ap.parse_args()
    truth = json.loads((HERE / "judge_truth43.json").read_text(encoding="utf-8"))
    vf = HERE / "judge_verdicts43.json"
    verdicts = json.loads(vf.read_text(encoding="utf-8"))["verdicts"] if vf.exists() else {}
    res = [score(d, truth, verdicts) for d in a.dirs]
    (J / "calib.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    types = sorted({k for r in res for f in ("caught", "missed", "false_alarms", "new_real", "debatable") for k in r[f]})
    print(f"{'type':18}" + "".join(f"{r['dir'][:26]:>34}" for r in res))
    print(f"{'':18}" + "".join(f"{'caught/known  false  new-real  deb':>34}" for _ in res))
    for t in types:
        print(f"{t:18}" + "".join(f"{str(r['caught'].get(t, 0)) + '/' + str(r['caught'].get(t, 0) + r['missed'].get(t, 0)):>21}"
                                  f"{r['false_alarms'].get(t, 0):>5}{r['new_real'].get(t, 0):>6}{r['debatable'].get(t, 0):>4}"
                                  for r in res))
    for r in res:
        print(f"{r['dir']}: {r['pages']} pages, ${r['usd']} (${r['usd_page']}/page); clean pages answered none "
              f"{r['clean_pages_said_none']}; confidence {r['confidence']}")


if __name__ == "__main__":
    main()
