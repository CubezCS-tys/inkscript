"""results.json and examples.json for probe D, from d1/d2/d3/page_data."""
import json
import common_d as cd

d1 = json.load(open(cd.OUT + "d1_metrics.json", encoding="utf-8"))
d2 = json.load(open(cd.OUT + "d2_growth.json", encoding="utf-8"))
d3 = json.load(open(cd.OUT + "d3_workload.json", encoding="utf-8"))
pg = json.load(open(cd.OUT + "page_data.json", encoding="utf-8"))
nets = json.load(open(cd.OUT + "d1_networks.json", encoding="utf-8"))
f = d1["citation_fate"]
cur = d2["curves"]

coverage = dict(
    measured_600=dict(
        mentions=f["total_mentions"],
        inside_the_corpus=dict(n=f["inside_the_600"], share=round(f["inside_the_600"] / f["total_mentions"], 5)),
        inside_the_catalogue=dict(share_union=f["shares"]["held by Mandumah"], share_probeA_strict="2.7-2.9%"),
        review_study_part_held=f["shares"]["review/study/part held"],
        journal_held_not_already_held=f["shares"]["journal held"],
        outside_by_doi_measured=f["shares"]["DOI found (Crossref/OpenAlex)"], outside_by_doi_projected="~8% (probe A)",
        nowhere=f["shares"]["unlinkable"], nowhere_with_full_doi_lookup="~85%"),
    subsets=dict(
        held_share_mean_by_size={n: cur[n]["held_share"]["mean"] for n in cur},
        held_share_sd_by_size={n: cur[n]["held_share"]["sd"] for n in cur},
        inside_corpus_mentions_by_size={n: cur[n]["inside_corpus_mentions"]["mean"] for n in cur},
        coupled_share_of_citing_articles={n: round(cur[n]["coupled_articles"]["mean"] / cur[n]["citing_articles"]["mean"], 3) for n in cur},
        shared_mention_share={n: cur[n]["shared_mention_share"]["mean"] for n in cur},
        fits=d2["power_law_fits_100_to_600"]),
    projection=[
        dict(corpus=600, inside_corpus="0.01% (1 citation)", inside_catalogue="~3%", doi="~5% measured / 8% full",
             nowhere="~86-88%", shared_works="100", coupled_share_of_citing="24%", basis="measured"),
        dict(corpus=3000, inside_corpus="~0.05% (~25 of ~48k): grows with N², mentions × corpus share",
             inside_catalogue="~3% (flat from 50 to 600; a property of what is cited)", doi="~8%", nowhere="~85%",
             shared_works="~1,000 (fit N^1.4; range 500-2,000)", coupled_share_of_citing="~35-45% (guess)",
             basis="extrapolated from 100-600 random subsets"),
        dict(corpus=1_000_000, inside_corpus="→ the catalogue share, ~2-3%, once the corpus is most of the catalogue",
             inside_catalogue="~3% (+ up to ~1 pt from matcher fixes; more if the field mix tilts to Arabic social science)",
             doi="~8%", nowhere="~85%",
             shared_works="not extrapolable: saturates around the classical core and each field's canon",
             coupled_share_of_citing="most humanities articles; unknown for sciences", basis="reasoned, not measured"),
    ],
    assumptions=[
        "The held share is flat across subset sizes (3.55% at 50 → 3.22% at 600; sd falls 1.7 → 0.2 pt): parsing more "
        "citing articles does not raise it. It is fixed by what authors cite (books 45%, Latin-script 57%) and what "
        "Mandumah holds.",
        "Inside-the-corpus citations rise from 0 to the catalogue share as the corpus fills the catalogue: at 1M "
        "scanned articles out of 1.56M catalogue records, most held targets are parsed, so inside-corpus ≈ held share.",
        "Growth in a *field* is faster than in a random mix: picking whole journal runs or one field would raise "
        "shared works and inside-corpus links at 3,000 well above these random-subset figures.",
        "None of the extrapolations is measured. The 1M row is a reasoned bound, not a fit.",
    ])

