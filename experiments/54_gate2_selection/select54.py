"""Experiment 54 step 6: the candidate table, the recommended set, the cheaper set, their cost, and the owner's page.
Reads out/articles.tsv, out/candidates.json, out/wordcheck.json, out/journals.json. No model calls.
-> out/selection.json, out/candidates.md, out/gate2_selection.html"""
import collections, csv, html, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
Y0, Y1 = 2010, 2025
YEARS = list(range(Y0, Y1 + 1))
SCAN_PAGE = 0.0108          # v3.5b incl. judge (gate 1 real: $24.24 / 2,439 pages = $0.0099)
SCAN_PAGE_WORST = 0.0140    # +30%: gate 1's dry run said $0.0117 a page, plus rechunks and retries
WORD_EXP, WORD_LO, WORD_WORST = 0.02, 0.01, 0.05   # exp 53: lean $0.010 (Flash) - $0.028 (Argon); full Argon $0.050

CANDIDATES = ("0130 0165 0011 0233 0523 0139 0246 1182 0097 0840 1192 0013 0085 0040 0151 1158 0990 1001 0082 0080 "
              "1029 0056 0121 0175 1428 0181 0232 0038 0073 0157 1167 1443 0219 1631 0054 0532 0118").split()
RECOMMENDED = "0130 0165 0011 0523 1001 0246 1182 0097 0840 0013".split()
CHEAPER = "0130 0165 0011 0097 0840".split()
WHY = {
    "0130": "Gate 1's journal, made complete: its 2010–2016 and 2020–2022 years come from Word files (175 articles; 10 of 10 sampled pass the first-page check).",
    "0165": "The closest topic to 0130 (childhood; Arab Council for Childhood and Development, Cairo). 0130 cites it from 10 articles (17 catalogue links) and names it 14 times; 33 shared authors.",
    "0011": "The Arab Bureau of Education for the Gulf States' journal, pan-Gulf. Cited by 6 0130 articles; shares 44–95 authors with the Gulf and Bahrain/Kuwait journals.",
    "0523": "Sultan Qaboos University, Oman. 35 authors shared with 0130 and 100 with 0233, 92 with 0246: the set's Gulf hub. Cheap: 17 pages an article.",
    "1001": "Taibah University's journal of educational sciences (Medina), small and cheap (19 pages an article). Shares 30 authors with 0011, 21 with 0523 and 17 with 1182; cited by 2 0130 articles. The swap if a UAE journal is wanted: 0233 (435 articles, about $95, 22 authors shared with 0130).",
    "0246": "Journal of the Association of Arab Universities for Education and Psychology (Damascus). Shares 139 authors with Damascus University's journal (0139) and 92 with 0523; a Levant crossroads at half 0139's cost.",
    "1182": "Al-Quds Open University's educational and psychological journal (Palestine, from 2013). Cited by 6 0130 articles; shares 66 authors with 0523 and 54 with 0246.",
    "0097": "ALECSO's Arab Journal of Education (Tunis), pan-Arab. Shares 30–41 authors with 0139, 0246 and 0233; cited by 3 0130 articles.",
    "0840": "دراسات نفسية (Algeria): the Maghreb's psychology side, small and cheap; shares 41 authors with 1192 and 25 with 1428, the Algerian education journals.",
    "0013": "دراسات نفسية (Egyptian Psychologists' Association, Ranm): cited by 7 0130 articles (13 links) and named 11 times; shares 115 authors with 0118 and 69 with 0175. Long articles (47 pages).",
}


