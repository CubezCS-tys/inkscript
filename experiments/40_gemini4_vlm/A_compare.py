"""Approach A: per-page and summed comparison of variants from their score_sample.json, on the pages each has."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
R = HERE / "out/A_oneshot"

def summ(rows, a0=None):
    def s(k): return sum((r.get(k) or 0) for r in rows)
    def ratio(a, b): return round(s(a) / s(b), 4) if s(b) else None
    return dict(pages=len(rows), cer_az=ratio("az.f_err", "az.f_chars"), cer_gold=ratio("gold.f_err", "gold.f_chars"),
                inv=round(1000 * s("az.invented") / max(1, s("az.ref_words")), 1),
                inv_az=round(1000 * s("az.invented_az") / max(1, s("az.ref_words")), 1),
                drop=round(1000 * s("az.dropped") / max(1, s("az.ref_words")), 1),
                rep=round(1000 * s("az.repeated") / max(1, s("az.ref_words")), 1),
                lay=ratio("lay_text_ok", "lay_n"), laybox=ratio("lay_box_ok", "lay_n"),
                order=ratio("order_ok", "order_pairs"), usd=round(s("usd"), 4))

variants = sys.argv[1:] or ["lo_hi", "hi_hi", "lo_uh", "lo_med", "md_uh"]
data = {}
for v in variants:
    f = R / v / "score_sample.json"
    rows = json.loads(f.read_text())["rows"]
    have = {p.stem for p in (R / v).glob("*.html")}
    data[v] = {r["page_id"]: r for r in rows if r["page_id"] in have}
common = set.intersection(*(set(d) for d in data.values()))
print("pages in common:", len(common))
for v in variants:
    print(f"{v:8}", summ([data[v][p] for p in sorted(common)]))
print("\nper page cer_az / invented / dropped (counts):")
for p in sorted(common):
    print(p[:28].ljust(28), "  ".join(
        f"{v}:{(data[v][p]['az.f_err'] or 0)/max(1,data[v][p]['az.f_chars']):.3f}/{data[v][p]['az.invented']}/{data[v][p]['az.dropped']}"
        for v in variants))
