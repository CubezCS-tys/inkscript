"""D1: every metric built end to end from platform_v2.db (shown versions of the 600), with accepted links only.
Writes out/d_metrics_and_workload/d1_metrics.json (+ d1_networks.json for the page)."""
import collections, itertools, json, re, statistics, time
import common_d as cd

t0 = time.time()
D = cd.load()
arts, ms, works = D["arts"], D["mentions"], D["works"]
R = {"scope": "the 600 (runs v33_300_final + v33_300b_fix3, is_current=1), citation mentions without Quran/hadith",
     "warning": "600 articles spread over ~100 years and ~300 journals: these numbers show the machinery works, "
                "they do not measure anyone. Do not quote them as metrics."}

# B's census: cross-article cards judged wrong / serial / mixed are not works (precision first)
bad_cards = {wid for wid, v in D["B_verdict"].items() if v in ("wrong", "serial", "mixed")}
pk_by_id = {w["id"]: pk for pk, w in works.items()}
bad_pks = {pk_by_id[i] for i in bad_cards if i in pk_by_id}

# ---------------------------------------------------------------- times cited per cited work
by_work = collections.defaultdict(lambda: dict(pubs=set(), n=0, full=0, back=0))
for m in ms:
    if m["work"] is None:
        continue
    b = by_work[m["work"]]
    b["pubs"].add(m["pub_id"]); b["n"] += 1
    b["full" if m["kind"] == "full" else "back"] += 1
tc = sorted(((len(b["pubs"]), b["n"], pk) for pk, b in by_work.items()), reverse=True)
hist = collections.Counter(min(x[0], 6) for x in tc)
R["times_cited_cited_work"] = dict(
    cards_with_mentions=len(tc),
    by_citing_articles={("6+" if k == 6 else str(k)): v for k, v in sorted(hist.items())},
    cited_by_2plus_raw=sum(1 for x in tc if x[0] >= 2),
    cited_by_2plus_clean=sum(1 for x in tc if x[0] >= 2 and x[2] not in bad_pks),
    removed_by_B_census=len([x for x in tc if x[0] >= 2 and x[2] in bad_pks]),
    max_citing_articles=tc[0][0],
    note="times cited = distinct citing articles (WoS headline); mentions incl. back references kept beside it")
top30 = []
for n_pubs, n, pk in [x for x in tc if x[2] not in bad_pks][:30]:
    w = works[pk]
    cls = D["cls"].get(pk, {}).get("cls")
    top30.append(dict(cited_work_id=w["id"], title=w["title"], type=cls, year=w["year_greg"] or w["year_printed"],
                      citing_articles=n_pubs, mentions=n,
                      authors=[a["printed"] for a in D["work_authors"].get(pk, [])][:2]))
R["top30_clean"] = top30

# ---------------------------------------------------------------- times cited per held article (accepted links)
marc = cd.marc()


def rec_of_c999(c999):
    r = marc.execute("SELECT rec,title,journal,journal_code,year_int,type FROM records WHERE c999=?", (c999,)).fetchone()
    return dict(rec=r[0], title=r[1], journal=r[2], journal_code=r[3], year=r[4], type=r[5]) if r else None


held = {}  # source -> {c999: {pubs, mentions, works}}
srcs = {"link47_db": {pk: v["c999"] for pk, v in D["links47"].items()},
        "probeA_v3": {pk: r["c999"] for pk, r in D["decA"].items() if r["decision"] == "accept" and r.get("c999")}}
srcs["union"] = dict(srcs["probeA_v3"]); srcs["union"].update({k: v for k, v in srcs["link47_db"].items() if k not in srcs["union"]})
held_summary = {}
c999_info = {}
for s, lk in srcs.items():
    per = collections.defaultdict(lambda: dict(pubs=set(), n=0, works=set(), years=[]))
    for m in ms:
        if m["work"] in lk:
            p = per[lk[m["work"]]]
            p["pubs"].add(m["pub_id"]); p["n"] += 1; p["works"].add(m["work"])
            p["years"].append(arts[m["pub_id"]]["year"])
    for c999 in per:
        if c999 not in c999_info:
            c999_info[c999] = rec_of_c999(c999)
    held[s] = per
    inside = [c for c in per if any(a["c999"] == c for a in arts.values())]
    held_summary[s] = dict(cards_linked=len(lk), held_records_cited=len(per),
                           citing_articles=len(set().union(*[p["pubs"] for p in per.values()])) if per else 0,
                           mentions=sum(p["n"] for p in per.values()),
                           records_cited_by_2plus=sum(1 for p in per.values() if len(p["pubs"]) >= 2),
                           max_times_cited=max((len(p["pubs"]) for p in per.values()), default=0),
                           targets_inside_the_600=len(inside))
