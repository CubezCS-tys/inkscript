"""D3: one human-workload table merged from probes A, B and C (their measured per-600 counts), de-duplicated,
ordered by impact on the metrics.  -> out/d_metrics_and_workload/d3_workload.json"""
import common_d as cd

N600, DOCS, TEAM, HOURS_DAY = 600, 1_000_000, 300, 5
scale = DOCS / N600

# count = decisions measured on the 600 (all 600 articles as the denominator, not only the 339 that cite).
# per_string: decided once per distinct string / entity, so it does not grow linearly with documents.
rows = [
    dict(rank=1, decision="Split or confirm a cross-article work joined through a citation with no author "
                          "(«الديوان», «اللسان», «المغني»; serial-only cards)",
         probe="B", count_600=62, minutes=1.0,
         why_minutes="2-3 member crops per article side by side; B judged 113 such cards in about 1 min each",
         metrics="times cited, top-cited list, coupling / co-citation networks, h-index of classical authors",
         after_rules="~15 (no join through an author-less member unless the title is >=3 words or on a classical-works list; serials typed automatically)",
         scales="linear (one per cross-article card at risk)"),
    dict(rank=2, decision="Is this authority one person? (records grouped by journal and decade, life dates)",
         probe="C", count_600=None, per_person=True, minutes=2.0,
         why_minutes="C read each authority profile in 1-2 min",
         metrics="h-index, person pages, self-citation, co-authorship",
         fixed_total_1M=515_000, prioritised_total_1M=60_000,
         prioritised_note="first the authorities that receive citations or sign articles, and those flagged by "
                          "'records after the life date' / 'journal cluster in another field': a guess of ~60k",
         scales="per authority, not per article: bounded by the catalogue (515k ids with 3+ records)"),
    dict(rank=3, decision="Catalogue link candidate: is the cited item this Mandumah record? "
                          "(same title + author, other journal or form; link47-only links)",
         probe="A", count_600=88, minutes=1.0,
         why_minutes="A: citation crop + record (journal, year, volume, pages) + authority; ~1 min",
         metrics="times cited of held articles, journal-level counts, h-index (the only route that reaches a person's own records)",
         after_rules="~60 (tolerate one misread letter in the author, 2-word titles with author + year)",
         scales="linear"),
    dict(rank=4, decision="Byline person with no authority, or a catalogue-only contributor that may be the same "
                          "person (double counting in 11 of 600 articles)",
         probe="C", count_600=97, minutes=1.5,
         why_minutes="C: byline crop, record contributors, loose candidates with their works; 1-2 min",
         metrics="h-index, co-authorship, person counts (double counting is a precision error)",
         after_rules="~50 (pair provisional bylines with catalogue-only contributors by transliteration, initials, role)",
         scales="linear"),
    dict(rank=5, decision="Merge two cards that may be one work (short vs full title, alternate classical title, reprint)",
         probe="B", count_600=154, minutes=0.67,
         why_minutes="B: two cards side by side with 2-3 crops each; 40 s",
         metrics="times cited (a split undercounts: the Muqaddima is on two cards, 7 + 6 articles), coupling",
         after_rules="~90 (auto-merge prefix + same uncommon first author; classical-works list)",
         scales="super-linear: more cards to collide with (B: 0.4M-2M at 1M)"),
    dict(rank=6, decision="Journal name candidate or generic name («مجلة كلية التربية», a Latin title equal to an Arab journal's English title)",
         probe="A", count_600=36, minutes=1.0, per_string=True,
         why_minutes="A: the citation + the candidate journals with their universities and years",
         metrics="journal-level citations, impact factor numerator",
         after_rules="most generic names need the university parsed from the citation first",
         scales="per distinct string: saturates (A: 1,142 entities from 1,696 citations, most cited once)"),
    dict(rank=7, decision="Affiliation wrong or partial (generic «المعهد», orphan faculty, lost university)",
         probe="C", count_600=82, minutes=1.5, per_string=True,
         why_minutes="C: affiliation crop + proposed tree + candidates in each script",
         metrics="institution-level counts only (none of the citation metrics)",
         after_rules="~40 (no entity for generic names; no shared org:? faculty)",
         scales="mostly per distinct string; C: 1,900-20,000 organisations at 1M"),
    dict(rank=8, decision="Back reference unresolved or resolved with low score (ibid / op. cit. → which earlier citation)",
         probe="B", count_600=189, minutes=0.33,
         why_minutes="B: marker crop + 3-5 previous notes + up to 3 candidates; one key; 20 s",
         metrics="mention counts only: an article's first full citation already counts it as citing, so times "
                 "cited by articles hardly moves",
         after_rules="~140 (Id, hint cut, whole name, corporate page continuity, sigles)",
         scales="linear, concentrated in the ~20% of articles that use back references"),
    dict(rank=9, decision="Self-citation that is a provenance note on page 1 ('this paper is from my PhD') or a wrong author",
         probe="C", count_600=5, minutes=0.5,
         why_minutes="one note crop",
         metrics="self-citation counts",
         after_rules="~1 (rule: a page-1 note naming the article's own source is not a citation)",
         scales="linear"),
]
# de-duplication notes
overlap = [
    "B's 'about 220 grouping decisions' = 154 merge pairs + 62 author-less joins + 21 author-conflict cards, "
    "overlapping; the 21 conflict cards are almost all among the 62, so they are not counted again.",
    "A's 56 candidates + 32 link47-only links are catalogue decisions; they touch no B card decision (a card is "
    "linked after it is grouped), so they are additive.",
    "C's cited-author decisions (167 with 2+ holders, 770 with one) are left unlinked by design: the safe route is "
    "citation -> catalogue record -> authority, which A's row 3 already covers. Counted zero here.",
    "C's per-article byline decisions (0.30) include affiliations (0.137); rows 4 and 7 split them.",
    "A's journal decisions are per string; B's serial cards (rows 1) feed A's journal table automatically once typed.",
]
total_now = total_after = 0.0
out_rows = []
for r in rows:
    if r.get("per_person"):
        dec = r["fixed_total_1M"]
        dec_p = r["prioritised_total_1M"]
        hours = dec * r["minutes"] / 60
        hours_p = dec_p * r["minutes"] / 60
        r.update(per_article=None, decisions_1M=dec, hours_1M=round(hours), hours_per_corrector=round(hours / TEAM, 1),
                 decisions_1M_prioritised=dec_p, hours_1M_prioritised=round(hours_p),
                 hours_per_corrector_prioritised=round(hours_p / TEAM, 1))
        total_now += hours_p
    else:
        per = r["count_600"] / N600
        dec = per * DOCS
        if r.get("per_string"):
            dec = dec * 0.3  # most strings recur: assume 30% are new at scale (A: 1,142 entities / 1,696 cites at 600; far fewer new at 1M)
            r["per_string_note"] = "decided once per distinct string; assumed 30% of per-article occurrences are new strings at scale"
        hours = dec * r["minutes"] / 60
        r.update(per_article=round(per, 3), decisions_1M=round(dec), hours_1M=round(hours),
                 hours_per_corrector=round(hours / TEAM, 1))
        total_now += hours
    out_rows.append(r)
