"""results.json: the headline numbers (every count from the files in out/a_cited_to_catalogue/)."""
import json, math
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n); h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return [round((c - h) / d, 3), round((c + h) / d, 3)]
def P(r, n, u=0): return dict(right=r, wrong=n - r - u, unsure=u, n=n, strict=round(r / n, 3), wilson95_strict=wilson(r, n))
R = dict(
  judged_by="an agent (Claude, probe A), reading each printed citation beside the record; not a person",
  data=dict(cited_works=5478, citation_mentions_no_quran=9775, on_cards=8693, off_cards_short_or_unresolved=1082,
            note="platform_v2.db as of 2026-10-21 14:18 (5,481 cards, 3 merged)"),
  A1=dict(
    type_distribution_works=dict(book=2483, journal_article=1418, turath=282, other=292, chapter=225, thesis=225, website=179,
                                 conference_paper=165, report=134, legal=44, news=31),
    type_distribution_mentions=dict(book=4178, journal_article=1833, turath=952, other=374, chapter=340, thesis=303, website=226,
                                    conference_paper=201, report=174, legal=61, news=51),
    type_classifier_note="regex rules over parsed fields + printed text (classify.py); not separately judged",
    decisions_v3=dict(accept=207, relation_review_study_part=132, candidate=56, link47_only=32, none=5051),
    accept_by_type=dict(journal_article=166, thesis=22, conference_paper=7, other=6, book=4, report=1, website=1),
    arabic_script_catalogue_types=dict(works=568, accepted=175, share=0.308),
    latin_script_catalogue_types=dict(works=1240, accepted=20),
    precision=dict(
      sample1_score_bands_seed4801=dict(note="60 works: by total score, top candidate right?", ge085=P(9, 9), b075_085=P(7, 9, 1), b065_075=P(4, 9, 1), b055_065=P(1, 9), lt055=P(0, 9),
                                        other_types_ge07="0 holdings; 11 of 15 are reviews/studies/parts (relations)"),
      v2_fresh_draw_30_accepted=P(26, 30, 4),
      v3_fresh_draw_20_accepted=P(18, 20, 1),
      v3_on_all_judged_accepted=dict(P(44, 45, 1), note="not independent: v3's two changes were made after reading these"),
      candidates_10=P(1, 10, 3),
      recall_none_40=dict(held=0, n=40, wilson95=wilson(0, 40), note="20 catalogue-type + 20 Arabic-script, unlinked; hand-searched by author and title")),
    link47=dict(accepted=181, same_target_as_mine=149, different_target=0, link47_only=32, mine_only=58,
                sample30=P(25, 30, 4), note="link47-only in the sample: 3 right, 4 unsure, 1 wrong"),
    estimated_held_share=dict(works_point=0.039, works_range=[0.035, 0.045],
                              of_catalogue_type_works=0.117, of_arabic_catalogue_type_works="~0.33",
                              mentions_accepted=266, mentions_share_point=0.029, mentions_range=[0.026, 0.036],
                              related_item_held_mentions=246, related_share=0.025)),
  A2=dict(
    external_calls=dict(total=1314, crossref_ok=1040, crossref_429=10, openalex_ok=99, openalex_429=161, openalex_400=4,
                        note="OpenAlex: the anonymous daily budget of this IP was spent after 99 searches (429 'Insufficient budget'); "
                             "using the owner's key was refused by the permission system, so the OpenAlex part stops at 99"),
    match_rate_ge08=dict(crossref_lat_article="280/500 (56%)", openalex_lat_article_title_search="50/99 (51%)",
                         union_on_41_sent_to_both="28/41 (both 23)", crossref_lat_book="47/300 (16%)",
                         crossref_ara_article="3/20 (+1 at 0.79), all four already held by Mandumah (DOIs 10.34120 Kuwait Univ., 10.47337 Mandumah)",
                         crossref_ara_book="0/20", openalex_arabic="not measured (budget)"),
    precision_seed4802=dict(all_40=P(31, 40, 2), articles_ge08=P(29, 30), books=P(1, 8, 1)),
    dois_gained=dict(lat_article_works_crossref=280, projected_all_latin_articles="~600 of 1,068 (Crossref alone), ~650 with OpenAlex"),
  ),
  A3=dict(journal_citations=1736, naming_a_source=1696, distinct_strings=1236, keys=1162, entities=1142, merged_entities=80,
          merge_precision=dict(right=74, wrong=2, unsure=4, n=80),
          decisions=dict(arabic_accept=153, arabic_family=5, arabic_candidate=1, arabic_none=110, latin_accept_confirmed=16, latin_candidate=13, latin_none=844),
          citations_by_decision=dict(accept=313, candidate=28, family=8, none=1341, no_entity=6),
          held_journal_share_of_journal_citations=dict(accepted=round(313 / 1696, 3), estimated_range=[0.17, 0.24]),
          sample_seed4803=dict(accept=P(12, 13), none_correct=dict(right=24, wrong=2, unsure=1, n=27), overall=P(36, 40, 1)),
          crossref_journals=dict(looked_up=200, sim_ge095="79 entities, 212 of 548 citations", spot_check="7 of 7 at ≥0.95 right; 'Language'→'Languages' (0.94) wrong")),
  shares_of_all_9775_citations=dict(
    cited_work_held_by_mandumah="2.9% (266 accepted mentions = 2.7%; with link47-only and candidates 2.6–3.6%)",
    a_review_or_study_of_it_held="2.5% (246 mentions; a relation, not the work)",
    its_journal_held="3.2% of all (313), = 18.5% of journal citations",
    linkable_externally_doi="~8% (Latin journal articles: 1,349 mentions × ~0.6 × 0.97)",
    unlinkable="~86%: Arabic books 25%, Latin books 18%, turath 10%, short forms / unresolved back references off any card 11%, "
               "Arabic articles/theses Mandumah does not hold ~5%, chapters, web, reports, laws, news, other ~13%"),
  cost=dict(matcher_s=381, matcher_rss_mb=63, per_work_s=0.07, decide_s="<10", a3_local_s="<10",
            external="Crossref ~1 req/s: 1,050 calls ≈ 20 min; OpenAlex 264 calls"),
)
json.dump(R, open(OUT + "results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(R["A1"]["precision"], ensure_ascii=False)[:600])
