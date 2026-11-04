"""A1 step 4: decide each work's catalogue link from the scored candidates (matches.jsonl).

Rule written after reading the first judged sample (seed 4801) and then checked on a fresh draw:
  * a Latin-script cited author against an Arabic-only catalogue heading is compared through translit_pairs
    (platform_v2, learned from the catalogue's own Latin headings); no Latin form known → unknown, not a contradiction;
  * the cited title must have ≥ 3 content words (a citation of a journal issue or a bare journal name is no work);
  * a cited thesis links only to a thesis record (رسائل جامعية) or the thesis's printed summary (عروض رسائل);
  * a book review (عروض كتب), a book-of-the-month column etc. is a relation, never the work;
  accept when
    (a) title ≥ 0.85 and author agrees and nothing contradicts (year differs by ≥ 2 with no volume/page agreement);
    (b) title ≥ 0.85, author unknown, year within 1 and (journal ≥ 0.6 or volume/issue/page agree);
    (c) title ≥ 0.70, author agrees, year within 1 and journal ≥ 0.8;
    (d) title ≥ 0.85, the authors share only common name words (≥ 2 of them), journal ≥ 0.8 (v3: was 'year or journal').
  v3: a different journal on both sides (journal < 0.3, no volume/page agreement) makes (a) a candidate;
  candidate (for a person) when title ≥ 0.75 and author agrees or (author unknown and year within 1); the rest no link.
"""
import json, re, difflib, collections, unicodedata
from q import pv
from match import toks

OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
AR = re.compile(r"[؀-ۿ]")
TR = collections.defaultdict(set)
for ar, lat in pv().execute("SELECT arabic, latin FROM translit_pairs WHERE n >= 3"):
    TR[ar].add(re.sub(r"[^a-z]", "", lat.lower()))


def compact(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def cross_author(cited, cat_names):
    """Latin cited names vs Arabic catalogue headings: 1 agree, 0 no Latin form agrees though forms are known,
    None nothing to compare."""
    lat = [c for c in cited if c and not AR.search(c)]
    if not lat or not cat_names:
        return None
    ctoks = set()
    for c in lat:
        for t in re.split(r"[\s,.;]+", c):
            t = compact(t)
            if len(t) >= 3:
                ctoks.add(t)
                if t.startswith("al") and len(t) > 4:
                    ctoks.add(t[2:])
    known = False
    for n in cat_names:
        for t in re.split(r"[\s،,]+", n or ""):
            t = t.strip()
            if not t:
                continue
            forms = set(TR.get(t, ())) | (set(TR.get(t[2:], ())) if t.startswith("ال") else set())
            if forms:
                known = True
            for f in forms:
                for g in (f, f[2:] if f.startswith("al") else f):
                    if len(g) >= 3 and any(difflib.SequenceMatcher(None, g, c).ratio() >= 0.85 for c in ctoks):
                        return 1.0
    return 0.0 if known else None


def decide(m, c):
    a = c["s_author"]
    if m["authors"] and c["authors"] and all(AR.search(n or "") for n in c["authors"]) and \
            not any(AR.search(x or "") for x in m["authors"]):
        a = cross_author(m["authors"], c["authors"])
    if c["authors"] and all(("التحرير" in (n or "")) or ("تحرير" in (n or "")) for n in c["authors"]):
        a = None                      # the catalogue gives the editorial board as author: nothing to compare
    T, Y, J, V = c["s_title"], c["s_year"], c["s_journal"], c["s_vip"]
    rtype = c["type"] or ""
    why = []
    if len(toks(m["title"])) < 3:
        return "none", a, ["title < 3 content words"]
    if "عروض كتب" in rtype or "افتتاحيات" in rtype or "نصوص أدبية" in rtype:
        return ("relation" if T >= 0.85 and a != 0 else "none"), a, [f"record type {rtype}"]
    if m["cls"] == "thesis" and not ("رسائل" in rtype):
        return ("candidate" if T >= 0.85 and a == 1 else "none"), a, ["cited thesis, record not a thesis"]
    if m["cls"] in ("book", "turath", "chapter") and "رسائل" not in rtype and T >= 0.85 and a == 1:
        return "relation", a, ["cited book matched to an article: a study or a part of it"]
    contradict = (Y is not None and Y <= 0.2 and not (V is not None and V >= 0.67)) or a == 0
    # v3 (after the validation draw): both sides name a journal and they differ, with no volume/page agreement:
    # the same title by the same author in another journal is often a second publication, not the one cited
    other_journal = J is not None and J < 0.3 and not (V is not None and V >= 0.67)
    if other_journal and T >= 0.85 and a == 1:
        return "candidate", a, ["same title+author, another journal"]
    ok_y = Y is not None and Y >= 0.7
    if T >= 0.85 and a == 1 and not contradict:
        return "accept", a, ["a: title+author"]
    if T >= 0.85 and a == 0.5 and not contradict and (J or 0) >= 0.8:
        return "accept", a, ["d: title+common-name author+year/journal"]
    if T >= 0.85 and a is None and ok_y and ((J or 0) >= 0.6 or (V or 0) >= 0.67):
        return "accept", a, ["b: title+year+journal/volume"]
    if T >= 0.70 and a == 1 and ok_y and (J or 0) >= 0.8:
        return "accept", a, ["c: close title+author+year+journal"]
    if T >= 0.75 and (a == 1 or (a is None and ok_y)):
        return "candidate", a, why
    return "none", a, why


def main():
    M = [json.loads(l) for l in open(OUT + "matches.jsonl", encoding="utf-8")]
    S = collections.Counter()
    with open(OUT + "decisions.jsonl", "w", encoding="utf-8") as f:
        for m in M:
            best = None
            for c in m["top"]:
                d, a, why = decide(m, c)
                rank = {"accept": 3, "relation": 2, "candidate": 1, "none": 0}[d]
                if best is None or rank > best[0] or (rank == best[0] and c["total"] > best[3]["total"]):
                    best = (rank, d, why, c, a)
            d = best[1] if best else "none"
            row = dict(cited_work_pk=m["cited_work_pk"], cls=m["cls"], decision=d,
                       why=best[2] if best else ["no candidate"],
                       c999=best[3]["c999"] if best and d != "none" else None,
                       rec=best[3]["rec"] if best and d != "none" else None,
                       author_cross=best[4] if best else None, total=best[3]["total"] if best else None)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            S[(m["cls"], d)] += 1
    for k in sorted(S):
        print(k, S[k])


if __name__ == "__main__":
    main()
