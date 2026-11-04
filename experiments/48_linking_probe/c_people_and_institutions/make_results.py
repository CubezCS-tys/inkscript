"""Collects probe C's headline numbers from the saved summaries into results.json, and writes examples.json."""
import json
from common48c import OUT, save, wilson, progress

L = lambda n: json.load(open(OUT / n))
b, sp, hx = L("c1_bylines_summary.json"), L("c1_splits_summary.json"), L("c1_hard_examples.json")
au, pe, ci = L("c1_authority_judged.json")["summary"], L("c1_person_judged.json")["summary"], L("c1_cited_judged.json")["summary"]
cs, sc = L("c1_cited_summary.json"), L("c1_selfcite_judged.json")["summary"]
c2, aj, xs, cu = L("c2_summary_raw.json"), L("c2_aff_judged.json")["summary"], L("c2_cross_script_judged.json"), L("c2_catalogue_universe.json")

N = 600
per_art = lambda x: round(x / N, 3)
# C3: uncertain decisions per article (each from a count above; see NOTES.md for what each is)
unc = dict(
    byline_no_authority_real_person=dict(n=61 - 12, note="61 provisional bylines minus ~12 that are roles/corporate bodies/initials-only, which stay unlinked"),
    catalogue_only_person_not_on_byline=dict(n=46, note="a catalogue contributor with no byline: missed byline, reviewed book's author, or the twin of a provisional byline"),
    weak_name_rejected=dict(n=2, note="both looked right on reading (al-Nadwi, Kenneth Clark): a person may accept them"),
    cited_author_2plus_holders=dict(n=cs["exact_holders"].get("2-5", 0) + cs["exact_holders"].get("6+", 0),
                                    note="the cited name is carried by 2+ authority ids and the work is not linked to a record"),
    affiliation_wrong_or_partial=dict(n=round(374 * (aj["verdicts"]["wrong"] + aj["verdicts"]["partial"] + aj["verdicts"]["unsure"]) / aj["n"]),
                                      note="374 linked affiliations x the 22% judged wrong/partial/unsure"),
)
for v in unc.values():
    v["per_article"] = per_art(v["n"])
must = unc["byline_no_authority_real_person"]["n"] + unc["catalogue_only_person_not_on_byline"]["n"] + \
    unc["weak_name_rejected"]["n"] + unc["affiliation_wrong_or_partial"]["n"]