R["times_cited_held_article"] = held_summary
held_top = []
for c999, p in sorted(held["union"].items(), key=lambda kv: (-len(kv[1]["pubs"]), -kv[1]["n"]))[:15]:
    i = c999_info[c999] or {}
    held_top.append(dict(c999=c999, title=i.get("title"), journal=i.get("journal"), year=i.get("year"),
                         citing_articles=len(p["pubs"]), mentions=p["n"]))
R["held_top15_union"] = held_top
inside_600 = {a["c999"]: a["pub_id"] for a in arts.values() if a["c999"]}

# ---------------------------------------------------------------- per journal (cited journal entities)
# route 1: journals of held articles (accepted links, union); route 2: probe A's journal entities accepted (A3)
jr = collections.defaultdict(lambda: dict(pubs=set(), mids=set(), via=collections.Counter()))
for c999, p in held["union"].items():
    i = c999_info[c999]
    if i and i["journal_code"]:
        for m in ms:
            if m["work"] in p["works"]:
                j = jr[i["journal_code"]]; j["pubs"].add(m["pub_id"]); j["mids"].add(m["mention_id"]); j["via"]["article-link"] += 1
mid2pub = {m["mention_id"]: m["pub_id"] for m in ms}
a3_ent_cites = collections.defaultdict(list)
for x in D["a3_cites"]:
    e = D["a3_s2e"].get(x["source"])
    if e is None:
        continue
    a3_ent_cites[e["entity"]].append(x)
    if e["journal_decision"] == "accept" and e["journal_code"] and x["mention_id"] in mid2pub:
        j = jr[e["journal_code"]]
        if x["mention_id"] not in j["mids"]:
            j["via"]["journal-name"] += 1
        j["pubs"].add(mid2pub[x["mention_id"]]); j["mids"].add(x["mention_id"])
jtitle = {}
for code in jr:
    r = marc.execute("SELECT journal FROM records WHERE journal_code=? AND journal IS NOT NULL LIMIT 1", (code,)).fetchone()
    jtitle[code] = r[0] if r else None
jrows = sorted(([code, jtitle[code], len(v["pubs"]), len(v["mids"]), dict(v["via"])] for code, v in jr.items()),
               key=lambda r: (-r[2], -r[3]))
cited_ent_all = sorted(((e, len(v), len({x["stem"] for x in v})) for e, v in a3_ent_cites.items()), key=lambda r: -r[1])
R["journal_level"] = dict(
    held_journals_cited=len(jr), citations_to_held_journals=sum(r[3] for r in jrows),
    citing_articles=len(set().union(*[v["pubs"] for v in jr.values()])) if jr else 0,
    held_journals_cited_by_2plus_articles=sum(1 for r in jrows if r[2] >= 2),
    top15=[dict(journal_code=r[0], journal=r[1], citing_articles=r[2], citations=r[3], via=r[4]) for r in jrows[:15]],
    cited_journal_entities_all=len(a3_ent_cites),
    cited_journal_entities_2plus_articles=sum(1 for r in cited_ent_all if r[2] >= 2),
    top_cited_journal_entities=[dict(entity=e, citations=n, citing_articles=k) for e, n, k in cited_ent_all[:10]],
    note="route 1 = journal of a held article reached by an accepted article link; route 2 = probe A's A3 journal-name "
         "match (accept). A mention counted once even when both routes reach it.")

# ---------------------------------------------------------------- h-index for byline persons
byline_people = collections.defaultdict(set)
for a in D["authorships"]:
    if a["person_id"] and a["role"] in ("author", "coauthor"):
        byline_people[a["person_id"]].add(a["pub_id"])
