"""C1b. Splits: how many spellings one authority id carries (Arabic / Latin, «ال», hamza, honorifics, life note), over
the whole catalogue (one GROUP BY in SQLite) and in detail for the authorities our 600 bylines reach. Also: the same
person under two authority ids (duplicate authorities) as seen from our bylines. Read-only."""
from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict

from common48c import OUT, exact_holders, hcon, heading_key, mcon, mfold, pcon, progress, save, split_life


def variant_kinds(names: list[str]) -> list[str]:
    """What separates the spellings of one authority id."""
    kinds = set()
    ar = [n for n in names if re.search("[؀-ۿ]", n)]
    la = [n for n in names if not re.search("[؀-ۿ]", n)]
    if ar and la:
        kinds.add("arabic+latin-heading")
    if len(set(ar)) > 1:
        f = {mfold(n) for n in ar}
        if len(f) == 1:
            kinds.add("hamza/ya/ta-marbuta/diacritics only")
        else:
            base = {mfold(split_life(n)[0]) for n in ar}
            if len(base) < len(f):
                kinds.add("life note added/dropped")
            noal = {re.sub(r"(^|\s)ال", r"\1", b).replace(" ", "") for b in base}
            if len(noal) < len(base):
                kinds.add("with/without ال or spacing")
            if len(noal) > 1:
                toks = [set(b.replace("،", " ").split()) for b in base]
                if any(a < b or b < a for a in toks for b in toks if a != b):
                    kinds.add("longer/shorter nasab")
                else:
                    kinds.add("other spelling")
    if len({x.lower() for x in la}) > 1:
        kinds.add("several Latin forms")
    return sorted(kinds)


def main():
    m, p, h = mcon(), pcon(), hcon()
    t0 = time.time()
    # whole catalogue, in SQLite: spellings per authority id
    hist = {}
    for col in ("name", "name_folded", "latin"):
        hist[col] = {str(k): n for k, n in m.execute(f"""
            SELECT CASE WHEN c > 5 THEN 6 ELSE c END k, count(*) FROM
              (SELECT authority_id, count(DISTINCT {col}) c FROM authors WHERE authority_id IS NOT NULL AND
               authority_id <> '' AND NOT coalesce(is_org,0) GROUP BY authority_id) GROUP BY k""")}
    t1 = time.time()
    progress(f"- c1_splits.py: catalogue-wide spelling histogram in {t1 - t0:.0f}s")
    save("c1_splits_catalogue_hist.json", dict(hist=hist, seconds=round(t1 - t0)))
    # our authorities (byline-linked + catalogue-only persons of the 600)
    by = json.load(open(OUT / "c1_bylines.json"))
    aids = sorted({r["authority_id"] for r in by if r["authority_id"] and not r["is_org"]})
    det, kinds_c, nform = [], Counter(), Counter()
    for aid in aids:
        rows = m.execute("SELECT name, latin, count(*) n FROM authors WHERE authority_id = ? GROUP BY name, latin",
                         (aid,)).fetchall()
        names = sorted({r["name"] for r in rows if r["name"]} | {r["latin"] for r in rows if r["latin"]})
        k = variant_kinds(names)
        for x in k:
            kinds_c[x] += 1
        nf = len({mfold(r["name"]) for r in rows if r["name"]})
        nform["raw_names"] += 0
        det.append(dict(authority_id=aid, n_headings=sum(r["n"] for r in rows), raw_ar=len({r["name"] for r in rows}),
                        folded_ar=nf, latin=len({r["latin"] for r in rows if r["latin"]}), kinds=k, names=names[:12]))
    dist = {c: Counter(min(d[c], 6) for d in det) for c in ("raw_ar", "folded_ar", "latin")}
    # duplicate authorities seen from the bylines: the linked heading's key is held by other authority ids too
    keys = {heading_key(r["cat_name"]) for r in by if r["cat_name"] and not r["is_org"]}
    EH = exact_holders(h, keys)
    dup_cands = []
    for r in by:
        if not r["cat_name"] or r["is_org"] or not r["authority_id"]:
            continue
        others = EH.get(heading_key(r["cat_name"]), set()) - {r["authority_id"]}
        if others:
            dup_cands.append(dict(stem=r["stem"], printed=r["printed"], heading=r["cat_name"], authority=r["authority_id"],
                                  others=sorted(others)))
    # the same person across our 600: printed name keys reaching several authority ids, authority ids with 2+ articles
    per_aid = defaultdict(set)
    for r in by:
        if r["authority_id"]:
            per_aid[r["authority_id"]].add(r["stem"])
    S = dict(catalogue_hist=hist, our_authorities=len(aids), our_dist={k: dict(v) for k, v in dist.items()},
             our_variant_kinds=dict(kinds_c), our_authorities_with_any_variant=sum(1 for d in det if d["kinds"]),
             linked_heading_shared_with_other_ids=len(dup_cands),
             our_authorities_in_2plus_of_the_600=sum(1 for v in per_aid.values() if len(v) > 1))
    save("c1_splits_summary.json", S)
    save("c1_splits_detail.json", det)
    save("c1_dup_authority_candidates.json", dup_cands)
    progress(f"- c1_splits.py: {len(aids)} of our authorities; variant kinds {dict(kinds_c)}")
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
