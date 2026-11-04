"""C2. Institutions in the 600: what affiliations become, the university/faculty/department tree, scripts and forms of
one institution, distinct institutions per article with a saturation curve, and a seeded sample (seed 4824, 50) of
affiliation -> institution links with the evidence to judge them. Read-only."""
from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict

from common48c import OUT, RUNS600, pcon, progress, save


def main():
    p = pcon()
    affs = [dict(r) for r in p.execute(f"""
        SELECT am.aff_pk, v.stem, b.byline_pos, b.printed byline, am.printed, am.org_text, am.faculty_text, am.dept_text,
               am.city, am.country_code, am.position_title, am.kind
        FROM affiliation_mentions am JOIN byline_mentions b USING (mention_pk)
        JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1 WHERE v.run IN {RUNS600} ORDER BY v.stem""")]
    links = defaultdict(list)
    for r in p.execute("SELECT aff_pk, inst_id, level, method FROM affiliation_links"):
        links[r["aff_pk"]].append(dict(r))
    inst = {r["inst_id"]: dict(r) for r in p.execute("SELECT * FROM institutions")}
    names = defaultdict(list)
    for r in p.execute("SELECT inst_id, name, script, n_seen FROM institution_names ORDER BY n_seen DESC"):
        names[r["inst_id"]].append((r["name"], r["script"], r["n_seen"]))
    for a in affs:
        a["links"] = [dict(l, kind=inst.get(l["inst_id"], {}).get("kind"), parent=inst.get(l["inst_id"], {}).get("parent_id"),
                           names=[n[0] for n in names.get(l["inst_id"], [])][:6]) for l in links.get(a["aff_pk"], [])]
    S = dict(affiliation_mentions_600=len(affs), articles_with_affiliation=len({a["stem"] for a in affs}),
             kinds=Counter(a["kind"] for a in affs), linked=sum(1 for a in affs if a["links"]),
             levels_per_aff=Counter("+".join(sorted(l["level"] for l in a["links"])) or "none" for a in affs),
             country_code_filled=sum(1 for a in affs if a["country_code"]))
    # institutions reached by the 600
    used = {l["inst_id"] for a in affs for l in a["links"]}
    S["institutions_reached"] = len(used)
    S["institutions_reached_by_kind"] = Counter(inst[i]["kind"] for i in used if i in inst)
    orgs = {l["inst_id"] for a in affs for l in a["links"] if l["level"] == "org"}
    S["org_level_institutions"] = len(orgs)
    S["org_level_scripts"] = Counter("+".join(sorted({n[1] or "?" for n in names.get(i, [])})) for i in orgs)
    S["org_names_per_institution"] = Counter(min(len(names.get(i, [])), 6) for i in orgs)
    S["faculties_without_parent"] = sum(1 for i in used if inst.get(i, {}).get("kind") in ("faculty", "department")
                                        and not inst[i]["parent_id"])
    # placeholder parent «org:?»: faculties of an unknown university
    reg = {r[0]: r[1] for r in p.execute("SELECT public_id, natural_key FROM id_registry WHERE kind = 'institution'")}
    S["placeholder_unknown_university"] = sorted({(reg.get(i) or "") for i in used if "org:?" in (reg.get(i) or "")})
    S["institutions_per_article"] = round(len(orgs) / len({a["stem"] for a in affs}), 3)
    # saturation: distinct org-level institutions as articles are added in random order (20 orders, seed 4824)
    by_stem = defaultdict(set)
    for a in affs:
        for l in a["links"]:
            if l["level"] == "org":
                by_stem[a["stem"]].add(l["inst_id"])
    stems = sorted({r["stem"] for r in p.execute(f"SELECT stem FROM versions WHERE is_current = 1 AND run IN {RUNS600}")})
    rnd = random.Random(4824)
    curve = defaultdict(list)
    for _ in range(20):
        order = stems[:]
        rnd.shuffle(order)
        seen = set()
        for i, s in enumerate(order, 1):
            seen |= by_stem.get(s, set())
            if i % 50 == 0:
                curve[i].append(len(seen))
    S["saturation_curve_org"] = {k: round(sum(v) / len(v), 1) for k, v in sorted(curve.items())}
    S["org_seen_once"] = sum(1 for i in orgs if sum(1 for s in by_stem.values() if i in s) == 1)
    save("c2_affiliations.json", affs)
    rnd = random.Random(4824)
    samp = rnd.sample([a for a in affs if a["links"]], 50)
    save("c2_aff_sample.json", samp)
    save("c2_summary_raw.json", S)
    progress(f"- c2_institutions.py: {len(affs)} affiliations, {len(orgs)} org-level institutions")
    print(json.dumps(S, ensure_ascii=False, indent=1, default=str))
    for i, a in enumerate(samp):
        print(f"===== {i} {a['stem']} | {a['printed'][:150]}")
        print(f"   pieces: org={a['org_text']} | fac={a['faculty_text']} | dept={a['dept_text']} | city={a['city']} "
              f"{a['country_code']} | pos={a['position_title']}")
        for l in a["links"]:
            print(f"   -> {l['level']}: {l['inst_id']} {l['kind']} parent={l['parent']} names={l['names'][:4]}")


if __name__ == "__main__":
    main()
