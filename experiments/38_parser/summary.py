"""Experiment 38: the headline numbers with intervals -> out/summary.json (read by make_report.py and the README).

    /home/yassine/inkscript/.venv/bin/python summary.py

Intervals: 95% percentile bootstrap over pages (each page here is from its own document but for none), 2,000 draws,
seed 38; shares (judge wins, correction precision) also with Wilson intervals.
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter

from common import OUT, pages, spent


def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - r) / d, 3), round((c + r) / d, 3)]


def boot(rows, num, den, n=2000, seed=38):
    if not rows:
        return None, [None, None]
    v = sum(num(r) for r in rows) / max(1, sum(den(r) for r in rows))
    rng = random.Random(seed)
    xs = []
    for _ in range(n):
        s = [rng.choice(rows) for _ in rows]
        xs.append(sum(num(r) for r in s) / max(1, sum(den(r) for r in s)))
    xs.sort()
    return round(v, 4), [round(xs[int(0.025 * n)], 4), round(xs[int(0.975 * n) - 1], 4)]


def main():
    M = json.loads((OUT / "measures.json").read_text(encoding="utf-8"))
    hard = {p["page_id"] for p in pages() if p["hard"]}
    gold = [m for m in M if m["gold_done"]]
    S = dict(pages=len(M), hard=len(hard), gold_done=len(gold))
    # text against the truth (gold) and against Azure (all other pages)
    for setname, rows in (("gold", gold), ("vs_azure", [m for m in M if not m["gold_done"]])):
        d = {}
        for rd in ("azure", "joined", "corrected", "dots"):
            rs = [m for m in rows if rd in m["scores"]]
            d[rd] = dict(
                cer=boot(rs, lambda m: m["scores"][rd]["faithful.char_err"], lambda m: m["scores"][rd]["faithful.chars"]),
                cer_folded=boot(rs, lambda m: m["scores"][rd]["folded.char_err"], lambda m: m["scores"][rd]["folded.chars"]),
                wer=boot(rs, lambda m: m["scores"][rd]["faithful.word_err"], lambda m: m["scores"][rd]["faithful.words"]),
                line_cer=boot(rs, lambda m: m["scores"][rd]["faithful.line_err"], lambda m: m["scores"][rd]["faithful.chars"]),
                bag_err=boot(rs, lambda m: m["scores"][rd]["bag.missing"] + m["scores"][rd]["bag.extra"],
                             lambda m: m["scores"][rd]["bag.words"]),
                bag_missing=boot(rs, lambda m: m["scores"][rd]["bag.missing"], lambda m: m["scores"][rd]["bag.words"]),
                order=boot(rs, lambda m: m["scores"][rd]["order_ok"], lambda m: m["scores"][rd]["order_pairs"]),
                dropped_lines=sum(m["scores"][rd]["dropped"] for m in rs),
                inserted_lines=sum(m["scores"][rd]["inserted"] for m in rs))
        S["text_" + setname] = d
    # corrections
    st = Counter()
    for m in M:
        for k, v in ((m.get("corrections") or {}).get("by_status") or {}).items():
            st[k] += v
    v = Counter(e["verdict"] for m in gold for e in (m.get("correction_truth") or {}).get("edits", []))
    kinds = {}
    for m in gold:
        for e in (m.get("correction_truth") or {}).get("edits", []):
            kinds.setdefault(e["kind"], Counter())[e["verdict"]] += 1
    wb = sum((m.get("correction_truth") or {}).get("word_errors_before", 0) for m in gold)
    wa = sum((m.get("correction_truth") or {}).get("word_errors_after", 0) for m in gold)
    n = v["right"] + v["wrong"] + v["neutral"]
    S["corrections"] = dict(by_status=dict(st), proposed=sum(st.values()), applied=st["applied"],
                            gold_verdicts=dict(v), gold_precision=round(v["right"] / n, 3) if n else None,
                            gold_precision_ci=wilson(v["right"], n), gold_wrong_share_ci=wilson(v["wrong"], n),
                            gold_by_kind={k: dict(c) for k, c in kinds.items()},
                            gold_word_errors_before=wb, gold_word_errors_after=wa,
                            pages_worse=[m["page_id"] for m in gold if (m.get("correction_truth") or {}).get(
                                "word_errors_after", 0) > (m.get("correction_truth") or {}).get("word_errors_before", 0)])
    # assignment
    keys = ("azure_words", "leftover_words", "words_in_pictures", "dots_blocks", "dots_blocks_no_words",
            "dots_blocks_kept_from_dots", "dots_blocks_dropped", "tables", "table_cells", "table_cells_azure",
            "table_cells_dots", "table_words_left", "formulas", "figures", "kraken_lines", "kraken_outside_blocks",
            "azure_lines_no_kraken", "dots_text_no_ink", "words_near")
    S["assignment"] = {k: sum(m["stats"].get(k, 0) for m in M) for k in keys}
    S["assignment"]["every_word_once_pages"] = sum(bool(m["stats"].get("every_word_once")) for m in M)
    # judges
    js = [json.loads(l) for l in (OUT / "judge_sides.jsonl").read_text().splitlines()] \
        if (OUT / "judge_sides.jsonl").exists() else []
    allj = js
    jg = [j for j in allj if j["key"] not in hard]
    wg = Counter(j["unblinded"]["winner"] for j in jg)
    S["judge_sides_gold"] = dict(pages=len(jg), winner=dict(wg),
                                 grade_new=round(sum(j["grade_new"] for j in jg) / max(1, len(jg)), 2),
                                 grade_old=round(sum(j["grade_old"] for j in jg) / max(1, len(jg)), 2))
    js = [j for j in allj if j["key"] in hard]
    w = Counter(j["unblinded"]["winner"] for j in js)
    asp = {}
    for j in js:
        for k, x in j["unblinded"].items():
            if k != "winner":
                asp.setdefault(k, Counter())[x] += 1
    S["judge_sides"] = dict(pages=len(js), winner=dict(w), new_wins_ci=wilson(w["new"], len(js)),
                            old_wins_ci=wilson(w["old"], len(js)),
                            grade_new=round(sum(j["grade_new"] for j in js) / max(1, len(js)), 2),
                            grade_old=round(sum(j["grade_old"] for j in js) / max(1, len(js)), 2),
                            aspects={k: dict(c) for k, c in asp.items()})
    jo = [json.loads(l) for l in (OUT / "judge_objects.jsonl").read_text().splitlines()] \
        if (OUT / "judge_objects.jsonl").exists() else []
    for kind in ("table", "formula"):
        rs = [r for r in jo if r["kind"] == kind and r.get("grades")]
        g = lambda r, k: (r["grades"].get(k) or {}).get("grade")
        S["judge_" + kind] = dict(n=len(rs), same=sum(r["same"] for r in rs),
                                  dots=round(sum(g(r, "dots") or 0 for r in rs) / max(1, len(rs)), 2),
                                  new=round(sum(g(r, "new") or 0 for r in rs) / max(1, len(rs)), 2),
                                  new_better=sum((g(r, "new") or 0) > (g(r, "dots") or 0) for r in rs),
                                  new_worse=sum((g(r, "new") or 0) < (g(r, "dots") or 0) for r in rs))
    # editions
    errs = [m["page_id"] for m in M if (m.get("edition") or {}).get("errors")]
    S["editions"] = dict(built=sum(1 for m in M if m.get("edition")), with_errors=errs)
    sp = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((OUT / "spotcheck").glob("*.json"))] \
        if (OUT / "spotcheck").exists() else []
    fc = Counter()
    for r in sp:
        for f in r.get("faults") or []:
            fc[f"{f.get('category')}|{f.get('severity')}"] += 1
    mean = lambda k: round(sum(r[k] for r in sp if isinstance(r.get(k), (int, float))) /
                           max(1, sum(isinstance(r.get(k), (int, float)) for r in sp)), 2)
    S["spotcheck"] = dict(pages=len(sp), better=dict(Counter(r.get("better") for r in sp)),
                          new_layout=mean("new_layout_score"), new_onecol=mean("new_onecol_score"),
                          old_layout=mean("old_layout_score"),
                          severity=dict(Counter(f.get("severity") for r in sp for f in r.get("faults") or [])),
                          faults=dict(fc.most_common()))
    S["gemini_usd"] = round(spent(), 3)
    (OUT / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(S, ensure_ascii=False, indent=1)[:4000])


if __name__ == "__main__":
    main()
