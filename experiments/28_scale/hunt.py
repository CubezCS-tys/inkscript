"""Failure hunt: rank the weakest documents and pages by each metric and sort what looks wrong into kinds.

    .venv/bin/python experiments/28_scale/hunt.py      -> out/hunt.json (and a printed digest)

Reads out/set/summary.json and pages.json (summarize.py) and each document's Azure JSON (for what a page holds:
a table, a sideways page, how many words Azure gave it). Classification here is mechanical; every kind was then
looked at on rendered pages (out/look/) before it went into the README and showcase.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from summarize import name_sim

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"; SET = OUT / "set"
summ = json.loads((SET / "summary.json").read_text())
pages = json.loads((SET / "pages.json").read_text())
docs = {d["doc"]: d for d in summ["docs"]}
NUM = re.compile(r"^[\d٠-٩۰-۹.,٫٬%/()\-–:+*×=|]+$")


def azure_pages(stem):
    j = json.loads((OUT / "azure" / stem / f"{stem}.json").read_text())
    return j.get("analyzeResult", j)["pages"]


_az = {}


def page_kind(stem, n):
    """table: many short lines, a good share of them numbers; sparse: few words."""
    if stem not in _az:
        try: _az[stem] = azure_pages(stem)
        except Exception: _az[stem] = []
    ps = _az[stem]
    if n - 1 >= len(ps): return "?"
    lines = [l.get("content", "") for l in ps[n - 1].get("lines", [])]
    if not lines: return "empty"
    short = sum(1 for l in lines if len(l.split()) <= 2)
    nums = sum(1 for l in lines if l.split() and all(NUM.match(w) for w in l.split()))
    if len(lines) >= 12 and short / len(lines) >= 0.5 and nums / len(lines) >= 0.2: return "table"
    if len(lines) >= 12 and short / len(lines) >= 0.6: return "short lines (list, table of text, index)"
    return "prose"


def main():
    B = [d for d in summ["docs"] if d.get("built")]
    res = {}
    r = lambda a, b: a / b if b else None
    # documents ranked
    rank = lambda f, rev=False, n=15: [(d["doc"], round(f(d), 4)) for d in sorted((d for d in B if f(d) is not None), key=f, reverse=rev)[:n]]
    res["weakest_docs"] = dict(
        letters=rank(lambda d: r(d["letters_cut"], d["letters_words"])),
        flagged=rank(lambda d: r(d["flagged"] or 0, d["assessed"] or 0), True),
        lines_in_order=rank(lambda d: r(d["in_order"], d["lines"])),
        words_intact=rank(lambda d: r(d["intact"], d["words"])),
        s_per_page=rank(lambda d: r(d.get("wall_s") or 0, d["pages"]), True),
        peak_mb=rank(lambda d: d.get("peak_mb"), True),
        inversions_per_page=rank(lambda d: r(d.get("inversions") or 0, d["pages"]), True),
        quotes_differ=rank(lambda d: d.get("quotes_differ") or 0, True))
    # pages ranked (pages with enough words to mean something)
    P = [p for p in pages if p["words"] >= 40]
    res["weakest_pages"] = dict(
        letters=[(p["doc"], p["page"], round(p["cut"] / (p["cut"] + p["whole"]), 3), p["cut"] + p["whole"]) for p in
                 sorted((p for p in P if p["cut"] + p["whole"] >= 30), key=lambda p: p["cut"] / (p["cut"] + p["whole"]))[:25]],
        flagged=[(p["doc"], p["page"], round(p["flagged"] / p["alto_words"], 3), p["alto_words"], p["why"]) for p in
                 sorted((p for p in P if p["alto_words"]), key=lambda p: -p["flagged"] / p["alto_words"])[:25]],
        lines=[(p["doc"], p["page"], p["in_order"], p["lines"], p["reversed"]) for p in
               sorted((p for p in P if p["lines"] >= 5), key=lambda p: p["in_order"] / p["lines"])[:25]],
        intact=[(p["doc"], p["page"], p["intact"], p["words"]) for p in sorted(P, key=lambda p: p["intact"] / p["words"])[:25]])
    # joins-lines warning, page by page, by what the page holds
    jl = [p for p in pages if p["lines_layer"] >= 8 and p["lines_pdfium"] < 0.8 * p["lines_layer"]]
    kinds = Counter(); ex = defaultdict(list)
    for p in jl:
        k = page_kind(p["doc"], p["page"]); kinds[k] += 1
        lio = p["in_order"] / p["lines"] if p["lines"] else 1
        ex[k].append((p["doc"], p["page"], p["lines_pdfium"], p["lines_layer"], round(lio, 3)))
    res["joins_lines_pages"] = dict(total=len(jl), docs=len({p["doc"] for p in jl}), by_kind=dict(kinds),
                                    examples={k: sorted(v, key=lambda x: x[2] / x[3])[:12] for k, v in ex.items()},
                                    prose_with_lines_out_of_order=[x for x in ex.get("prose", []) if x[4] < 0.95])
    # front matter
    tw = []
    for d in B:
        if not d.get("cat_title"): continue
        ji = d.get("jats_info") or {}
        if (d.get("title_sim") or 0) < 0.6:
            tw.append(dict(doc=d["doc"], sim=d.get("title_sim"), jats=ji.get("title", ""), catalogue=d["cat_title"],
                           source=ji.get("title_source", ""), title_file=d.get("title_file")))
    res["title_wrong"] = tw
    res["title_wrong_by_source"] = dict(Counter(("file" if t["title_file"] else "layout") + (":empty" if not t["jats"] else ":other") for t in tw))
    res["title_by_source"] = dict(file=[sum(1 for d in B if d.get("title_file") and d.get("cat_title") and (d.get("title_sim") or 0) >= .6),
                                        sum(1 for d in B if d.get("title_file") and d.get("cat_title"))],
                                  layout=[sum(1 for d in B if not d.get("title_file") and d.get("cat_title") and (d.get("title_sim") or 0) >= .6),
                                          sum(1 for d in B if not d.get("title_file") and d.get("cat_title"))])
    aw = []
    for d in B:
        ji = d.get("jats_info") or {}
        wrong = [y for y in ji.get("authors", []) if d.get("cat_authors") and not any(name_sim(x, y) >= .6 for x in d["cat_authors"])]
        missed = [x for x in d.get("cat_authors") or [] if not any(name_sim(x, y) >= .6 for y in ji.get("authors", []))]
        if wrong or missed:
            aw.append(dict(doc=d["doc"], jats=ji.get("authors", []), catalogue=d.get("cat_authors"), wrong=wrong, missed=missed))
    res["authors_off"] = aw
    jt = Counter((d.get("jats_info") or {}).get("journal_title", "") for d in B)
    res["journal_titles"] = dict(found=sum(1 for d in B if (d.get("jats_info") or {}).get("journal_title")),
                                 right=sum(1 for d in B if (d.get("jats_info") or {}).get("journal_title") and _sim(d["journal"], d["jats_info"]["journal_title"]) >= .6),
                                 examples_wrong=[(d["doc"], d["jats_info"]["journal_title"], d["journal"]) for d in B
                                                 if (d.get("jats_info") or {}).get("journal_title") and _sim(d["journal"], d["jats_info"]["journal_title"]) < .6][:30])
    # failures of the build itself
    res["crashed"] = [(d["doc"], d["status"], (d.get("traceback") or "")[-600:]) for d in summ["docs"] if d["status"] not in (None, "0", "124")]
    res["timeouts"] = [d["doc"] for d in summ["docs"] if d["status"] == "124"]
    res["enrich_errors"] = [(d["doc"], d["enrich_error"]) for d in B if d.get("enrich_error")]
    res["xml_invalid"] = [d["doc"] for d in B if d.get("jats_valid") is not True or d.get("alto_valid") is not True]
    res["trust_pdf_bad"] = [d["doc"] for d in B if d.get("trust_pdfs_ok") is not True]
    res["lost_image"] = [(d["doc"], d["lost_image"]) for d in B if d.get("lost_image")]
    res["reversed_lines"] = [(d["doc"], d["reversed"]) for d in B if d.get("reversed")]
    res["no_words"] = [d["doc"] for d in B if not d.get("words")]
    res["born_digital_pages"] = [(d["doc"], d["born_digital_pages"], d["pages"]) for d in B if d.get("born_digital_pages")]
    (OUT / "hunt.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    for k, v in res.items():
        s = json.dumps(v, ensure_ascii=False)
        print(f"== {k}: {s[:700]}")


def _sim(a, b):
    import difflib
    L = lambda s: re.sub(r"[^ء-ي0-9a-zA-Z]", "", re.sub("[أإآٱ]", "ا", re.sub(r"[ًٌٍَُِّْـٰ]", "", s or "")).replace("ة", "ه").replace("ى", "ي"))
    a, b = L(a), L(b)
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a and b else 0.0


if __name__ == "__main__":
    main()
