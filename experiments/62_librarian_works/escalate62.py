"""Experiment 62, step 5e: the few cases left for the owner — genuinely disputed, or a policy that moves many counts.
Each names the decision as it stands, the question in plain words, what each answer would change, and the
librarian's lean. Everything else is settled by the blind check, its adjudication and the hard checks.

    python3 escalate62.py   -> out/escalate62.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))

CASES = [
    dict(qkey="pair|C4EZV38PP2|CMGAH5Y38J", title="«صحيح مسلم بشرح النووي»: Muslim's book, or al-Nawawi's?",
         question="An article cites a hadith as «صحيح مسلم بشرح النووي 12/131». Is that a citation of Sahih Muslim (the "
                  "text quoted) or of al-Nawawi's commentary (the book on the shelf)?",
         if_yes="Count it as al-Nawawi's commentary, a work of its own: the librarian's decision stands (Sahih Muslim "
                "stays at its own count; al-Nawawi's commentary gains this citation).",
         if_no="Count it as Sahih Muslim: the commentary's printings join Sahih Muslim, and every «بشرح النووي» "
               "citation in the archive goes to Muslim.",
         lean="yes (the commentary): it is the book named, and joining both made one 'work' with two authors five "
              "centuries apart, which the authors check flagged.",
         why="policy for every commented classic (بشرح, مع شرح, حاشية): moves the counts of the most-cited hadith books"),
    dict(qkey="pair|CH8RVJCW1A|CP7MZCSEQN", title="The DSM: one work across its editions?",
         question="DSM-IV-TR (2000), DSM-5 (2013) and the French DSM-5 (2015) are joined as editions of one work (4 cards, "
                  "7 articles). Should a citation index count a manual's editions as one work?",
         if_yes="One work with editions (the librarian's call): the DSM is cited by 7 articles.",
         if_no="Each edition is its own work: DSM-5 and DSM-IV-TR are counted apart (fewer shared works).",
         lean="yes, with the edition kept on every citation (Web of Science counts editions apart; Google Scholar "
              "joins them): the platform can show both.",
         why="policy for every textbook with editions (Zahran, Armstrong, the DSM …): 86 edition_of decisions"),
    dict(qkey="pair|C2BE7XGM7E|C7TGVAC7QF", title="A chapter cited under its author's name: the book?",
         question="Two citations name different authors (عبد الدايم / سليم) but the same collective book «الثقافة العربية: "
                  "أسئلة التطور والمستقبل» (مركز دراسات الوحدة العربية 2003). Are they one cited work?",
         if_yes="One work, the collective book: both citations count for it.",
         if_no="Two works, the two chapters (each part_of the book): no shared work.",
         lean="yes, as the librarian has it: both print the same book, series no. 29 and the same section title "
              "(«مستقبل الثقافة العربية والتحديات التي تواجهها»), so the book is the publication cited; but if each name "
              "is a chapter's author, they are two chapters (each part_of the book). The blind check did not sample it.",
         why="policy for chapters in edited volumes: decides whether a chapter citation counts for the book"),
    dict(qkey="pair|C5QZVDD45J|CQCRSFF7DR", title="A thesis and the article drawn from it: one work?",
         question="The same title as a thesis (Ain Shams 2002) and as a journal article (2003) by the same author. The "
                  "librarian keeps them apart and links them as a relation.",
         if_yes="Two works, related (the librarian's rule): a citation of the thesis does not count as a citation of "
                "the article in Mandumah.",
         if_no="One work: thesis citations count for the article, and the held share rises.",
         lean="yes (two works, related): the blind check agreed on every such case it saw (B121, B137, B153).",
         why="policy: 12 such pairs here, and every thesis-to-article link in the catalogue (K3) depends on it"),
    dict(qkey="catalogue:CK75AY2BG4", title="The same text in two journals: not linked?",
         question="The citation gives the Fayoum kindergarten-college journal (2016, 2(2), 319-368); Mandumah holds an "
                  "article of the same title and first author in «مجلة بحوث ودراسات الطفولة» (2015). The librarian does "
                  "not link the citation to that record as the work, and shows it as related. Is that right?",
         if_yes="Not linked as the work, shown as related (the librarian's call); the same reading for the 11 other "
                "links taken back after the blind checks.",
         if_no="Linked: the same text in another venue counts as held by Mandumah; those 12 links come back and the "
               "held share rises a little.",
         lean="yes: link only the publication cited; show the other as related.",
         why="policy for republished articles and mis-cited venues: under the strict reading 12 links were taken back "
             "(11 to relation, 1 to unsure) after the blind checks (B122, B2005, B2033, B2035, B2044 and 7 found by "
             "re-reading)"),
]


def main():
    from finalize62 import standing
    S = {d["qkey"]: d for d in standing()}
    out = []
    for c in CASES:
        d = S[c["qkey"]]
        out.append(dict(c, decision_id=d["decision_id"], kind=d["kind"], confidence=d["confidence"], reason=d["reason"],
                        printed=d.get("printed"), subject_keys=d["subject_keys"]))
    (OUT / "escalate62.json").write_text(json.dumps(dict(cases=out), ensure_ascii=False, indent=1), encoding="utf-8")
    for x in out:
        print(x["decision_id"], x["kind"], x["title"])


if __name__ == "__main__":
    main()