audit = dict(decision="Audit: a 1% random check of automatic links (B's figure)", hours_1M=580,
             hours_per_corrector=round(580 / TEAM, 1))
total_now += 580
R = dict(
    team=TEAM, docs=DOCS, productive_hours_per_day=HOURS_DAY,
    rows=out_rows, audit=audit, overlap_and_double_counting=overlap,
    total_hours_1M=round(total_now), hours_per_corrector=round(total_now / TEAM, 1),
    working_days_team=round(total_now / (TEAM * HOURS_DAY), 1),
    total_without_authority_review=round(total_now - out_rows[1]["hours_1M_prioritised"]),
    caveats=[
        "Counts are measured on 600 articles; minutes are the probes' own reading times by an agent, not a person's.",
        "The merge row grows faster than the corpus (B); at its high end (2M decisions) it alone is ~22,000 h.",
        "Per-string rows use an assumed 30% novelty; per-person authority review uses C's 515k ids (full) or a guessed "
        "60k prioritised.",
    ],
    safe_to_leave_unlinked=[
        "Cited works with no held record and no DOI (~86% of citations): give them a card, never a guessed catalogue link.",
        "Cited authors with no linked record (C: ~1.6 per article); with 2+ holders never guess.",
        "Generic short titles across articles (B): keep per-article cards until an author or the classical-works list joins them.",
        "Unresolved back references with no earlier full citation: they change mentions, not citing-article counts.",
        "Latin-script books against Crossref (A: 1 of 8 right): leave them.",
        "Place-only / position-only affiliations, orphan faculties, generic names (C): keep the printed text, link nothing.",
        "Journal-issue citations with no item title (serials): attach to the journal for journal counts only, never a work card.",
    ])
cd.save("d3_workload.json", R)
for r in out_rows:
    print(r["rank"], r["probe"], r.get("per_article"), r["decisions_1M"], r["hours_1M"], r["hours_per_corrector"])
print(R["total_hours_1M"], R["hours_per_corrector"], R["working_days_team"])
