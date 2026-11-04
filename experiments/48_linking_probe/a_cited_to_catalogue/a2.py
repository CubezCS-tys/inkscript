"""A2: cited works outside Mandumah, looked up in OpenAlex and Crossref (source marked on every result).

Sets (seeded, so the request count is bounded):
  lat_article : every Latin-script journal article (OpenAlex; Crossref on a seeded 500)
  lat_book    : a seeded 300 of the Latin-script books (both sources)
  ara         : a seeded 40 Arabic-script works (20 journal articles + 20 books/theses), both sources
Output: out/a_cited_to_catalogue/external.jsonl, one row per (work, source) with the best hit and its components.
"""
import json, random, re, sys, difflib, unicodedata
from ext import openalex_works, openalex_search, crossref, n_requests
from match import title_fields

OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
ARABIC = re.compile(r"[؀-ۿ]")
LSTOP = set("the of and in on for a an to with by at from la le les de des du et en un une der die und das its as is are".split())


def lat(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return [t for t in re.sub(r"[^\w\s]", " ", s).split() if t not in LSTOP and len(t) > 1 and not t.isdigit()]


def arab(s):
    sys.path.insert(0, "/home/appuser/inkscript/experiments/45_marc_db")
    from match import toks
    return toks(s)


def tsim(a, b):
    f = arab if ARABIC.search(a or "") else lat
    x, y = f(a), f(b)
    if not x or not y:
        return 0.0
    d = 2 * len(set(x) & set(y)) / (len(set(x)) + len(set(y)))
    r = difflib.SequenceMatcher(None, " ".join(x), " ".join(y)).ratio()
    return round(max(d, (d + r) / 2), 3)


def surnames(w, p):
    out = []
    for a in (p.get("authors") or []):
        if isinstance(a, list) and a and a[0]:
            out.append(a[0])
    if not out:
        out = [a["printed"] for a in w["authors"] if a["printed"]]
    toks = set()
    for s in out[:3]:
        for t in (lat(s) if not ARABIC.search(s) else arab(s)):
            if len(t) >= 3:
                toks.add(t)
    return toks


def judge_fields(hit_title, hit_authors, hit_year, hit_venue, ct, csrc, sn, years):
    s_t = tsim(ct, hit_title or "")
    ha = set()
    for n in hit_authors:
        ha |= set(lat(n)) | set(arab(n) if ARABIC.search(n or "") else [])
    s_a = None if not sn or not ha else (1.0 if sn & ha else 0.0)
    s_y = None if not years or not hit_year else (1.0 if min(abs(y - hit_year) for y in years) <= 1 else 0.0)
    s_v = None if not csrc or not hit_venue else tsim(csrc, hit_venue)
    tot = 0.6 * s_t + 0.2 * (0.5 if s_a is None else s_a) + 0.1 * (0.5 if s_y is None else s_y) + \
        0.1 * (0.5 if s_v is None else s_v)
    return dict(s_title=s_t, s_author=s_a, s_year=s_y, s_venue=s_v, total=round(tot, 3))


def best_openalex(res, ct, csrc, sn, years):
    out = []
    for h in ((res.get("body") or {}).get("results") or []):
        venue = ((h.get("primary_location") or {}).get("source") or {}).get("display_name")
        auths = [(a.get("author") or {}).get("display_name") or "" for a in h.get("authorships") or []]
        j = judge_fields(h.get("display_name"), auths, h.get("publication_year"), venue, ct, csrc, sn, years)
        out.append(dict(j, source="openalex", id=h.get("id"), doi=h.get("doi"), title=h.get("display_name"),
                        year=h.get("publication_year"), venue=venue, authors=auths[:4], type=h.get("type"),
                        language=h.get("language")))
    out.sort(key=lambda x: -x["total"])
    return out[:2]


def best_crossref(res, ct, csrc, sn, years):
    out = []
    for h in (((res.get("body") or {}).get("message") or {}).get("items") or []):
        title = (h.get("title") or [""])[0]
        venue = (h.get("container-title") or [None])[0]
        auths = [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in h.get("author") or []]
        yr = None
        try:
            yr = h["issued"]["date-parts"][0][0]
        except Exception:
            pass
        j = judge_fields(title, auths, yr, venue, ct, csrc, sn, years)
        out.append(dict(j, source="crossref", doi=h.get("DOI"), title=title, year=yr, venue=venue, authors=auths[:4],
                        type=h.get("type"), cr_score=h.get("score")))
    out.sort(key=lambda x: -x["total"])
    return out[:2]


def main():
    from match import cited_years
    W = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")}
    C = {json.loads(l)["cited_work_pk"]: json.loads(l) for l in open(OUT + "classified.jsonl", encoding="utf-8")}
    done = set()
    try:
        for l in open(OUT + "external.jsonl", encoding="utf-8"):
            d = json.loads(l); done.add((d["cited_work_pk"], d["source"]))
    except FileNotFoundError:
        pass
    pks = sorted(W)
    rng = random.Random(4802)
    lat_art = [k for k in pks if C[k]["lang"] == "lat" and C[k]["cls"] == "journal_article"]
    lat_book = [k for k in pks if C[k]["lang"] == "lat" and C[k]["cls"] == "book"]
    ara_art = [k for k in pks if C[k]["lang"] == "ara" and C[k]["cls"] == "journal_article"]
    ara_book = [k for k in pks if C[k]["lang"] == "ara" and C[k]["cls"] in ("book", "thesis")]
    cr_art = set(rng.sample(lat_art, min(500, len(lat_art))))
    lb = rng.sample(lat_book, 300)
    aa = rng.sample(ara_art, 20)
    ab = rng.sample(ara_book, 20)
    jobs = [(k, "lat_article", ("openalex",) + (("crossref",) if k in cr_art else ())) for k in lat_art]
    jobs += [(k, "lat_book", ("openalex", "crossref")) for k in lb]
    jobs += [(k, "ara_article", ("openalex", "crossref")) for k in aa] + [(k, "ara_book", ("openalex", "crossref")) for k in ab]
    print(len(jobs), "works;", sum(len(j[2]) for j in jobs), "lookups planned;", n_requests(), "requests so far")
    with open(OUT + "external.jsonl", "a", encoding="utf-8") as f:
        for i, (k, group, srcs) in enumerate(jobs):
            w = W[k]
            ct, csrc, p, rep = title_fields(w)
            if not ct:
                continue
            sn = surnames(w, p); years = cited_years(w, p)
            for s in srcs:
                if (k, s) in done or (s == "openalex" and "--no-openalex" in sys.argv):
                    continue
                if s == "openalex":
                    res = openalex_works(ct, f"A2 {group}: title of cited work {w['cited_work_id']}")
                    hits = best_openalex(res, ct, csrc, sn, years)
                    if group.startswith("ara") and not hits:      # second try: free search
                        res = openalex_search(ct, f"A2 {group}: free search, cited work {w['cited_work_id']}")
                        hits = best_openalex(res, ct, csrc, sn, years)
                else:
                    bib = re.sub(r"https?://\S+", " ", rep["printed"] or ct)
                    res = crossref(bib, f"A2 {group}: citation string of cited work {w['cited_work_id']}")
                    hits = best_crossref(res, ct, csrc, sn, years)
                if res.get("status") != 200:
                    continue
                f.write(json.dumps(dict(cited_work_pk=k, cited_work_id=w["cited_work_id"], group=group, source=s,
                                        status=res.get("status"), title=ct, container=csrc, sn=sorted(sn),
                                        years=sorted(years), hits=hits), ensure_ascii=False) + "\n")
                f.flush()
            if (i + 1) % 100 == 0:
                print(i + 1, "works;", n_requests(), "requests", flush=True)
    print("done;", n_requests(), "requests")


if __name__ == "__main__":
    main()