# works of a person = catalogue records under any of their authority ids (marc.db, all 1.56M records)
held_cites = collections.defaultdict(set)  # c999 -> citing pubs (union links)
for c999, p in held["union"].items():
    held_cites[c999] = p["pubs"]
pers_rows = []
for pid in byline_people:
    recs = set()
    for aid in D["person_auth"].get(pid, []):
        for (c999,) in marc.execute("SELECT r.c999 FROM authors a JOIN records r ON r.rec=a.rec WHERE a.authority_id=?", (aid,)):
            recs.add(c999)
    counts = sorted((len(held_cites.get(c, ())) for c in recs), reverse=True)
    h = sum(1 for i, x in enumerate(counts) if x >= i + 1)
    # card route: cited-work cards whose author is linked to this person (books not held count too)
    cards = [pk for pk, al in D["work_authors"].items() if any(a["person_id"] == pid for a in al)]
    cc = sorted((len(by_work[pk]["pubs"]) for pk in cards if pk in by_work), reverse=True)
    h2 = sum(1 for i, x in enumerate(cc) if x >= i + 1)
    # same, without self-citation (citing article has this person on the byline)
    cc_ns = sorted((len(by_work[pk]["pubs"] - byline_people[pid]) for pk in cards if pk in by_work), reverse=True)
    h2ns = sum(1 for i, x in enumerate(cc_ns) if x >= i + 1)
    pers_rows.append(dict(person_id=pid, name=D["person_name"].get(pid), catalogue_records=len(recs),
                          records_cited=sum(1 for x in counts if x), cites_received_held=sum(counts), h_held=h,
                          cards_linked=len(cards), cites_received_cards=sum(cc), h_cards=h2, h_cards_no_self=h2ns))
recs_all = [p["catalogue_records"] for p in pers_rows]
R["h_index"] = dict(
    byline_persons=len(pers_rows),
    with_authority=sum(1 for p in pers_rows if p["catalogue_records"]),
    their_catalogue_records=sum(recs_all), median_records=statistics.median(recs_all) if recs_all else 0,
    route_held_links=dict(h_ge1=sum(1 for p in pers_rows if p["h_held"] >= 1), h_ge2=sum(1 for p in pers_rows if p["h_held"] >= 2),
                          persons_cited=sum(1 for p in pers_rows if p["cites_received_held"])),
    route_author_linked_cards=dict(h_ge1=sum(1 for p in pers_rows if p["h_cards"] >= 1),
                                   h_ge2=sum(1 for p in pers_rows if p["h_cards"] >= 2),
                                   h_ge1_without_self=sum(1 for p in pers_rows if p["h_cards_no_self"] >= 1)),
    top=sorted(pers_rows, key=lambda p: (-max(p["h_held"], p["h_cards"]), -p["cites_received_held"] - p["cites_received_cards"]))[:12])
# why: the mass of citable records versus the citing pool
total_records_of_people = sum(recs_all)

# ---------------------------------------------------------------- self-citation (probe C's judged list)
sc = json.load(open(cd.C + "c1_selfcite_judged.json", encoding="utf-8"))
scr = json.load(open(cd.C + "c1_selfcite.json", encoding="utf-8"))
per = collections.Counter()
per_name = {}
for it, raw in zip(sc["items"], scr):
    if it["verdict"] == "right":
        per[raw["person_id"]] += 1
        per_name[raw["person_id"]] = it["byline"]
R["self_citation"] = dict(
    view_rows=sc["summary"]["rows"], judged_right=sc["summary"]["verdicts"]["right"], provenance_notes=sc["summary"]["verdicts"]["provenance"],
    wrong=sc["summary"]["verdicts"]["wrong"], missed_by_view=sc["summary"]["missed_by_view_name_equal"],
    persons_self_citing=len(per), articles_with_self_citation=len({raw["stem"] for it, raw in zip(sc["items"], scr) if it["verdict"] == "right"}),
    byline_persons=len(byline_people), share_persons=round(len(per) / max(1, len(byline_people)), 3),
    per_person_hist=dict(collections.Counter(per.values())),
    top=[dict(person_id=p, byline=per_name[p], self_cites=n) for p, n in per.most_common(8)],
    note="judged by probe C (agent). Self-citation counted per (citing article, cited work, person).")