R = dict(
    probe="c_people_and_institutions", date="2026-10-21", judged_by="agent (Claude), by reading the evidence",
    data=dict(articles=N, runs=["v33_300_final", "v33_300b_fix3"], platform="platform_v2.db (is_current=1)",
              catalogue="marc.db (2.2M headings) + experiment 47's heading-key index"),
    C1_bylines=dict(byline_person_authorships=b["byline_person_authorships"], byline_mentions=b["byline_mentions_600"],
                    with_authority_id=b["with_authority_id"],
                    how=dict(b["how_byline"]), methods=dict(b["method_byline"]),
                    no_catalogue_record=0, articles_without_byline_person=b["articles_with_no_byline_person"],
                    catalogue_only_authorships=b["authorships_600"] - b["authorships_with_byline_mention"],
                    provisional_twins_of_catalogue_only=dict(articles=11, note="the catalogue names the same people "
                                                             "(transliteration, short name, role, initials); each such author is counted twice")),
    C1_ambiguity=dict(exact_holders_of_printed_name=b["exact_holders_dist"],
                      loose_holders_given_plus_surname=b["loose_holders_dist"],
                      linked_heading_shared_with_other_ids=b["linked_heading_homonyms_dist"],
                      catalogue_heading_keys_by_ids=hx["heading_keys_by_number_of_authority_ids"],
                      hard_examples=hx["examples"]),
    C1_splits=dict(catalogue_spellings_per_authority=sp["catalogue_hist"], our_authorities=sp["our_authorities"],
                   our_variant_kinds=sp["our_variant_kinds"],
                   print_vs_heading=dict(token_subset=117, weak_given_name=22, transliteration=7, exact_holders_0=b["exact_holders_dist"].get("0")),
                   our_heading_also_held_by_other_ids=sp["linked_heading_shared_with_other_ids"]),
    C1_authority_errors=au,
    C1_person_link_precision=pe,
    C1_cited_authors=dict(rows=cs["cited_author_rows_600"], linked=cs["linked"], linked_share=round(cs["linked"] / cs["cited_author_rows_600"], 3),
                          by_method=cs["by_method"], kinds=cs["kinds"], exact_holders=cs["exact_holders"],
                          judged_linked=ci["linked_sample"], judged_unique_name_unlinked=ci["unique_name_unlinked_sample"]),
    C1_self_citation=sc,
    C2_institutions=dict(affiliation_mentions=c2["affiliation_mentions_600"], kinds=c2["kinds"], linked=c2["linked"],
                         levels=c2["levels_per_aff"], org_level_institutions=c2["org_level_institutions"],
                         institutions_reached_by_kind=c2["institutions_reached_by_kind"],
                         orphan_faculty_department_keys=len(c2["placeholder_unknown_university"]),
                         org_institutions_per_1000_articles=round(c2["org_level_institutions"] / N * 1000),
                         saturation_curve_org=c2["saturation_curve_org"], org_seen_once=c2["org_seen_once"],
                         precision=aj, cross_script=dict(already_both_scripts=xs["already_holding_both_scripts"],
                                                         confirmed_splits=xs["confirmed_splits"]),
                         catalogue_thesis_universities=dict(theses=cu["theses_with_university"],
                                                            distinct=cu["distinct_university_strings"],
                                                            curve=cu["saturation_curve"]),
                         projection_1M_org_level=dict(low=1900, high=20000,
                                                      method="from 208 at 600 articles: growth exponent 0.3 after 600 (the shape of the catalogue's own thesis-university curve) gives ~1,900; exponent 0.6 (half the measured early slope, for the long tail of ministries, schools, hospitals and foreign bodies) gives ~20,000; the measured early exponent 0.85 would give ~110,000 and is not credible"),
                         openalex=dict(status="blocked", calls=6, source="openalex",
                                       why="HTTP 429: the free daily budget shared by this server's IP was used up ($0 remaining, resets 00:00 UTC); no API key",
                                       ready="c2_openalex.py (seed 4824, 50 universities, resumable, cached, logged)")),
    C3_workload=dict(uncertain_per_article=unc, must_decide_per_article=per_art(must),
                     safe_to_leave_unlinked=dict(cited_author_name_only=cs["unlinked_with_one_holder"],
                                                 cited_author_2plus=unc["cited_author_2plus_holders"]["n"],
                                                 note="per 600 articles; leaving these unlinked costs recall, not precision"),
                     projection_1M=None),
    costs=dict(wall_seconds_total_all_scripts="about 90", peak_rss_mb=72, external_calls="6 OpenAlex (all 429, logged)",
               paid_calls=0))
d = R["C3_workload"]
d["projection_1M"] = dict(
    article_level_decisions=round(must / N * 1_000_000),
    minutes_each=1.5, hours=round(must / N * 1_000_000 * 1.5 / 60),
    hours_per_corrector_300=round(must / N * 1_000_000 * 1.5 / 60 / 300, 1),
    person_level_authority_review=dict(authorities_3plus_records_est=int(721_138 * 482 / 675), minutes_each=2,
                                       hours_per_corrector_300=round(721_138 * 482 / 675 * 2 / 60 / 300, 1),
                                       note="reviewing every authority with 3+ records once; ~15% hold another person's records; triage by citations received cuts this"),
    institution_level=dict(org_entities_est="1,900-20,000", minutes_each=3,
                           note="one merge/name decision per institution, not per article"))
save("results.json", R)
progress("- results.json written")
print(json.dumps(R["C3_workload"], indent=1))
