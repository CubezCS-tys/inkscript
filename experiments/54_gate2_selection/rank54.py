"""Experiment 54 step 4: per journal, 2010-2025: catalogue count, by route, years present, research share, subject
similarity to 0130, shared authority ids with 0130, cited by 0130 (catalogue links + references naming it).
-> out/candidates.json (all journals) and prints the shortlist."""
import collections, csv, json, math, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
Y0, Y1 = 2010, 2025
rows = [r for r in csv.DictReader(open(HERE / "out/articles.tsv"), delimiter="\t") if Y0 <= int(r["year"]) <= Y1]
J = json.load(open(HERE / "out/journals.json"))
C = json.load(open(HERE / "out/cited_by_0130.json"))

def norm(s):
    s = re.sub(r"[ً-ْـ]", "", s or "")
    s = s.translate(str.maketrans("أإآىة", "اااىه")).replace("ى", "ي")
    s = re.sub(r"[^\w ]", " ", s)
    return " ".join(w for w in s.split())

per = collections.defaultdict(lambda: dict(n=0, route=collections.Counter(), years=collections.Counter(),
                                           yr=collections.defaultdict(collections.Counter), pages=0, pages_scan=0))
meta = {}
for r in rows:
    k = r["journal_code"]; p = per[k]; y = int(r["year"])
    p["n"] += 1; p["route"][r["route"]] += 1; p["years"][y] += 1; p["yr"][y][r["route"]] += 1
    try: pg = max(1, int(r["page_last"]) - int(r["page_first"]) + 1)
    except Exception: pg = None
    if pg and pg > 200: pg = None
    p.setdefault("pgs", []).append(pg)
    meta[k] = (r["journal"], r["country"])

# name mentions in 0130's references -> journals with that normalised name
names = collections.defaultdict(list)
for k, (n, _) in meta.items(): names[norm(n)].append(k)
mention = collections.Counter(); ambiguous = collections.Counter()
for s, cnt in C["sources_top"]:
    ns = norm(s)
    for cand in (ns, norm(s.split("،")[0]), "مجله " + ns):
        if cand in names:
            ks = names[cand]
            for k in ks:
                mention[k] += cnt if len(ks) == 1 else 0
                if len(ks) > 1: ambiguous[k] += cnt
            break
links = {k: v["articles"] for k, v in C["links_by_journal"].items()}
linkn = {k: v["links"] for k, v in C["links_by_journal"].items()}

def vec(code):
    return J.get(code, {}).get("subjects", {})
v0 = vec("0130"); n0 = math.sqrt(sum(x * x for x in v0.values()))
def cos(code):
    v = vec(code); n = math.sqrt(sum(x * x for x in v.values()))
    return sum(v0.get(t, 0) * x for t, x in v.items()) / (n0 * n) if n and n0 else 0
A0 = set(J["0130"]["authority_ids"])

out = {}
for k, p in per.items():
    j = J.get(k, {}); types = j.get("types", {}); tot = sum(types.values()) or 1
    pgs = [x for x in p["pgs"] if x]; mean_pg = sum(pgs) / len(pgs) if pgs else 15
    scan_pages = sum((x or mean_pg) for x, r in zip(p["pgs"], [None] * len(p["pgs"])))
    out[k] = dict(code=k, journal=meta[k][0], country=meta[k][1], n=p["n"], scan=p["route"]["scan"],
                  word=p["route"]["word"], nowhere=p["route"]["nowhere"],
                  years_present=sum(1 for y in range(Y0, Y1 + 1) if p["years"][y]),
                  first=min(p["years"]), last=max(p["years"]),
                  by_year={y: dict(p["yr"][y]) for y in sorted(p["yr"])},
                  research_share=round(types.get("بحوث ومقالات", 0) / tot, 2), types=types,
                  mean_pages=round(mean_pg, 1), fos=j.get("fos", []),
                  subject_cos=round(cos(k), 3), shared_authors=len(A0 & set(j.get("authority_ids", []))),
                  n_authority=len(j.get("authority_ids", [])),
                  cited_links_articles=links.get(k, 0), cited_links=linkn.get(k, 0),
                  cited_name=mention[k], cited_name_ambiguous=ambiguous[k])
(HERE / "out/candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=0))
if __name__ == "__main__":
    lo, hi = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (100, 900)
    L = [x for x in out.values() if lo <= x["n"] <= hi and x["years_present"] >= 13 and x["research_share"] >= .6]
    L.sort(key=lambda x: -(x["subject_cos"] * 3 + x["shared_authors"] / 20 + x["cited_links_articles"] / 5 + x["cited_name"] / 10))
    for x in L[:90]:
        print(x["code"], x["country"], x["journal"][:38], x["n"], x["scan"], x["word"], x["nowhere"], x["years_present"],
              x["research_share"], x["mean_pages"], "cos", x["subject_cos"], "sh", x["shared_authors"],
              "cit", x["cited_links_articles"], x["cited_name"], x["cited_name_ambiguous"], x["fos"][:2])