R = dict(
    probe="d_metrics_and_workload", date="2026-10-21",
    judged_by="no new judging: probe D reuses the verdicts of probes A, B, C (all agents, Claude); the metrics are "
              "computed, not judged",
    external_calls=0, paid_calls=0,
    warning=d1["warning"],
    D1_metrics=dict(
        times_cited_cited_work=d1["times_cited_cited_work"],
        times_cited_held_article=d1["times_cited_held_article"],
        journal_level=dict((k, v) for k, v in d1["journal_level"].items() if k not in ("top15", "top_cited_journal_entities")),
        h_index=dict((k, v) for k, v in d1["h_index"].items() if k != "top"),
        self_citation=dict((k, v) for k, v in d1["self_citation"].items() if k != "top"),
        coauthorship=d1["coauthorship"], coupling=d1["coupling"], cocitation_work_pairs=dict(
            (k, v) for k, v in d1["cocitation_work_pairs"].items() if k != "top"),
        trending=dict((k, d1["trending"][k]) for k in ("citation_age_median", "share_of_mentions_cited_within_2_years",
                                                         "share_within_5_years", "held_works_cited_in_two_different_citing_years",
                                                         "citing_articles_by_decade")),
        impact_factor=dict((k, v) for k, v in d1["impact_factor_ingredients"].items() if k != "example_denominators")),
    D2_coverage=coverage,
    D3_workload=dict(rows=[dict((k, r.get(k)) for k in ("rank", "probe", "decision", "per_article", "decisions_1M", "minutes",
                                                       "hours_1M", "hours_per_corrector", "hours_1M_prioritised"))
                           for r in d3["rows"]],
                     total_hours_1M=d3["total_hours_1M"], hours_per_corrector=d3["hours_per_corrector"],
                     working_days_team_300=d3["working_days_team"]),
    cost=dict(d1_s=d1["runtime_s"], d1_rss_mb=66, d2_s=d2["runtime_s"], note="d1 is slow only because marc.db pages "
              "were read cold on a swapping server (process in state D, 3% CPU); every query is indexed"),
)
cd.save("results.json", R)

ex = []
for cdx in pg["example_cards"]:
    ex.append(dict(kind=f"{cdx['probe']} card", verdict=cdx["verdict"], what=cdx["title"],
                   citation=dict(stem=cdx["stem"], page=cdx["page"], note_id=cdx["note_id"], mention_id=cdx["mention_id"],
                                 printed=cdx["printed"]),
                   matched_to=cdx["matched_to"], crop=cdx["crop"] and cdx["crop"]["file"], note=cdx["lesson"]))
# metric-level examples
top = d1["top30_clean"][0]
ex.append(dict(kind="D1 times cited (cited work)", verdict="computed", what="most cited work in the 600 after B's census",
               matched_to=f"{top['cited_work_id']} «{top['title']}»", note=f"{top['citing_articles']} citing articles, {top['mentions']} mentions"))
h = d1["held_top15_union"][0]
ex.append(dict(kind="D1 times cited (held article)", verdict="computed", what="the only held record cited by 2 of the 600",
               matched_to=f"catalogue c999 {h['c999']} «{h['title']}» ({h['year']})",
               note="every other held record reached by an accepted link is cited once: times cited is a list of 1s"))
p = [x for x in nets["persons"] if x["h_held"] >= 1][0]
ex.append(dict(kind="D1 h-index", verdict="computed", what="a byline person with h = 1 through accepted catalogue links",
               matched_to=f"person {p['person_id']} {p['name']}", note=f"{p['catalogue_records']} catalogue records, "
               f"{p['records_cited']} cited, {p['cites_received_held']} citations; no person in the 600 reaches h = 2"))
cc = d1["cocitation_work_pairs"]["top"][0]
ex.append(dict(kind="D1 co-citation pair", verdict="computed", what="the strongest co-cited pair",
               matched_to=f"«{cc['a']}» + «{cc['b']}»", note=f"cited together by {cc['articles']} articles"))
e = max(pg["cocitation_network"]["edges"], key=lambda x: x["n"])
ex.append(dict(kind="D1 coupling edge", verdict="computed", what="the strongest coupling between two articles",
               matched_to=f"{e['a']} — {e['b']}", note=f"{e['n']} shared works: " + ", ".join(e["works"][:6])))
cd.save("examples.json", ex)
print(json.dumps(R["D2_coverage"]["subsets"]["coupled_share_of_citing_articles"]), len(ex))