def load():
    C = json.load(open(HERE / "out/candidates.json"))
    WC = json.load(open(HERE / "out/wordcheck.json")) if (HERE / "out/wordcheck.json").exists() else {}
    pages = collections.Counter()
    for r in csv.DictReader(open(HERE / "out/articles.tsv"), delimiter="\t"):
        if r["route"] != "scan" or not (Y0 <= int(r["year"]) <= Y1):
            continue
        k = r["journal_code"]
        try:
            p = int(r["page_last"]) - int(r["page_first"]) + 1
            p = p if 0 < p <= 200 else C[k]["mean_pages"]
        except (TypeError, ValueError):
            p = C[k]["mean_pages"]
        pages[k] += p
    for k, c in C.items():
        c["scan_pages"] = round(pages[k])
        w = WC.get(k, {}).values()
        c["wc_checked"] = len(w)
        c["wc_same"] = sum(1 for x in w if str(x["word_start"]) == str(x["cat_first"]))
        c["wc_diff"] = sum(1 for x in w if isinstance(x["word_start"], int) and str(x["word_start"]) != str(x["cat_first"]))
        c["wc_title"] = sum(1 for x in w if (x.get("title_share") or 0) >= .6)
        c["cost_exp"] = c["scan_pages"] * SCAN_PAGE + c["word"] * WORD_EXP
        c["cost_lo"] = c["scan_pages"] * SCAN_PAGE + c["word"] * WORD_LO
        c["cost_worst"] = c["scan_pages"] * SCAN_PAGE_WORST + c["word"] * WORD_WORST
    return C


def totals(C, codes):
    t = dict(journals=len(codes), n=0, scan=0, word=0, nowhere=0, scan_pages=0, cost_exp=0.0, cost_lo=0.0, cost_worst=0.0)
    for k in codes:
        for f in ("n", "scan", "word", "nowhere", "scan_pages", "cost_exp", "cost_lo", "cost_worst"):
            t[f] += C[k][f]
    t["max_share"] = max(C[k]["n"] for k in codes) / t["n"]
    t["scan_cost"] = t["scan_pages"] * SCAN_PAGE
    t["word_cost"] = t["word"] * WORD_EXP
    for f in ("cost_exp", "cost_lo", "cost_worst", "scan_cost", "word_cost", "max_share"):
        t[f] = round(t[f], 3 if f == "max_share" else 2)
    return t


def internal_shared(codes):
    J = json.load(open(HERE / "out/journals.json"))
    A = {k: set(J[k]["authority_ids"]) for k in codes}
    pairs = [(a, b, len(A[a] & A[b])) for i, a in enumerate(codes) for b in codes[i + 1:]]
    return pairs


REGION = {"الكويت": "Gulf", "السعودية": "Gulf", "الإمارات": "Gulf", "سلطنة عمان": "Gulf", "البحرين": "Gulf", "قطر": "Gulf",
          "اليمن": "Gulf", "مصر": "Egypt", "السودان": "Egypt", "سوريا": "Levant", "الأردن": "Levant", "فلسطين": "Levant",
          "لبنان": "Levant", "العراق": "Levant", "تونس": "Maghreb", "الجزائر": "Maghreb", "المغرب": "Maghreb", "ليبيا": "Maghreb"}
EN = {"الكويت": "Kuwait", "السعودية": "Saudi Arabia", "الإمارات": "UAE", "سلطنة عمان": "Oman", "البحرين": "Bahrain",
      "قطر": "Qatar", "اليمن": "Yemen", "مصر": "Egypt", "سوريا": "Syria", "الأردن": "Jordan", "فلسطين": "Palestine",
      "تونس": "Tunisia", "الجزائر": "Algeria", "المغرب": "Morocco", "العراق": "Iraq", "السودان": "Sudan"}


