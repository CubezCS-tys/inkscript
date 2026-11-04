"""Experiment 60, test 1: the proof pack's 30 metadata articles, fields right / loose / wrong (no calls).
Argon = the proof's verdicts after fix round 3 (experiment 43 README: fully right 18 -> 25); Claude = Argon's where
the two masters' fields are equal (meta60.py), else the hand verdicts below (looked at on page 1's scan where the
text alone does not settle it: out/t1/meta_look/).      -> out/t1/meta_scores.json"""
import json
from collections import Counter
from common60 import E43, OUT, jdump
items = {x["stem"]: x for x in json.loads((E43 / "out/proof/meta_score.json").read_text())["items"]}
FIX3 = {"0071-020-144-001": {"authors": "right"}, "0266-001-001,002-002": {"year": "right"},
        "0596-037-437-020": {"year": "right"}, "0806-003-004-010": {"authors": "right"},
        "1036-000-182-010": {"authors": "right"}, "1633-000-006-019": {"authors": "right"},
        "2483-000-019-001": {"authors": "right"}, "8480-000-000-002": {"authors": "right"}}
# Claude, per field that differs from Argon's master (the other fields take Argon's verdict)
HAND = {
 "0266-001-001,002-002": ({"year": "right", "affiliation": "right"}, "1989 right (the Hijri 1409 not kept beside it); affiliation differs by a space"),
 "0330-002-004-002": ({"title": "right"}, "فى for في: orthographic"),
 "0331-000-076-003": ({"title": "right"}, "the kicker «جدول أعمال :» left out of the title (the scan prints it as a label above); Argon's includes it"),
 "0367-000-006-017": ({"title": "loose"}, "book review: the reviewed book's title L'ORIENTALISME with «(Paris, Seuil, 1980).» as subtitle (Argon loose too)"),
 "0486-000-007-005": ({"affiliation": "loose"}, "«Universite» for Université (Azure's reading kept)"),
 "0596-037-437-020": ({"title": "loose"}, "«الشيخ» of the display title dropped"),
 "0597-012-011-002": ({"title": "wrong"}, "the stylised title read as «الفتنة يا ◌ً الليجا الجد»; subtitle garbled"),
 "0706-000-011-021": ({"title": "loose"}, "«النمن» for النص and a stray «*»"),
 "0728-022-003-013": ({"title": "loose"}, "the first poem's title «سكرة» instead of the series title «سداسيات»"),
 "0735-003-005,006-027": ({"title": "right"}, "the book's «تأليف …» line not taken as subtitle (better)"),
 "0744-000-063-045": ({"authors": "loose"}, "readers' mail: the initials «ع. م.» as author (Argon: initials + a letter writer)"),
 "0806-003-002-001": ({"title": "loose"}, "vowelled title: «بُرْيَطَنَانيا» for بُرْيطَانيَا"),
 "0806-003-004-010": ({"title": "wrong", "affiliation": "loose"}, "vowelled title garbled «ذكريَاِىّ وابِطَ عَالَّعَنْ .مِيْل»; the profession «المحامى» as affiliation"),
 "0924-009-007-003": ({"title": "wrong", "year": "unverified"}, "the title read as «ضَاءِكَةُ الأَعْنَ الَهْلِيَّةُ»; year 1928 (catalogue) not decidable from the scan"),
 "1036-000-182-010": ({"authors": "loose", "affiliation": "right"}, "the translator (ترجمة) not given: one contributor missing; affiliation the institution only (clean)"),
 "1289-000-001-006": ({"title": "wrong", "pages": "wrong"}, "title words in reverse order «الاحلام صدى»; no printed page read, so the catalogue's wrong 51-52 stands (print: 9)"),
 "1633-000-006-019": ({"authors": "wrong"}, "1 of the 8 rapporteurs, typed editor"),
 "1717-006-001-005": ({"affiliation": "right"}, "a trailing comma"),
 "2483-000-019-001": ({"title": "loose", "authors": "wrong", "affiliation": "loose"}, "«التقرير النهائي حول» dropped from the title; 2 of the 7 team members (5 missing) and their affiliations"),
 "8480-000-000-002": ({"title": "loose", "affiliation": "loose"}, "one title split into title + subtitle; the country dropped from the affiliation"),
}
meta = {r["stem"]: r for r in json.loads((OUT / "t1/meta.json").read_text())}
rows, pf_a, pf_c = [], Counter(), Counter()
for s, it in items.items():
    a = dict(it["verdicts"], **FIX3.get(s, {}))
    c = dict(a)
    why = "same fields as Argon's master"
    if not meta[s]["same"]:
        upd, why = HAND[s]
        c.update(upd)
    for k, v in a.items():
        pf_a[(k, v)] += 1
    for k, v in c.items():
        pf_c[(k, v)] += 1
    rows.append(dict(stem=s, argon=a, claude=c, argon_all=all(v == "right" for v in a.values() if v != "unverified") and "unverified" not in a.values(),
                     claude_all=all(v == "right" for v in c.values()), why=why))
tot = dict(argon_fully_right=sum(r["argon_all"] for r in rows), claude_fully_right=sum(r["claude_all"] for r in rows),
           argon_fields={f"{k}:{v}": n for (k, v), n in sorted(pf_a.items())},
           claude_fields={f"{k}:{v}": n for (k, v), n in sorted(pf_c.items())})
jdump(OUT / "t1/meta_scores.json", dict(totals=tot, articles=rows))
print(json.dumps(tot, ensure_ascii=False, indent=1))