# self-citation share of the citations the persons receive in the card route
selfc = sum(p["cites_received_cards"] for p in pers_rows) - sum(
    sum(len(by_work[pk]["pubs"] - byline_people[p["person_id"]]) for pk, al in D["work_authors"].items()
        if pk in by_work and any(a["person_id"] == p["person_id"] for a in al)) for p in pers_rows)
R["self_citation"]["share_of_cites_received_by_byline_persons_card_route"] = (
    f"{selfc} of {sum(p['cites_received_cards'] for p in pers_rows)}")

# ---------------------------------------------------------------- co-authorship
nodes = set(byline_people)
pub_people = collections.defaultdict(set)
for pid, pubs in byline_people.items():
    for p in pubs:
        pub_people[p].add(pid)
edges = collections.Counter()
for p, ps in pub_people.items():
    for a, b in itertools.combinations(sorted(ps), 2):
        edges[(a, b)] += 1
comps = cd.components(nodes, list(edges))
size_hist = collections.Counter(len(c) for c in comps)
# catalogue-wide ego network: co-authors of these persons over the whole catalogue (authority ids)
cat_co = collections.Counter()
cat_auth_edges = set()
for pid in byline_people:
    mine = set(D["person_auth"].get(pid, []))
    for aid in mine:
        for (rec,) in marc.execute("SELECT rec FROM authors WHERE authority_id=?", (aid,)):
            for (oth,) in marc.execute("SELECT authority_id FROM authors WHERE rec=? AND authority_id IS NOT NULL", (rec,)):
                if oth not in mine:
                    cat_auth_edges.add((pid, oth))
R["coauthorship"] = dict(
    nodes=len(nodes), edges=len(edges), repeated_pairs=sum(1 for v in edges.values() if v >= 2),
    components=len(comps), isolated=size_hist.get(1, 0), largest_component=len(comps[0]) if comps else 0,
    component_sizes=dict(sorted(size_hist.items())),
    articles_with_2plus_persons=sum(1 for ps in pub_people.values() if len(ps) >= 2),
    catalogue_wide_coauthor_links=len(cat_auth_edges),
    catalogue_wide_persons_with_a_coauthor=len({a for a, b in cat_auth_edges}),
    note="inside the 600 two persons are joined only if they sign one of the 600 together; catalogue-wide uses each "
         "person's authority ids over all 1.56M records (all records, any role), so it already works at full scale.")
coauth_net = dict(nodes=[dict(id=p, name=D["person_name"].get(p), articles=len(byline_people[p])) for p in nodes if
                         any(p in e for e in edges)],
                  edges=[dict(a=a, b=b, n=n) for (a, b), n in edges.items()])

# ---------------------------------------------------------------- bibliographic coupling ("co-citation" in B) and co-citation
def coupling(pubset, drop_bad=True):
    w2p = collections.defaultdict(set)
    for m in ms:
        if m["work"] is not None and m["pub_id"] in pubset and not (drop_bad and m["work"] in bad_pks):
            w2p[m["work"]].add(m["pub_id"])
    shared = {w: ps for w, ps in w2p.items() if len(ps) >= 2}
    e = collections.defaultdict(set)
    for w, ps in shared.items():
        for a, b in itertools.combinations(sorted(ps), 2):
            e[(a, b)].add(w)
    nodes = set().union(*shared.values()) if shared else set()
    comps = cd.components(nodes, list(e))
    return shared, e, nodes, comps


pub_all = set(arts)
art_with_cards = {m["pub_id"] for m in ms if m["work"] is not None}
for label, drop in (("raw", False), ("clean", True)):
    shared, e, nodes_c, comps_c = coupling(pub_all, drop)
    R.setdefault("coupling", {})[label] = dict(
        shared_works=len(shared), articles_in_network=len(nodes_c), of_articles_with_cards=len(art_with_cards),
        edges=len(e), components=len(comps_c), largest_component=len(comps_c[0]) if comps_c else 0,
        second_component=len(comps_c[1]) if len(comps_c) > 1 else 0,
        edges_with_2plus_shared_works=sum(1 for v in e.values() if len(v) >= 2))
