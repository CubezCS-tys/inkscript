"""Experiment 43: the fresh sample after the fetch. Measures the catalogue articles' layouts on their Azure JSON (the
same features as sample43.py's local 186), checks every article is usable, swaps thin strata (verse, equations) and
unusable articles from the reserve, and writes the final sample43.json. No model calls.

    .venv/bin/python fetched43.py measure     -> out/fetch/measure43.json (catalogue + reserve features, checks)
    .venv/bin/python fetched43.py check       -> out/fetch/check43.json   (every article of sample43.json)
    .venv/bin/python fetched43.py swap        -> sample43.json (final), out/fetch/swaps43.json, prints the strata

Usable = the PDF opens, its page count = Azure's pages, Azure's JSON loads with 1-30 pages, a year (the catalogue's
when the article's own record has none). Layout features: sample43.page_feats (tables, two columns, verse);
equations for a fetched article = a page with >= 2 lines that look like maths (experiment 39's MATH rule, its
round-2 "maths page"); French / English = the catalogue's language and a Latin share > 0.3; shared = the catalogue
range test. The proposal sample43.json is kept as out/fetch/sample43_proposal.json before the first swap.
Reserve JSONs are fetched to out/fetch/reserve/<id>/ (JSON only); a reserve article swapped in moves to
out/fetch/<id>/ and gets its PDF.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample43 as S  # noqa: E402

FETCH = S.FETCH
RES = FETCH / "reserve"
MAIN = HERE.parents[1]
AWS = str(MAIN / ".venv/bin/aws")
MATH = re.compile(r"[=+×÷√∑∫±≤≥<>^∆Δαβγσμλπ]")             # experiment 34 features.MATH (39's maths lines)
AR = re.compile("[ء-ي]")
LAYOUTS = ("verse", "tables", "equations", "two_columns", "french", "english", "shared")
TARGET = dict(verse=25, equations=20)                         # sample43.QUOTA's
# Contact sheets by eye (out/fetch/sheets/: each flagged article's best page by the rule), 2026-10-19. The formula
# rule fires on statistics tables, "alpha <= 0.05", calendars and quoted "a"="b"; experiment 39's loose maths flag on
# the local articles fired on references and tables. An article has the equations flag only if a page shows formulas
# (worked arithmetic counts); verse flags are kept unless the page is not verse.
EYE = {"equations": {"yes": {"1541-006-001-030", "0315-000-015-001", "2483-000-004-013", "0168-029-002-020",
                             "0814-008-024-002", "1147-000-010-003", "0527-055-002-016", "0314-030-003-009",
                             "1993-010-001-013"}},
       "verse": {"no": {"0412-005-001-005"}}}                 # a list of libraries in two columns


def eye(stem: str, flags: list[str]) -> list[str]:
    out = [f for f in flags if f != "equations" or stem in EYE["equations"]["yes"]]
    return [f for f in out if f != "verse" or stem not in EYE["verse"]["no"]]


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def jdump(p: Path, obj):
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


FORMULA = re.compile(r"\S\s*[=≤≥≈≠]\s*\S|[∑∫√∂]")
URL = re.compile(r"https?:|www\.|[?&]\w+=|\.(com|org|net)\b")


def math_page(pg: dict) -> int:
    """Lines that look like a formula on one page: experiment 39's maths line (a MATH symbol, at most 30% Arabic
    letters, >= 3 characters) that also has a relation with something on both sides (=, <=, ...) or a sum, integral or
    root, and is not a web address (the loose rule alone took URLs, "3.34x" ratios and Greek quotations)."""
    m = 0
    for ln in pg.get("lines", []):
        t = (ln.get("content") or "").strip()
        s = t.replace(" ", "")
        m += (bool(MATH.search(t)) and len(AR.findall(t)) <= 0.3 * len(s) and len(t) >= 3
              and bool(FORMULA.search(t)) and not URL.search(t))
    return m


def measure_json(stem: str, azure: Path) -> dict:
    a = jl(azure)
    a = a.get("analyzeResult", a)
    pages = a.get("pages", [])
    pf = [S.page_feats(p) for p in pages]
    n = len(pages)
    txt = a.get("content", "")
    ar = len(re.findall(r"[؀-ۿ]", txt))
    la = len(re.findall(r"[A-Za-zÀ-ɏ]", txt))
    mp = [math_page(p) for p in pages]
    c, _ = S.catalogue()
    rec = c.get(stem) or {}
    lang = rec.get("lang")
    lang = (lang[0] if isinstance(lang, list) and lang else str(lang or "")).strip("[]' ")
    lat = round(la / max(1, ar + la), 3)
    year = str(rec.get("year") or "")[:4]
    return dict(stem=stem, azure_pages=n, tables=sum(f["grid"] for f in pf) >= 1,
                two_columns=sum(f["two_col"] for f in pf) >= max(1, n // 3), verse=sum(f["verse"] for f in pf) >= 1,
                equations=max(mp or [0]) >= 2, math_lines=sum(mp), french=lang == "fre" and lat > 0.3,
                english=lang == "eng" and lat > 0.3, lang=lang, latin_share=lat, shared=S.shared_by_catalogue(stem),
                year=year if year.isdigit() else None, journal_code=stem[:4],
                journal=(rec.get("journal") or {}).get("title") if isinstance(rec.get("journal"), dict) else None,
                printed=rec.get("pages"), lines=sum(f["lines"] for f in pf))


def pdf_pages(pdf: Path) -> int | str:
    try:
        import pymupdf
        with pymupdf.open(pdf) as d:
            return d.page_count
    except Exception as e:
        return f"{type(e).__name__}: {e}"


def problems(azure: Path, pdf: Path, year) -> tuple[list[str], dict]:
    out, info = [], {}
    if not Path(azure).exists():
        return ["no Azure JSON"], info
    if not Path(pdf).exists():
        return ["no PDF"], info
    try:
        a = jl(azure)
        a = a.get("analyzeResult", a)
        na = len(a.get("pages", []))
    except Exception as e:
        return [f"Azure JSON unreadable: {type(e).__name__}"], info
    npdf = pdf_pages(pdf)
    info.update(azure_pages=na, pdf_pages=npdf)
    if isinstance(npdf, str):
        out.append(f"PDF does not open: {npdf}")
    elif npdf != na:
        out.append(f"PDF {npdf} pages, Azure {na}")
    if not 1 <= na <= S.MAX_PAGES:
        out.append(f"{na} pages")
    if not (year and str(year)[:4].isdigit()):
        out.append("no year")
    return out, info


def fetch_one(stem: str, d: Path, exts=("pdf", "json")) -> list[str]:
    d.mkdir(parents=True, exist_ok=True)
    got = []
    for ext in exts:
        f = d / f"{stem}.{ext}"
        if not f.exists():
            subprocess.run([AWS, "s3", "cp", "--quiet", f"s3://mandumah-source-docs/{stem}/{stem}.{ext}", str(f)],
                           timeout=900)
        if f.exists():
            got.append(ext)
    return got


# ------------------------------------------------------------------------------------------------ steps

def reserve_ids(s: dict) -> list[str]:
    """The proposal's reserve (100), then reserve2 (200 more from the same catalogue draw, kept only if the corpus
    listing of experiment 19 holds them, evened over decades; seed 4343): 34 of the first 100 are not in the bucket."""
    r2 = FETCH / "reserve2_ids.txt"
    extra = [l.strip() for l in r2.read_text().splitlines() if l.strip()] if r2.exists() else []
    return list(s["reserve"]) + [x for x in extra if x not in s["reserve"]]


def cmd_measure():
    p = FETCH / "sample43_proposal.json"
    s = jl(p if p.exists() else HERE / "sample43.json")
    f = FETCH / "measure43.json"
    m = jl(f) if f.exists() else {}
    todo = [(a["stem"], Path(a["azure"]), Path(a["pdf"]), "sample") for a in s["articles"] if a["source"] != "local"]
    todo += [(st, RES / st / f"{st}.json", RES / st / f"{st}.pdf", "reserve") for st in reserve_ids(s)]
    for st, az, pdf, where in todo:
        if st in m and "error" not in m[st]:
            continue
        if not az.exists():
            m[st] = dict(stem=st, where=where, error="no Azure JSON")
            continue
        try:
            m[st] = dict(measure_json(st, az), where=where)
        except Exception as e:
            m[st] = dict(stem=st, where=where, error=f"{type(e).__name__}: {e}")
        jdump(f, m)
    jdump(f, m)
    for where in ("sample", "reserve"):
        xs = [x for x in m.values() if x["where"] == where and "error" not in x]
        print(where, len(xs), "measured,", sum("error" in x for x in m.values() if x["where"] == where), "errors;",
              {k: sum(1 for x in xs if x.get(k)) for k in LAYOUTS},
              "decades", dict(sorted(Counter(S.decade(x["year"]) or "unknown" for x in xs).items())))


def cmd_check():
    p = FETCH / "sample43_proposal.json"
    s = jl(p if p.exists() else HERE / "sample43.json")
    m = jl(FETCH / "measure43.json")
    c, _ = S.catalogue()
    res = {}
    for a in s["articles"]:
        year = a.get("year")
        ysrc = "sample"
        if not (year and str(year)[:4].isdigit()):
            y = str((c.get(a["stem"]) or {}).get("year") or "")[:4]
            year, ysrc = (y, "catalogue") if y.isdigit() else (None, None)
        p, info = problems(Path(a["azure"]), Path(a["pdf"]), year)
        if a["source"] != "local" and a["stem"] in m and "azure_pages" in m[a["stem"]]:
            info["catalogue_pages"] = a.get("pages_total")
        res[a["stem"]] = dict(source=a["source"], problems=p, year=year, year_source=ysrc, **info)
    jdump(FETCH / "check43.json", res)
    bad = {k: v for k, v in res.items() if v["problems"]}
    print(len(res), "checked;", len(bad), "unusable;", Counter(p.split(":")[0] if "pages" not in p else re.sub(r"\d+", "N", p)
                                                       for v in bad.values() for p in v["problems"]))
    print("years from the catalogue:", sum(v["year_source"] == "catalogue" for v in res.values()))
    for k, v in bad.items():
        print(" ", k, v["source"], v["problems"])


def art_of_measure(x: dict, why: str, folder: Path) -> dict:
    n = x["azure_pages"]
    return dict(stem=x["stem"], kind="whole", first=1, last=n, pages_total=n, n=n,
                pdf=str(folder / f"{x['stem']}.pdf"), azure=str(folder / f"{x['stem']}.json"),
                decade=S.decade(x["year"]), year=x["year"], journal=x["journal"], why=why,
                flags=eye(x["stem"], [k for k in LAYOUTS if x.get(k)]), source="catalogue", printed_pages=x.get("printed"))


def rare(a: dict) -> bool:
    return any(f in a["flags"] for f in ("verse", "equations", "tables", "two_columns", "shared", "french", "english"))


def cmd_swap():
    prop = FETCH / "sample43_proposal.json"
    if not prop.exists():
        shutil.copy(HERE / "sample43.json", prop)
    s = jl(prop)
    m = jl(FETCH / "measure43.json")
    chk = jl(FETCH / "check43.json")
    arts = []
    for a in s["articles"]:
        a = dict(a)
        ck = chk[a["stem"]]
        if a["source"] != "local" and "error" not in m[a["stem"]]:
            x = m[a["stem"]]
            a = dict(art_of_measure(x, a["why"], FETCH / a["stem"]), journal=a["journal"] or x["journal"])
        if ck.get("year") and not a.get("year"):
            a["year"], a["decade"] = ck["year"], S.decade(ck["year"])
            a["year_source"] = "catalogue"
        if a["source"] == "local" and not ck["problems"]:       # the fetched articles' formula rule, on the local too
            j = jl(a["azure"])
            j = j.get("analyzeResult", j)
            if max([math_page(p) for p in j.get("pages", [])] or [0]) >= 2 and "equations" not in a["flags"]:
                a["flags"] = [k for k in LAYOUTS if k in a["flags"] or k == "equations"]
                a["equations_by"] = "formula rule (fetched43)"
        a["flags"] = eye(a["stem"], a["flags"])
        a.pop("equations_by", None)
        a["usable"] = not ck["problems"]
        a["problems"] = ck["problems"]
        arts.append(a)
    swaps = []
    per_j = Counter(a["stem"][:4] for a in arts)
    pool = [m[st] for st in reserve_ids(s) if st in m and "error" not in m[st] and 1 <= m[st]["azure_pages"] <= S.MAX_PAGES
            and m[st]["year"]]
    pool = [dict(x, equations=x["stem"] in EYE["equations"]["yes"],
                 verse=x["verse"] and x["stem"] not in EYE["verse"]["no"]) for x in pool]
    used = set()

    def out_candidate(dec, keep_rare=True):
        xs = [a for a in arts if not a.get("swapped_in") and not rare(a) and a["usable"]]
        xs.sort(key=lambda a: a["source"] == "catalogue")           # a catalogue article goes first (taken from the end)
        same = [a for a in xs if a["decade"] == dec]
        if same:
            return same[-1]
        cnt = Counter(a["decade"] for a in arts)
        return max(xs, key=lambda a: cnt[a["decade"]]) if xs else None

    def take_in(x, why, out):
        folder = FETCH / x["stem"]
        if not folder.exists():
            shutil.move(str(RES / x["stem"]), str(folder))
        got = fetch_one(x["stem"], folder)
        p, info = problems(folder / f"{x['stem']}.json", folder / f"{x['stem']}.pdf", x["year"])
        used.add(x["stem"])
        if p:
            swaps.append(dict(in_=x["stem"], rejected=p, got=got))
            return False
        new = dict(art_of_measure(x, why, folder), usable=True, problems=[], swapped_in=True)
        i = arts.index(out)
        arts[i] = new
        per_j[out["stem"][:4]] -= 1
        per_j[x["stem"][:4]] += 1
        swaps.append(dict(out=out["stem"], out_source=out["source"], out_decade=out["decade"],
                          out_why=out.get("problems") or "no rare layout", out_flags=out["flags"],
                          **{"in": x["stem"]}, in_decade=new["decade"], in_flags=new["flags"], why=why))
        jdump(FETCH / "swaps43.json", swaps)
        return True

    # 1. unusable articles: a reserve article of the same decade (a thin layout first)
    for a in [a for a in arts if not a["usable"]]:
        cands = [x for x in pool if x["stem"] not in used and per_j[x["stem"][:4]] < S.PER_JOURNAL]
        lang = [k for k in ("french", "english") if k in a["flags"]]
        cands.sort(key=lambda x: (bool(lang) and not any(x[k] for k in lang), S.decade(x["year"]) != a["decade"],
                                  not (x["verse"] or x["equations"])))
        for x in cands:
            if take_in(x, f"replaces unusable {a['stem']} ({'; '.join(a['problems'])})", a):
                break
    # 2. thin layouts: verse, equations
    for k, q in TARGET.items():
        for x in pool:
            if sum(1 for a in arts if k in a["flags"]) >= q:
                break
            if x["stem"] in used or not x[k] or per_j[x["stem"][:4]] >= S.PER_JOURNAL:
                continue
            out = out_candidate(S.decade(x["year"]))
            if out is None:
                break
            take_in(x, f"reserve, layout: {k}", out)
    for a in arts:
        a.pop("usable", None)
        if not a.get("problems"):
            a.pop("problems", None)
        a.pop("swapped_in", None)
    still_bad = [a["stem"] for a in arts if a.get("problems")]
    reserve_left = [st for st in reserve_ids(s) if st not in used and st in m and "error" not in m[st]]
    strata = dict(articles=len(arts), local=sum(a["source"] == "local" for a in arts),
                  catalogue=sum(a["source"] != "local" for a in arts), pages=sum(a["n"] for a in arts),
                  chunks=sum(-(-a["n"] // 10) for a in arts), journals=len({a["stem"][:4] for a in arts}),
                  max_per_journal=max(Counter(a["stem"][:4] for a in arts).values()),
                  decades=dict(sorted(Counter(a["decade"] or "unknown" for a in arts).items())),
                  layouts={k: sum(1 for a in arts if k in a["flags"]) for k in LAYOUTS},
                  layouts_by_source={src: {k: sum(1 for a in arts if k in a["flags"] and (a["source"] == "local") == (src == "local"))
                                           for k in LAYOUTS} for src in ("local", "catalogue")},
                  pages_hist=dict(sorted(Counter(min(30, -(-a["n"] // 5) * 5) for a in arts).items())),
                  swaps=len([w for w in swaps if "out" in w]), unusable_left=still_bad,
                  proposal_counts=s["counts"])
    jdump(HERE / "sample43.json", dict(
        made="experiment 43 sample43.py (seed 43) + fetched43.py (catalogue layouts measured, checks, swaps); final",
        counts=strata, articles=arts, reserve=reserve_left))
    jdump(FETCH / "swaps43.json", swaps)
    print(json.dumps({k: v for k, v in strata.items() if k != "proposal_counts"}, ensure_ascii=False, indent=1))
    for w in swaps:
        print(w)


if __name__ == "__main__":
    {"measure": cmd_measure, "check": cmd_check, "swap": cmd_swap}[sys.argv[1]]()
