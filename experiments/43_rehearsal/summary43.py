"""Experiment 43: the summary numbers of a run over the fresh sample (no model calls).

    summary43.py --run v33_300      -> out/<run>/summary.json (totals, per article, per decade) + summary.txt

From the run's rules/ answers (after rules43), its masters (stats/, metachanges.json) and raw/ (tokens, cost):
blocks by type, another-article regions, footnotes / endnotes and calls linked, verse cuts, pictures (the model's,
found from the ink, inside a line), tables, equations, parsed references and note citations, misprints flagged (sic),
fixes (orthography-only), metadata changes (D33), lines rescued from noise / noise lines left out, cost per article
and per page by decade and length.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compare43 as CMP  # noqa: E402
import run43  # noqa: E402
from masters43 import ST  # noqa: E402

OUT = HERE / "out"
STATS = ["figures", "picture_boxes_from_ink", "inline_pictures", "inline_pictures_from_ornaments", "tables",
         "table_cells", "footnotes", "jats_endnotes", "calls_linked", "refs_parsed", "refs_element_citations",
         "refs_notes_citing", "refs_note_citations", "refs_fields_written", "refs_tidy_label_volume",
         "refs_tidy_label_issue", "refs_tidy_label_pages", "refs_tidy_year_from_date", "refs_tidy_url_joined",
         "noise_lines", "noise_lines_with_words", "noise_words", "sic_placed", "fixes_marked", "ornaments",
         "picture_junk_lines", "headings", "blocks"]


def decade(y) -> str:
    try:
        y = int(str(y)[:4])
    except Exception:
        return "?"
    return "pre-1960" if y < 1960 else f"{y // 10 * 10}s"


def length(n) -> str:
    return "1-5" if n <= 5 else "6-10" if n <= 10 else "11-15" if n <= 15 else "16-20" if n <= 20 else "21-30"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    run = args.run
    rules, mast, raw = OUT / run / "rules", OUT / run / "masters", OUT / run / "raw"
    tot, types, per, by_dec, by_len = Counter(), Counter(), {}, defaultdict(Counter), defaultdict(Counter)
    oa_regions = 0
    for a in run43.articles("b"):
        s = a["stem"]
        one = CMP.one(s, rules, mast)
        if one is None:
            tot["articles_missing"] += 1
            continue
        st = mast / "stats" / f"{s}.json"
        st = json.loads(st.read_text()) if st.exists() else {}
        mc = mast / f"{s}.metachanges.json"
        mc = json.loads(mc.read_text()).get("changes", []) if mc.exists() else []
        usd = tin = tout = 0
        for f in raw.glob(f"{s}_c*.json"):
            if f.name.endswith(".failed.json"):
                continue
            r = json.loads(f.read_text(encoding="utf-8"))
            usd += r.get("usd") or 0
            tin += r.get("tin") or 0
            tout += r.get("tout") or 0
        rescued = 0
        oa_pages = set()
        for f in rules.glob(f"{s}_c*.json"):
            r = json.loads(f.read_text(encoding="utf-8"))
            rescued += len((r.get("rules43") or {}).get("never_noise") or [])
            for pg in r["answer"].get("pages") or []:
                if any(isinstance(b, dict) and b.get("type") == "other_article" for b in pg.get("blocks") or []):
                    oa_pages.add(pg.get("page"))
        oa_regions += len(oa_pages)
        n = a.get("n") or (a["last"] - a["first"] + 1)
        types.update(one["types"])
        row = dict(year=a.get("year"), decade=decade(a.get("year")), pages=n, lang=a.get("lang"),
                   usd=round(usd, 4), tin=tin, tout=tout, meta_changes=[c.get("field") for c in mc],
                   rescued_lines=rescued, other_article_pages=len(oa_pages),
                   **{k: one[k] for k in ("calls", "linked", "footnotes", "endnotes", "cuts", "other_article", "sic",
                                          "fixes", "fixes_ortho", "fixes_diac", "body_words", "text_words")},
                   types=one["types"], stats={k: st.get(k, 0) for k in STATS})
        row["body_words"] = sum(one["body_words"].values())
        per[s] = row
        for k in ("calls", "linked", "footnotes", "endnotes", "cuts", "other_article", "sic", "fixes", "fixes_ortho",
                  "fixes_diac", "body_words", "text_words", "rescued_lines", "other_article_pages", "tin", "tout"):
            tot[k] += row[k]
        tot["usd"] += usd
        tot["pages"] += n
        tot["articles"] += 1
        tot["meta_changes"] += len(mc)
        tot["articles_meta_changed"] += bool(mc)
        for k in STATS:
            tot["st_" + k] += st.get(k, 0)
        for key, D in ((row["decade"], by_dec), (length(n), by_len)):
            D[key]["articles"] += 1
            D[key]["pages"] += n
            D[key]["usd"] += usd
            D[key]["tout"] += tout
            D[key]["tin"] += tin
    tot["other_article_pages_total"] = oa_regions
    res = dict(run=run, totals=dict(tot), block_types=dict(types.most_common()),
               by_decade={k: dict(v) for k, v in sorted(by_dec.items())},
               by_length={k: dict(v) for k, v in by_len.items()}, articles=per)
    (OUT / run / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"{run}: {tot['articles']} articles, {tot['pages']} pages, ${tot['usd']:.3f}"]
    L.append("block types: " + ", ".join(f"{k} {v}" for k, v in types.most_common()))
    L.append(json.dumps(dict(tot), ensure_ascii=False, indent=1))
    for name, D in (("decade", by_dec), ("length", by_len)):
        for k, v in sorted(D.items()):
            L.append(f"{name} {k:9} {v['articles']:4} art {v['pages']:5} pp ${v['usd']:.3f}  "
                     f"${v['usd'] / v['articles']:.4f}/art  ${v['usd'] / v['pages']:.5f}/page  "
                     f"out {v['tout'] / v['pages']:.0f}/page")
    (OUT / run / "summary.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
