"""results.json: the headline numbers, from the judged files."""
import json
from db import OUT
d = json.load(open(f"{OUT}/distribution.json"))["all654"]
b1 = json.load(open(f"{OUT}/b1_judged.json"))["summary"]
cx = json.load(open(f"{OUT}/cross_article_judged.json"))["summary"]
b2 = json.load(open(f"{OUT}/b2_judged.json"))["summary"]
cards = json.load(open(f"{OUT}/cards_dump.json"))
KIND = ["classical lexicon", "classical biographical dictionary", "NOT A WORK: six poets' diwans over-merged",
        "classical grammar (Sibawayh)", "classical (Ibn Khaldun, Muqaddima)", "classical geography (Yaqut)",
        "classical bibliography (Ibn al-Nadim)", "classical lexicon", "classical (Ibn Khaldun) - same work as #5, split",
        "classical grammar (Ibn Jinni)", "classical history (Ibn al-Athir)", "classical adab (al-Isfahani)",
        "classical biographical (Yaqut)", "hadith collection (al-Bukhari)", "classical biographical (al-Suyuti)",
        "classical history (Ibn Kathir)", "modern reference book (al-Zirikli, 1954-59)", "Ottoman-era bibliography (Hajji Khalifa)",
        "classical tafsir (Abu Hayyan)", "classical lexicon (Ibn Faris)", "classical grammar (Ibn al-Anbari)",
        "classical grammar (Ibn 'Aqil)", "hadith collection (Muslim)", "modern dictionary (Arabic Language Academy)",
        "classical history (Ibn al-Athir) - same work as #11, split", "NOT A WORK: magazine al-Adab, different issues",
        "classical adab (al-Jahiz)", "classical (al-Ghazali)", "classical biographical (al-Humaydi)",
        "modern book (Jurji Zaydan)"]
top = sorted(cards, key=lambda c: (-c["n_pubs"], -c["n_mentions"]))[:30]
res = {
 "probe": "b_works_and_backrefs", "date": "2026-10-21",
 "judged_by": "Claude (agent) by reading the printed citations and notes; no person checked these verdicts",
 "external_calls": 0, "paid_calls": 0,
 "scope": "platform_v2.db shown versions (654: the 600 + 54 of v2_55; the v2_55 documents add no cited-work members); "
          "339 of the 600 have any citation mention; 129 have back references",
 "B1_grouping": {
  "cards": d["n_cards"], "cards_by_members": d["by_members"], "cards_by_mentions_incl_backrefs": d["by_mentions_incl_backrefs"],
  "cards_by_citing_articles": d["by_citing_articles"],
  "over_merge_sample_seed_4811": b1["over"],
  "over_merge_note": "wrong = two or more different works on one card; serial = the citations name only a journal/newspaper/law-report series (different items)",
  "author_conflict_cards_found_by_detector": 21,
  "cross_article_census_all_113": cx,
  "cross_article_precision_by_bridge": {"all articles' members name an author": "50 right / 51",
                                         "joined through an article whose members name no author": "50 right, 5 wrong, 6 serial, 1 mixed / 62"},
  "under_merge_candidates": b1["under"]["n_candidates"], "under_merge_sample_seed_4812": b1["under"],
  "under_merge_estimated_true_pairs": round(b1["under"]["n_candidates"] * b1["under"]["tally"]["yes"] / 50),
  "under_merge_true_pairs_adding_cross_article_link_in_sample": "26 of 35 (16 would create a new cross-article work)",
  "cross_article": {"cards_cited_by_gt1_article": 113, "true_works_cited_by_gt1_article": cx["true_cross_article_works"],
                    "articles_sharing_a_true_work": 82, "of_articles_with_cards": 337,
                    "largest_connected_group_of_articles": 67,
                    "note": "the links come almost all from classical Arabic humanities sources (lexica, biographical dictionaries, grammar, hadith)"},
  "quran": {"mentions": 216, "articles": 32, "note": "kept as kind quran, not a cited-work card; by articles it is the most-cited work"},
  "top30_by_citing_articles": [dict(rank=i + 1, cited_work_id=c["cited_work_id"], title=c["title"], articles=c["n_pubs"],
                                    mentions_incl_backrefs=c["n_mentions"], what=KIND[i]) for i, c in enumerate(top)],
 },
 "B2_back_references": {
  "population_600": {"total": 1096, "resolved": 992, "part_of_citation": 25, "unresolved": 79,
                      "note": "link47's metrics (111/36/24 unresolved) include the 54 v2_55 documents: 96 of their back references, none resolved"},
  "sample_seed_4813": b2,
 },
}
json.dump(res, open(f"{OUT}/results.json", "w"), ensure_ascii=False, indent=1)
print("ok")
