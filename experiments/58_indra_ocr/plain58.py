"""Experiment 58: the "plain page skips Gemini" design, measured.  No calls.

    /home/appuser/inkscript/.venv/bin/python plain58.py   -> out/plain_scores.json and a printout

Inputs: out/layout_lines.jsonl (every Azure line with Gemini's role and Indra's label, score58_layout.py), Indra's
pages (out/indra/lay300), and Gemini's answers (exp 43 v33_300b_fix3 rules: note calls, fixes, page-break joins).

A page is "plain" by rules that use only free signals (Indra's labels, Azure's lines and boxes, Indra vs Azure words):
  R1  Indra-plain: every Indra block is Text / Section-Header / Page-Header / Page-Footer; not page 1
  R2  R1 and one column (Azure geometry), no line in the lower 45% that starts with a note marker or is set smaller
      than the page's body lines, no note-call pattern in the text ((1), (١), [3] ...), no two lines side by side
  R3  R2 and not the article's last page, Indra and Azure agree on >= 92% of the page's words (folded), and no
      Section-Header (a page with a heading goes to Gemini)
  R4  R3 without the heading condition
  R2b R2 without the small-line test (it fires on most pages); R2c R2b with note-call patterns allowed
For each: pages covered, what Gemini found on them that the skip would lose (roles, note calls, Argon's fixes,
page-break joins, order), and the money (cost58.py token shares, v3.5b $0.0094 a page Batch, 15.9 pages a document).
"""
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

from inkscript.gold.text import folded

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from hybrid58 import ok, G2C, I2C, SIMPLE, COMPLEX_G, side_by_side, kendall  # noqa: E402

RULES = E / "43_rehearsal/out/v33_300b_fix3/rules"
CALL = re.compile(r"[\(\[]\s*[0-9٠-٩]{1,3}\s*[\)\]]|[¹²³⁴⁵⁶⁷⁸⁹⁰]")
MARK = re.compile(r"^\s*[\(\[]?\s*[0-9٠-٩]{1,3}\s*[\)\]\-\.]")
PAGE_USD, IN_IMG, IN_AZ, IN_PROMPT, OUT_TOK = 0.0094, 1295, 1268, 801, 892


def gemini_extras():
    """page id -> calls, fixes, continued blocks, last page of its article."""
    ex = defaultdict(Counter)
    last = {}
    for f in RULES.glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        a = d["answer"]
        stem = d["stem"]
        last[stem] = max(last.get(stem, 0), max(p["page"] for p in a["pages"]))
        for p in a["pages"]:
            pid = f"{stem}_p{p['page']:03d}"
            for b in p["blocks"]:
                ex[pid]["calls"] += len(b.get("calls") or [])
                ex[pid]["continued"] += bool(b.get("continued"))
        for fx in a.get("fixes") or []:
            pg = str(fx.get("line", "")).split(":")[0]
            if pg.isdigit():
                ex[f"{stem}_p{int(pg):03d}"]["fixes"] += 1
    return ex, last