def page(C, rec, alt, tr, ta, pairs):
    e = html.escape
    order = rec + [k for k in CANDIDATES if k not in rec]

    def cell(c, y):
        b = c["by_year"].get(str(y), {})
        n = sum(b.values())
        if not n:
            return '<td class="g none" title="no research article in the catalogue"></td>'
        s, w, x = b.get("scan", 0), b.get("word", 0), b.get("nowhere", 0)
        bar = "".join(f'<i class="{cl}" style="flex:{v}"></i>' for cl, v in (("s", s), ("w", w), ("x", x)) if v)
        tip = f"{y}: {n} articles; scan {s}, Word {w}, nowhere {x}"
        return f'<td class="g" title="{tip}"><div class="bar">{bar}</div><span>{n}</span></td>'

    grid = []
    for k in order:
        c = C[k]
        cls = "rec" if k in rec else ""
        mark = "★ " if k in rec else ("◆ " if k in alt else "")
        grid.append(f'<tr class="{cls}"><th class="jn"><b>{mark}{k}</b> <span dir="rtl">{e(c["journal"])}</span>'
                    f'<small>{EN.get(c["country"], c["country"])}</small></th>'
                    + "".join(cell(c, y) for y in YEARS) + f'<td class="num">{c["n"]}</td></tr>')
    yh = "".join(f"<th class='yh'>{str(y)[2:]}</th>" for y in YEARS)

    def row(k):
        c = C[k]
        wc = f'{c["wc_title"]}/{c["wc_checked"]} · {c["wc_same"]}' if c["wc_checked"] else "—"
        mark = "★" if k in rec else ("◆" if k in alt else "")
        return (f'<tr class="{"rec" if k in rec else ""}"><td>{mark}</td><td><b>{k}</b></td><td dir="rtl">{e(c["journal"])}</td>'
                f'<td>{EN.get(c["country"], c["country"])}</td><td class="num">{c["first"]}–{c["last"]}</td>'
                f'<td class="num">{c["n"]}</td><td class="num">{c["scan"]}</td><td class="num">{c["word"]}</td>'
                f'<td class="num">{c["nowhere"]}</td><td class="num">{c["research_share"]:.0%}</td>'
                f'<td class="num">{c["mean_pages"]:.0f}</td><td class="num">{c["shared_authors"] if k != "0130" else "—"}</td>'
                f'<td class="num">{c["cited_links_articles"] if k != "0130" else "(self) " + str(c["cited_links_articles"])}</td>'
                f'<td class="num">{c["cited_name"] or ("~" + str(c["cited_name_ambiguous"]) if c["cited_name_ambiguous"] else 0)}</td>'
                f'<td class="num">{wc}</td><td class="num">${c["cost_exp"]:.0f}</td></tr>')

    cand = "".join(row(k) for k in sorted(CANDIDATES, key=lambda k: (k not in rec, k not in alt, -C[k]["cited_links_articles"])))
    whys = "".join(f'<tr><td><b>{k}</b></td><td dir="rtl">{e(C[k]["journal"])}</td><td>{EN.get(C[k]["country"])}</td>'
                   f'<td class="num">{C[k]["n"]}</td><td class="num">{C[k]["scan"]} / {C[k]["word"]} / {C[k]["nowhere"]}</td>'
                   f'<td class="num">${C[k]["cost_exp"]:.0f}</td><td class="note">{e(WHY[k])}</td></tr>' for k in rec)
    regions = collections.Counter(REGION.get(C[k]["country"], "?") for k in rec)
    top_pairs = sorted(pairs, key=lambda p: -p[2])[:12]
    pairs_html = "".join(f"<tr><td>{a} – {b}</td><td class='num'>{n}</td></tr>" for a, b, n in top_pairs)
    css = open(HERE / "page54.css").read()
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gate 2: choosing journals</title>
<style>{css}</style></head><body>
<header><div class="wrap"><div class="crumb">Education Citation Index · experiment 54 · 2026-10-22</div>
<h1>Gate 2: which ten journals</h1>
<p class="sub">Ten education journals, 2010–2025, read whole, so that we can see whether education journals cite each other.
Each row below is a journal and each square is a year. The colours show where that year's articles can be read from:
a <b class="cs">scan</b>, the publisher's <b class="cw">Word file</b>, or <b class="cx">nowhere</b>. The ★ rows are the
recommendation and the ◆ rows the cheaper set. Prices are estimates; nothing has been run.</p></div></header>
<main><div class="wrap">
<div class="cards">
<div class="card kpi"><div class="n">{tr['n']:,}</div><div class="l">articles in the ★ set</div><div class="s">{tr['scan']:,} scans · {tr['word']:,} Word · {tr['nowhere']} nowhere</div></div>
<div class="card kpi"><div class="n">${tr['cost_exp']:.0f}</div><div class="l">expected cost</div><div class="s">scans ${tr['scan_cost']:.0f} ({tr['scan_pages']:,} pages) + Word ${tr['word_cost']:.0f}</div></div>
<div class="card kpi grey"><div class="n">${tr['cost_worst']:.0f}</div><div class="l">worst case</div><div class="s">scans +30%, Word at the full Argon call</div></div>
<div class="card kpi grey"><div class="n">{tr['max_share']:.0%}</div><div class="l">largest journal's share</div><div class="s">limit about 25%</div></div>
<div class="card kpi grey"><div class="n">${ta['cost_exp']:.0f}</div><div class="l">◆ cheaper set</div><div class="s">{ta['journals']} journals, {ta['n']:,} articles</div></div>
</div>
<div class="card sec"><h2>The years, journal by journal</h2>
<div class="legend"><span><i class="dot s"></i>scan (main bucket)</span><span><i class="dot w"></i>Word original only (estimated pages, D36)</span><span><i class="dot x"></i>nowhere</span><span><i class="dot n"></i>no article in the catalogue that year</span><span>the number in a square is the catalogue's count of research articles</span></div>
<div class="tw"><table class="grid"><thead><tr><th></th>{yh}<th class="num">all</th></tr></thead><tbody>{''.join(grid)}</tbody></table></div></div>
<div class="card sec"><h2>The recommendation (★), and why each journal is in it</h2>
<p class="note">Regions: {', '.join(f'{k} {v}' for k, v in regions.most_common())}. The scan / Word / nowhere column is articles, 2010–2025.</p>
<div class="tw"><table><thead><tr><th>code</th><th>journal</th><th>country</th><th class="num">articles</th><th class="num">scan / Word / nowhere</th><th class="num">cost</th><th>why</th></tr></thead><tbody>{whys}</tbody></table></div></div>
<div class="two">
<div class="card"><h2>Cost</h2><table>
<tr><th></th><th class="num">★ set</th><th class="num">◆ cheaper set</th></tr>
<tr><td>articles</td><td class="num">{tr['n']:,}</td><td class="num">{ta['n']:,}</td></tr>
<tr><td>scan pages × $0.0108</td><td class="num">{tr['scan_pages']:,} → ${tr['scan_cost']:.0f}</td><td class="num">{ta['scan_pages']:,} → ${ta['scan_cost']:.0f}</td></tr>
<tr><td>Word articles × $0.02 (between $0.01 and $0.03)</td><td class="num">{tr['word']:,} → ${tr['word_cost']:.0f}</td><td class="num">{ta['word']:,} → ${ta['word_cost']:.0f}</td></tr>
<tr><td><b>expected</b></td><td class="num"><b>${tr['cost_exp']:.0f}</b></td><td class="num"><b>${ta['cost_exp']:.0f}</b></td></tr>
<tr><td>with Flash for the Word articles ($0.01)</td><td class="num">${tr['cost_lo']:.0f}</td><td class="num">${ta['cost_lo']:.0f}</td></tr>
<tr><td>worst case (scans $0.014 a page, Word $0.05)</td><td class="num">${tr['cost_worst']:.0f}</td><td class="num">${ta['cost_worst']:.0f}</td></tr>
</table><p class="note">Gate 1 really cost $0.0099 a page, judge included. Page counts are the catalogue's page ranges; for gate 1 these
gave 2,441 pages against 2,439 read. Prices double after 1 December (Argon) and 1 January (Flash).</p></div>
<div class="card"><h2>Shared authors inside the ★ set</h2><p class="note">Mandumah authority ids found in both journals, articles 2000–2025.</p>
<table><thead><tr><th>pair</th><th class="num">authors</th></tr></thead><tbody>{pairs_html}</tbody></table></div>
</div>
<div class="card sec"><h2>All {len(CANDIDATES)} candidates</h2>
<p class="note">2010–2025, EduSearch research articles («بحوث ومقالات»). <b>Shared</b> means authority ids also found in 0130.
<b>Cited (articles)</b>: how many of 0130's 126 read articles have a reference linked to this journal in the catalogue.
<b>Named</b>: references whose journal name is this journal's own (~ means the name is shared by several journals, such as «مجلة كلية التربية»).
<b>Word check</b>: a random sample of its Word-only articles (15 a journal for the ★ set and 0139/0233, 6 for the rest): how many Word files open with the catalogue's title, then (after ·) how many also start on exactly the catalogue's first page (experiment 53's test). Almost every page miss is one page off with the right title: the test needs the title beside it.</p>
<div class="tw"><table><thead><tr><th></th><th>code</th><th>journal</th><th>country</th><th class="num">years</th><th class="num">articles</th>
<th class="num">scan</th><th class="num">Word</th><th class="num">nowhere</th><th class="num">research</th><th class="num">pages</th>
<th class="num">shared</th><th class="num">cited (articles)</th><th class="num">named</th><th class="num">Word check</th><th class="num">cost</th></tr></thead>
<tbody>{cand}</tbody></table></div></div>
</div></main></body></html>"""


def main():
    C = load()
    tr, ta = totals(C, RECOMMENDED), totals(C, CHEAPER)
    pairs = internal_shared(RECOMMENDED)
    sel = dict(span=[Y0, Y1], rates=dict(scan_page=SCAN_PAGE, scan_page_worst=SCAN_PAGE_WORST, word=WORD_EXP,
                                         word_lo=WORD_LO, word_worst=WORD_WORST),
               recommended=RECOMMENDED, recommended_totals=tr, cheaper=CHEAPER, cheaper_totals=ta,
               shared_pairs=pairs, candidates={k: {f: C[k][f] for f in (
                   "journal", "country", "first", "last", "n", "scan", "word", "nowhere", "research_share", "mean_pages",
                   "scan_pages", "shared_authors", "cited_links_articles", "cited_links", "cited_name",
                   "cited_name_ambiguous", "topic", "wc_checked", "wc_same", "wc_diff", "wc_title", "cost_exp", "cost_lo",
                   "cost_worst", "by_year")} for k in CANDIDATES})
    (HERE / "out/selection.json").write_text(json.dumps(sel, ensure_ascii=False, indent=1))
    lines = ["| | code | journal | country | years | articles | scan | Word | nowhere | research | pages/art | shared with 0130 | cited by 0130 (articles) | named | Word check | cost |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in sorted(CANDIDATES, key=lambda k: (k not in RECOMMENDED, k not in CHEAPER, -C[k]["cited_links_articles"])):
        c = C[k]
        lines.append(f'| {"★" if k in RECOMMENDED else ""}{"◆" if k in CHEAPER else ""} | {k} | {c["journal"]} | {EN.get(c["country"], c["country"])} | '
                     f'{c["first"]}–{c["last"]} | {c["n"]} | {c["scan"]} | {c["word"]} | {c["nowhere"]} | {c["research_share"]:.0%} | '
                     f'{c["mean_pages"]:.0f} | {c["shared_authors"]} | {c["cited_links_articles"]} | {c["cited_name"] or ("~" + str(c["cited_name_ambiguous"]) if c["cited_name_ambiguous"] else 0)} | '
                     f'{c["wc_title"]}/{c["wc_checked"]} title, {c["wc_same"]} page | ${c["cost_exp"]:.0f} |')
    (HERE / "out/candidates.md").write_text("\n".join(lines) + "\n")
    (HERE / "out/gate2_selection.html").write_text(page(C, RECOMMENDED, CHEAPER, tr, ta, pairs))
    print("recommended", tr); print("cheaper", ta)
    for k in RECOMMENDED + CHEAPER:
        c = C[k]; print(k, c["n"], c["scan"], c["word"], c["nowhere"], c["scan_pages"], round(c["cost_exp"]), f'{c["wc_same"]}/{c["wc_checked"]}')


if __name__ == "__main__":
    main()
