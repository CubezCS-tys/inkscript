"""C1a. Byline authors of the 600 articles: how each is tied to a catalogue authority, and how ambiguous each name is in
the whole catalogue (2.2M headings). Read-only; writes out/c_people_and_institutions/c1_bylines.json (+ summary)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from common48c import (RUNS600, exact_holders, given_surname, hcon, heading_key, is_arab, latin_loose_holders,
                       loose_holders, mcon, name_key, pcon, progress, save)

OWN = {"exact", "token-subset", "transliteration", "script-twin", "weak-name+given-name"}
SEARCH = {"name-key-to-authority", "name-cluster+second-signal"}
NONE = {"provisional", "weak-name-rejected"}


def bucket(n):
    return "0" if n == 0 else "1" if n == 1 else "2-5" if n <= 5 else "6-20" if n <= 20 else "21-100" if n <= 100 else ">100"


def main():
    p, m, h = pcon(), mcon(), hcon()
    rows = [dict(r) for r in p.execute(f"""
        SELECT a.authorship_pk, v.stem, v.run, a.pub_id, a.position, a.role_code, a.role_raw, a.method, a.score,
               a.person_id, a.inst_id, a.c999, a.catalogue_seq, a.evidence,
               c.name cat_name, c.latin cat_latin, c.authority_id, c.is_org
        FROM authorships a JOIN versions v ON v.version_id = a.from_version AND v.is_current = 1
        LEFT JOIN catalogue_contributors c ON c.c999 = a.c999 AND c.seq = a.catalogue_seq
        WHERE v.run IN {RUNS600} ORDER BY v.stem, a.position""")]
    ment = defaultdict(list)
    for r in p.execute("""SELECT am.authorship_pk, b.printed, b.name_text, b.titles, b.script, b.email IS NOT NULL has_mail,
                          b.block_id, b.min_word_conf, b.byline_pos FROM authorship_mentions am
                          JOIN byline_mentions b USING (mention_pk) ORDER BY b.byline_pos, b.script"""):
        ment[r["authorship_pk"]].append(dict(r))
    keys = set()
    for r in rows:
        r["mentions"] = ment.get(r["authorship_pk"], [])
        r["printed"] = [x["name_text"] or x["printed"] for x in r["mentions"]] or \
            (json.loads(r["evidence"] or "{}").get("printed") or [])
        for n in r["printed"]:
            keys.add(name_key(n))
        if r["cat_name"]:
            keys.add(heading_key(r["cat_name"]))
    EH = exact_holders(h, keys)
    nrec = {}
    for r in rows:
        best = max(r["printed"], key=lambda n: (is_arab(n), len(n))) if r["printed"] else None
        r["best_printed"] = best
        r["exact_holders"] = len(set().union(*[EH.get(name_key(n), set()) for n in r["printed"]])) if r["printed"] else None
        g, s = given_surname(best) if best else (None, None)
        r["given"], r["surname"] = g, s
        lh = (loose_holders(m, g, s) if is_arab(best or "") else latin_loose_holders(h, g, s)) if best else set()
        r["loose_holders"] = len(lh)
        r["true_in_loose"] = (r["authority_id"] in lh) if r["authority_id"] else None
        r["heading_homonyms"] = len(EH.get(heading_key(r["cat_name"]), set())) if r["cat_name"] and not r["is_org"] else None
        if r["authority_id"]:
            if r["authority_id"] not in nrec:
                nrec[r["authority_id"]] = m.execute("SELECT count(DISTINCT rec) FROM authors WHERE authority_id = ?",
                                                    (r["authority_id"],)).fetchone()[0]
            r["authority_n_records"] = nrec[r["authority_id"]]
        meth = r["method"]
        r["how"] = ("editorial/corporate" if r["inst_id"] or meth in ("editorial-role", "corporate-byline")
                    else "own-record" if meth in OWN else "name-search" if meth in SEARCH
                    else "no-link" if meth in NONE else "catalogue-only" if meth == "catalogue-only" else meth)
        r.pop("evidence", None)
    S = {}
    on_byline = [r for r in rows if r["mentions"]]
    S["authorships_600"] = len(rows)
    S["authorships_with_byline_mention"] = len(on_byline)
    S["byline_mentions_600"] = sum(len(r["mentions"]) for r in rows)
    S["how_byline"] = Counter(r["how"] for r in on_byline)
    S["method_byline"] = Counter(r["method"] for r in on_byline)
    S["how_catalogue_only"] = Counter((r["role_code"], bool(r["is_org"])) .__str__() for r in rows if not r["mentions"])
    persons = [r for r in on_byline if r["how"] not in ("editorial/corporate",)]
    S["byline_person_authorships"] = len(persons)
    S["with_authority_id"] = sum(1 for r in persons if r["authority_id"] and r["method"] != "weak-name-rejected")
    S["scripts"] = Counter("+".join(sorted({x["script"] for x in r["mentions"]})) for r in persons)
    S["exact_holders_dist"] = Counter(bucket(r["exact_holders"] or 0) for r in persons)
    S["loose_holders_dist"] = Counter(bucket(r["loose_holders"]) for r in persons)
    S["loose_holders_dist_arabic"] = Counter(bucket(r["loose_holders"]) for r in persons if is_arab(r["best_printed"] or ""))
    S["loose_holders_dist_latin_only"] = Counter(bucket(r["loose_holders"]) for r in persons
                                                 if not is_arab(r["best_printed"] or ""))
    S["linked_heading_homonyms_dist"] = Counter(bucket(r["heading_homonyms"]) for r in persons
                                                if r["heading_homonyms"] is not None)
    S["true_authority_inside_loose_set"] = Counter(str(r["true_in_loose"]) for r in persons if r["authority_id"])
    S["authority_n_records_dist"] = Counter(bucket(r["authority_n_records"]) for r in persons if r.get("authority_n_records"))
    S["titles_printed"] = sum(1 for r in persons if any(x["titles"] for x in r["mentions"]))
    S["email_printed"] = sum(1 for r in persons if any(x["has_mail"] for x in r["mentions"]))
    S["articles_with_no_byline_person"] = len({r["stem"] for r in rows}) - len({r["stem"] for r in persons})
    S["articles"] = len({r["stem"] for r in rows})
    save("c1_bylines.json", rows)
    save("c1_bylines_summary.json", S)
    hard = sorted(persons, key=lambda r: -r["loose_holders"])[:25]
    save("c1_hard_names.json", [dict(stem=r["stem"], printed=r["printed"], method=r["method"], cat=r["cat_name"],
                                     authority=r["authority_id"], loose=r["loose_holders"], exact=r["exact_holders"])
                                for r in hard])
    progress(f"- c1_bylines.py: {len(persons)} byline person authorships; how {dict(S['how_byline'])}")
    print(json.dumps(S, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