def main():
    ex, last = gemini_extras()
    rows = []
    for line in open(OUT / "layout_lines.jsonl", encoding="utf-8"):
        pg = json.loads(line)
        L = pg["lines"]
        stem, p = pg["id"].rsplit("_p", 1)
        p = int(p)
        W, H = pg["W"], pg["H"]
        labs = {l["lab"] for l in L if l["lab"] != "none"}
        gts = Counter(l["g"] for l in L)
        hs = [l["px"][3] - l["px"][1] for l in L if l["lab"] == "Text"]
        med = st.median(hs) if hs else 0
        small_low = sum(1 for l in L if l["px"][1] > 0.55 * H and med and (l["px"][3] - l["px"][1]) < 0.85 * med)
        mark_low = sum(1 for l in L if l["px"][1] > 0.55 * H and MARK.match(l["t"]))
        calls_txt = sum(len(CALL.findall(l["t"])) for l in L)
        narrow = sum(1 for l in L if (l["px"][2] - l["px"][0]) < 0.45 * W)
        onecol = narrow <= 0.3 * max(len(L), 1)
        sbs = side_by_side(L, W) if onecol else 99
        ind = json.loads((OUT / "indra/lay300" / f"{pg['id']}.json").read_text())
        a = Counter(folded(" ".join(l["t"] for l in L)).split())
        b = Counter(folded(" ".join(l["text"] for l in ind["lines"])).split())
        n = sum(a.values()) + sum(b.values())
        tdis = (n - 2 * sum((a & b).values())) / n if n else 1.0
        LL = [l for l in L if l["g"] != "noise"]
        agree = sum(ok(l["g"], l["lab"]) for l in LL)
        head_miss = sum(1 for l in LL if G2C.get(l["g"]) == "heading" and I2C.get(l["lab"]) != "heading")
        head_extra = sum(1 for l in LL if G2C.get(l["g"]) != "heading" and I2C.get(l["lab"]) == "heading")
        furn_miss = sum(1 for l in LL if G2C.get(l["g"]) == "furniture" and I2C.get(l["lab"]) != "furniture")
        seq = sorted([l for l in L if l["go"] is not None and l["io"] is not None and l["g"] not in ("header", "footer")],
                     key=lambda l: l["go"])
        kc, pairs = kendall([l["io"] for l in seq]) if len(seq) < 400 else (None, 0)
        rows.append(dict(id=pg["id"], p=p, last=p == last.get(stem), labs=sorted(labs), n=len(LL), agree=agree,
                         head_miss=head_miss, head_extra=head_extra, furn_miss=furn_miss,
                         g_extra=sorted(set(gts) & COMPLEX_G), g_counts={k: gts[k] for k in set(gts) & COMPLEX_G},
                         calls=ex[pg["id"]]["calls"], fixes=ex[pg["id"]]["fixes"], cont=ex[pg["id"]]["continued"],
                         kc=kc, small_low=small_low, mark_low=mark_low, calls_txt=calls_txt, onecol=onecol, sbs=sbs,
                         tdis=round(tdis, 4), has_head="Section-Header" in labs))
    R1 = lambda r: r["labs"] and set(r["labs"]) <= SIMPLE and r["p"] != 1
    R2 = lambda r: R1(r) and r["onecol"] and r["sbs"] == 0 and r["small_low"] == 0 and r["mark_low"] == 0 and r["calls_txt"] == 0
    R2b = lambda r: R1(r) and r["onecol"] and r["sbs"] == 0 and r["mark_low"] == 0 and r["calls_txt"] == 0
    R2c = lambda r: R1(r) and r["onecol"] and r["sbs"] == 0 and r["mark_low"] == 0
    R4 = lambda r: R2(r) and not r["last"] and r["tdis"] < 0.08
    R3 = lambda r: R4(r) and not r["has_head"]
    tot_calls = sum(r["calls"] for r in rows)
    tot_fixes = sum(r["fixes"] for r in rows)
    res = dict(pages=len(rows), total_calls=tot_calls, total_fixes=tot_fixes, rules={})
    unit = (IN_IMG + IN_AZ + IN_PROMPT) / 1e6 + OUT_TOK * 5 / 1e6
    for name, R in (("R1 Indra-plain, not page 1", R1), ("R2 + one column, no notes, no calls, no verse", R2),
                    ("R2b = R2 without the small-line test", R2b), ("R2c = R2b but note-call patterns allowed", R2c),
                    ("R3 + not last page, Indra~Azure words, no heading", R3), ("R4 = R3 but headings allowed", R4)):
        rs = [r for r in rows if R(r)]
        k = len(rs)
        kk = [r for r in rs if r["kc"] is not None]
        lines = sum(r["n"] for r in rs)
        saved = k / len(rows) * ((IN_IMG + IN_AZ) / 1e6 + OUT_TOK * 5 / 1e6) / unit
        res["rules"][name] = dict(
            pages=k, share=round(k / len(rows), 4), lines=lines,
            line_roles_differ=round(1 - sum(r["agree"] for r in rs) / max(lines, 1), 4),
            pages_every_line_agrees=round(sum(r["agree"] == r["n"] for r in rs) / max(k, 1), 4),
            gemini_plain_pages=round(sum(not r["g_extra"] for r in rs) / max(k, 1), 4),
            gemini_found_pages={t: sum(t in r["g_extra"] for r in rs) for t in
                                ("footnote", "verse", "list_item", "caption", "figure", "reference", "byline",
                                 "abstract", "other_article", "table", "equation", "boxed", "quote")},
            gemini_found_lines=dict(sum((Counter(r["g_counts"]) for r in rs), Counter()).most_common(12)),
            headings_missed_lines=sum(r["head_miss"] for r in rs), headings_extra_lines=sum(r["head_extra"] for r in rs),
            running_heads_missed_lines=sum(r["furn_miss"] for r in rs),
            note_calls_lost=sum(r["calls"] for r in rs), note_calls_lost_share=round(sum(r["calls"] for r in rs) / max(tot_calls, 1), 4),
            argon_fixes_lost=sum(r["fixes"] for r in rs), argon_fixes_lost_share=round(sum(r["fixes"] for r in rs) / max(tot_fixes, 1), 4),
            page_break_joins_on_pages=sum(r["cont"] for r in rs),
            order_identical_pages=round(sum(r["kc"] >= 0.9999 for r in kk) / max(len(kk), 1), 4),
            order_below_090_pages=sum(r["kc"] < 0.9 for r in kk),
            saving_share=round(saved, 4), usd_page=round(PAGE_USD * (1 - saved), 5),
            usd_saved_per_1M_docs=round(PAGE_USD * saved * 15.9e6),
            usd_saved_per_1M_docs_after_1_dec=round(2 * PAGE_USD * saved * 15.9e6))
    r1 = [r for r in rows if R1(r)]
    res["R1_pages_failing"] = {c: sum(f(r) for r in r1) for c, f in (
        ("two columns", lambda r: not r["onecol"]), ("side-by-side lines", lambda r: r["onecol"] and r["sbs"] > 0),
        ("small lines low on the page", lambda r: r["small_low"] > 0), ("note marker low on the page", lambda r: r["mark_low"] > 0),
        ("note-call pattern in text", lambda r: r["calls_txt"] > 0), ("last page", lambda r: r["last"]),
        ("Indra vs Azure words >= 8%", lambda r: r["tdis"] >= 0.08))}
    (OUT / "plain_rows.json").write_text(json.dumps(rows, ensure_ascii=False))
    (OUT / "plain_scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
