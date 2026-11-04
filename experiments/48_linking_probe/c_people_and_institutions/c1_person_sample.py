"""C1d. Precision of platform v2's byline -> person links: a seeded sample (seed 4822, 50) of the byline authorships of
the 600 that carry a catalogue authority, with all the evidence to judge them: the byline as the JATS prints it (contrib
group, affiliations, the byline meta line), the article's own catalogue record (title, journal, year, contributors),
and the linked authority's other works (journals, years, titles). Writes c1_person_sample.json and prints a digest."""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict

from common48c import OUT, REPO, mcon, pcon

MASTERS = REPO / "experiments" / "43_rehearsal" / "out"


def jats_byline(run, stem):
    p = MASTERS / run / "masters" / f"{stem}.jats.xml"
    if not p.exists():
        return None
    s = p.read_text(encoding="utf-8")
    cg = re.search(r"<contrib-group>.*?</contrib-group>", s, re.S)
    affs = re.findall(r"<aff[ >].*?</aff>", s, re.S)
    meta = [m for m in re.findall(r"<custom-meta[^>]*>.*?</custom-meta>", s, re.S) if re.search("byline|author", m)]
    strip = lambda x: " ".join(re.sub(r"<[^>]+>", " ", x).split())
    return dict(contrib=strip(cg.group(0)) if cg else None, affs=[strip(a) for a in affs][:6],
                byline_meta=[strip(m)[:300] for m in meta][:3])


def authority_works(m, aid, limit=40):
    rows = m.execute("""SELECT r.year_int y, r.journal j, r.title t, a.role FROM authors a JOIN records r ON r.rec = a.rec
                        WHERE a.authority_id = ? ORDER BY r.year_int""", (aid,)).fetchall()
    g = defaultdict(list)
    for r in rows:
        g[r["j"] or "?"].append(r)
    return dict(n=len(rows), by_journal=[f"{min((r['y'] or 0) for r in rs)}-{max((r['y'] or 0) for r in rs)} n{len(rs)} "
                                         f"{j[:40]} :: {(rs[0]['t'] or '')[:60]}" for j, rs in
                                         sorted(g.items(), key=lambda x: -len(x[1]))[:8]])


def main():
    by = json.load(open(OUT / "c1_bylines.json"))
    pop = [r for r in by if r["mentions"] and r["authority_id"] and r["method"] != "weak-name-rejected"]
    rnd = random.Random(4822)
    samp = rnd.sample(pop, 50)
    m, p = mcon(), pcon()
    out = []
    for r in samp:
        rec = p.execute("SELECT * FROM catalogue_records WHERE c999 = ?", (r["c999"],)).fetchone()
        rec = dict(rec) if rec else {}
        contrib = [dict(x) for x in p.execute("SELECT seq, tag, name, latin, role_raw, authority_id FROM "
                                              "catalogue_contributors WHERE c999 = ? ORDER BY seq", (r["c999"],))]
        out.append(dict(authorship_pk=r["authorship_pk"], stem=r["stem"], run=r["run"], position=r["position"],
                        method=r["method"], score=r["score"], person_id=r["person_id"], printed=r["printed"],
                        titles=[x["titles"] for x in r["mentions"]], block=[x["block_id"] for x in r["mentions"]],
                        min_conf=[x["min_word_conf"] for x in r["mentions"]],
                        cat_name=r["cat_name"], cat_latin=r["cat_latin"], authority_id=r["authority_id"],
                        record=dict(title=rec.get("title"), journal=rec.get("journal_raw"), year=rec.get("year_int")),
                        record_contributors=contrib, jats=jats_byline(r["run"], r["stem"]),
                        authority=authority_works(m, r["authority_id"]),
                        exact_holders=r["exact_holders"], loose_holders=r["loose_holders"]))
    (OUT / "c1_person_sample.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for i, x in enumerate(out):
        print(f"===== {i} {x['stem']} pos{x['position']} {x['method']} printed={x['printed']} titles={x['titles']}")
        print(f"  record: {x['record']}")
        print("  contributors: " + " ; ".join(f"{c['seq']}:{c['name']}/{c['latin'] or ''}({c['role_raw']},{c['authority_id']})"
                                              for c in x["record_contributors"]))
        print(f"  linked: {x['cat_name']} | {x['cat_latin']} auth {x['authority_id']}  holders exact {x['exact_holders']} "
              f"loose {x['loose_holders']}")
        j = x["jats"] or {}
        print(f"  jats contrib: {(j.get('contrib') or '')[:250]}")
        if j.get("affs"):
            print(f"  jats aff: {' || '.join(a[:120] for a in j['affs'][:3])}")
        print(f"  authority n={x['authority']['n']}: " + " | ".join(x["authority"]["by_journal"][:5]))


if __name__ == "__main__":
    main()