R["coupling"]["note"] = ("Probe B called this co-citation; in bibliometrics, articles joined by a shared cited work is "
                        "bibliographic coupling. 'clean' drops the cards probe B's census judged wrong, serial or mixed.")
shared, e, nodes_c, comps_c = coupling(pub_all, True)
largest = set(comps_c[0]) if comps_c else set()
coupling_net = dict(
    nodes=[dict(pub_id=p, stem=arts[p]["stem"], title=arts[p]["title"], year=arts[p]["year"],
                journal=D["journal_title"].get(arts[p]["journal_id"]), journal_id=arts[p]["journal_id"],
                in_largest=p in largest) for p in nodes_c],
    edges=[dict(a=arts[a]["stem"], b=arts[b]["stem"], works=[works[w]["title"] for w in ws], n=len(ws)) for (a, b), ws in e.items()])
# true co-citation: pairs of works cited together in one article
w_in_pub = collections.defaultdict(set)
for m in ms:
    if m["work"] is not None and m["work"] not in bad_pks:
        w_in_pub[m["pub_id"]].add(m["work"])
cocit = collections.Counter()
for p, ws in w_in_pub.items():
    for a, b in itertools.combinations(sorted(ws), 2):
        cocit[(a, b)] += 1
cc2 = [(k, v) for k, v in cocit.items() if v >= 2]
R["cocitation_work_pairs"] = dict(
    pairs_cocited_once=sum(1 for v in cocit.values() if v == 1), pairs_cocited_2plus=len(cc2),
    pairs_cocited_3plus=sum(1 for k, v in cc2 if v >= 3),
    top=[dict(a=works[a]["title"], b=works[b]["title"], articles=v) for (a, b), v in sorted(cc2, key=lambda kv: -kv[1])[:10]],
    note="co-citation proper: two cited works named together in one citing article; strength = number of such articles")

