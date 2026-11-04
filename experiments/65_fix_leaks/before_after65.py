"""Experiment 65: experiment 61's audit before and after the fixes, row by row.

    before_after65.py [--before out/audit_before_check/audit.json] [--after out/audit_after/audit.json]
        -> out/before_after.json + out/before_after.md

"before" is experiment 61's audit run again with this experiment's audit code (the new homes and --release/--out
options, which find nothing in the old masters: 1 line of 435,270 moves) on the release R20261023T005909;
"after" is the same code on the candidate DB (the *_fix61 runs current).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def row_key(r):
    return (r["field"], r["kind"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(HERE / "out" / "audit_before_check" / "audit.json"))
    ap.add_argument("--after", default=str(HERE / "out" / "audit_after" / "audit.json"))
    ap.add_argument("--outdir", default=str(HERE / "out"), help="experiment 68: where before_after.json / .md go")
    a = ap.parse_args()
    B = json.loads(Path(a.before).read_text(encoding="utf-8"))
    A = json.loads(Path(a.after).read_text(encoding="utf-8"))
    md = ["## Totals (lines)", "", "| prompt | articles | lines | a field | b generic | c not article text | d nowhere | "
          "accounted |", "|---|---|---|---|---|---|---|---|"]
    for v in ("v2", "v3.3", "v3.5b", "all"):
        for tag, X in (("before", B), ("after", A)):
            t = X["totals"].get(v)
            if not t:
                continue
            lb = t["lines_by_bucket"]
            md.append(f"| {v} {tag} | {t['articles']} | {t['lines']:,} | {lb.get('a', 0):,} | {lb.get('b', 0):,} | "
                      f"{lb.get('c', 0):,} | {lb.get('d', 0):,} | {t['accounted_lines']}% |")
    rb = {row_key(r): r for r in B["leak_table"]}
    ra = {row_key(r): r for r in A["leak_table"]}
    md += ["", "## Leak table (lines that fell through; articles)", "",
           "| what it is | kind | before lines (articles) | after lines (articles) | change |", "|---|---|---|---|---|"]
    rows = []
    for k in sorted(set(rb) | set(ra), key=lambda k: -(rb.get(k, {}).get("lines", 0))):
        b, x = rb.get(k, {}), ra.get(k, {})
        lab = (b or x).get("label", k[0])
        rows.append(dict(field=k[0], kind=k[1], label=lab, before=b.get("lines", 0), before_articles=b.get("articles", 0),
                         after=x.get("lines", 0), after_articles=x.get("articles", 0)))
        md.append(f"| {lab} | {k[1]} | {b.get('lines', 0)} ({b.get('articles', 0)}) | {x.get('lines', 0)} "
                  f"({x.get('articles', 0)}) | {x.get('lines', 0) - b.get('lines', 0):+d} |")
    kinds = {}
    for k in ("mapping", "not_asked", "gemini_missed"):
        kinds[k] = (sum(r["before"] for r in rows if r["kind"] == k), sum(r["after"] for r in rows if r["kind"] == k))
    md += ["", "By kind: " + "; ".join(f"{k} {b} -> {a_}" for k, (b, a_) in kinds.items())]
    md += ["", "## Bilingual pairs (all prompts)", "", "| pair | printed both | both in JATS | linked | both in platform |",
           "|---|---|---|---|---|"]
    for p in ("title", "names", "affiliations", "positions", "abstracts", "keywords"):
        b, x = B["bilingual"][p]["all"], A["bilingual"][p]["all"]
        md.append(f"| {p} | {b['printed_both']} -> {x['printed_both']} | {b['jats_both']} -> {x['jats_both']} | "
                  f"{b['linked']} -> {x['linked']} | {b['platform_both']} -> {x['platform_both']} |")
    md += ["", "## Answer accounting (values Gemini returned that are not in their field)", "",
           "| answer key | returned | not in its field before | after |", "|---|---|---|---|"]
    ab = {r["key"]: r for r in B["answers"]}
    aa = {r["key"]: r for r in A["answers"]}

    def notin(r):
        return sum((r.get(s) or {}).get("n", 0) for s in ("flattened", "dropped", "elsewhere")) if r else 0
    for k in sorted(set(ab) | set(aa), key=lambda k: -notin(ab.get(k))):
        if notin(ab.get(k)) or notin(aa.get(k)):
            md.append(f"| {k} | {(ab.get(k) or aa.get(k)).get('total')} | {notin(ab.get(k))} | {notin(aa.get(k))} |")
    wb = {r["key"]: r for r in B["works"]}
    wa = {r["key"]: r for r in A["works"]}
    md += ["", "Parsed reference parts dropped: " + ", ".join(
        f"{k} {wb[k]['dropped']} -> {wa.get(k, {}).get('dropped')}" for k in wb if wb[k]["dropped"])]
    cb = {(r["table"], r["column"]): r for r in B["columns"]}
    ca = {(r["table"], r["column"]): r for r in A["columns"]}
    md += ["", "## Platform columns no current article filled (before) and what they hold after", "",
           "| column | before filled | after filled |", "|---|---|---|"]
    for k, r in cb.items():
        if r["filled"] == 0:
            md.append(f"| {k[0]}.{k[1]} | 0 | {ca.get(k, {}).get('filled', '-')} |")
    out = dict(rows=rows, kinds=kinds, totals_before=B["totals"], totals_after=A["totals"])
    (Path(a.outdir) / "before_after.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(a.outdir) / "before_after.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