# ---------------------------------------------------------------- trending: citations by year
cy = collections.Counter()  # citing year of mentions
cited_y = collections.Counter()  # publication year of the cited work (cards with a year)
age = []
held_by_citing_year = collections.Counter()
for m in ms:
    y = arts[m["pub_id"]]["year"]
    yy = y if y and y > 1700 else None
    if yy:
        cy[yy // 10 * 10] += 1
    w = works.get(m["work"]) if m["work"] else None
    if w and w["year_greg"] and 1000 < w["year_greg"] <= 2026:
        cited_y[w["year_greg"] // 10 * 10] += 1
        if yy and yy >= w["year_greg"]:
            age.append(yy - w["year_greg"])
    if m["work"] in srcs["union"] and yy:
        held_by_citing_year[yy // 10 * 10] += 1
art_years = collections.Counter((a["year"] // 10 * 10) if a["year"] and a["year"] > 1700 else "hijri/none" for a in arts.values())
R["trending"] = dict(
    citing_articles_by_decade={str(k): v for k, v in sorted(art_years.items(), key=lambda kv: str(kv[0]))},
    mentions_by_citing_decade={str(k): v for k, v in sorted(cy.items())},
    mentions_by_cited_decade={str(k): v for k, v in sorted(cited_y.items())},
    held_mentions_by_citing_decade={str(k): v for k, v in sorted(held_by_citing_year.items())},
    citation_age_median=statistics.median(age) if age else None, citation_age_n=len(age),
    share_of_mentions_cited_within_2_years=round(sum(1 for a in age if a <= 2) / len(age), 3) if age else None,
    share_within_5_years=round(sum(1 for a in age if a <= 5) / len(age), 3) if age else None,
    cited_works_with_year=sum(1 for w in works.values() if w["year_greg"]),
    held_works_cited_in_two_different_citing_years=sum(
        1 for c999, p in held["union"].items() if len({arts[x]["year"] for x in p["pubs"]}) >= 2))

# ---------------------------------------------------------------- impact factor ingredients
# citable items per journal-year from the catalogue, for the held journals cited
jif = []
window_hits = 0
window_all = 0
for c999, p in held["union"].items():
    i = c999_info[c999]
    if not i or not i["year"]:
        continue
    for pub in p["pubs"]:
        cyr = arts[pub]["year"]
        if cyr and cyr > 1700:
            window_all += 1
            if 1 <= cyr - i["year"] <= 2:
                window_hits += 1
for code, title, npubs, ncit, via in jrows[:8]:
    rows = marc.execute("SELECT year_int, count(*) FROM records WHERE journal_code=? AND type=? GROUP BY year_int",
                        (code, "بحوث ومقالات")).fetchall()
    yrs = {y: n for y, n in rows if y}
    if yrs:
        last = max(yrs)
        jif.append(dict(journal_code=code, journal=title, citations_from_600=ncit, years_catalogued=f"{min(yrs)}-{last}",
                        citable_items_total=sum(yrs.values()),
                        citable_items_last_two_years={str(last - 1): yrs.get(last - 1, 0), str(last): yrs.get(last, 0)}))
citing_journals = {a["journal_id"] for a in arts.values() if a["journal_id"]}
R["impact_factor_ingredients"] = dict(
    held_article_citations_with_both_years=window_all, of_which_in_2_year_window=window_hits,
    citing_journals_in_600=len(citing_journals),
    example_denominators=jif,
    note="JIF(Y) = citations in year Y from all indexed articles to items the journal published in Y-1 and Y-2, divided "
         "by its citable items of Y-1 and Y-2. The denominator is ready in the catalogue (records by journal_code, "
         "year_int, type بحوث ومقالات). The numerator needs every article of year Y parsed (the citing window), not 600 "
         "articles spread over a century.")
marc.close()

# ---------------------------------------------------------------- fate of every citation (by kind) for D2 / the page
held_ids = set(srcs["union"])
rel_ids = {pk for pk, r in D["decA"].items() if r["decision"] == "relation"}
jheld_mids = set().union(*[v["mids"] for v in jr.values()]) if jr else set()
doi_ids = set(D["extA"])
# journal-held via the full citation mention id only covers full mentions; extend to their back references
full_jheld = {m["mention_pk"] for m in ms if m["mention_id"] in jheld_mids}
fate2 = collections.defaultdict(collections.Counter)
for m in ms:
    k = D["cls"].get(m["work"], {}).get("cls", "no card (short form / unresolved)") if m["work"] else "no card (short form / unresolved)"
    if m["work"] in held_ids:
        f = "held by Mandumah"
    elif m["work"] in rel_ids:
        f = "review/study/part held"
    elif m["mention_id"] in jheld_mids or m["full_pk"] in full_jheld:
        f = "journal held"
    elif m["work"] in doi_ids:
        f = "DOI found (Crossref/OpenAlex)"
    else:
        f = "unlinkable"
    fate2[k][f] += 1
tot = collections.Counter()
for k, v in fate2.items():
    tot.update(v)
N = sum(tot.values())
R["citation_fate"] = dict(total_mentions=N, totals=dict(tot), shares={k: round(v / N, 4) for k, v in tot.items()},
                          by_kind={k: dict(v) for k, v in sorted(fate2.items(), key=lambda kv: -sum(kv[1].values()))},
                          inside_the_600=sum(1 for m in ms if m["work"] in held_ids and srcs["union"][m["work"]] in inside_600),
                          note="held = probe A v3 accepts ∪ link47 accepts. DOI = measured Crossref/OpenAlex hit ≥0.8 "
                               "(only ~600 of 1,068 Latin articles were looked up; probe A projects ~8% of all citations "
                               "for full lookup). Precedence: held > relation > journal held > DOI > unlinkable.")
R["runtime_s"] = round(time.time() - t0, 1)
cd.save("d1_metrics.json", R)
cd.save("d1_networks.json", dict(coupling=coupling_net, coauthorship=coauth_net, persons=pers_rows))
print(json.dumps({k: R[k] for k in R if k not in ("top30_clean",)}, ensure_ascii=False, indent=1)[:9000])
