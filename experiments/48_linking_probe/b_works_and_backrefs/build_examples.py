"""examples.json: 19 real examples (good and bad) with the printed evidence. Card members: stem, mention_id
(stem|page|words|n), note/ref id, printed text. None of these cards has a catalogue link in platform_v2
(citation_links empty for them), so 'matched to' is the card or the in-article target citation."""
import json
from db import OUT
cards = {c["cited_work_id"]: c for c in json.load(open(f"{OUT}/cards_dump.json"))}
B2 = json.load(open(f"{OUT}/b2_judged.json"))["sample"]
def card(cid, verdict, kind, why, only=None):
    c = cards[cid]
    ms = [dict(stem=m["stem"], mention_id=m["mention_id"], page=m["page"], note_or_ref=m["container_id"], printed=m["printed"])
          for m in c["members"] if m["method"] == "in-article-first" and (only is None or m["stem"] in only)]
    return dict(direction="B1", kind=kind, verdict=verdict, matched_to=dict(cited_work_id=cid, title=c["title"],
                catalogue_link=None), n_articles=c["n_pubs"], why=why, members=ms)
def pair(a, b, why):
    return dict(direction="B1", kind="under-merge (one work on two cards)", verdict="should merge", why=why,
                cards=[card(a, "", "", "")["matched_to"] | dict(members=card(a, "", "", "")["members"][:3]),
                       card(b, "", "", "")["matched_to"] | dict(members=card(b, "", "", "")["members"][:3])])
def br(i, kind):
    s = B2[i]
    return dict(direction="B2", kind=kind, verdict=s["verdict"], why=s["why_judged"], category=s["category"],
                citation=dict(stem=s["stem"], mention_id=s["mention_id"], note=s["note"], marker=s["marker"], note_text=s["note_text"]),
                matched_to=(dict(note_or_ref=s["target"]["container_id"], mention_id=s["target"]["mention_id"],
                                 printed=s["target"]["printed"]) if s["target"] else None),
                notes_before=s["before"][-3:])
ex = [
 card("C7H83S6DX4", "right", "good grouping", "Lisan al-'Arab in 14 articles, eight printings and bare short forms; one work"),
 card("CC8ACBQFGF", "right", "good grouping, editions", "al-Aghani: Bulaq, Dar al-Kutub, Sadir 2008 editions on one work card"),
 card("CK4KYP6BAX", "wrong", "over-merge via author-less bridge", "«الديوان» of six poets joined because two members print no poet"),
 card("C8BJW04HWY", "wrong", "over-merge, generic short title", "«اللسان» = Lisan al-'Arab in 0692 but Ibn Hajar's Lisan al-Mizan in 1453"),
 card("CT9GTP7QSE", "wrong", "over-merge, generic short title", "«المغني»: Mughni al-Labib (grammar) vs Ibn Qudama's al-Mughni (law)"),
 card("CF622F7PED", "mixed", "over-merge, one foreign member", "Ibn Khaldun's Muqaddima + «مقدمة رسائل للرفاعي» (0596), an editor's preface"),
 card("C577XTTEWM", "wrong", "in-article over-merge", "six Egyptology works sharing «Late Middle Kingdom» in their titles, one card"),
 card("CRE29QBA2C", "serial", "serial, not a work", "a law-report series: 13 different rulings on one card"),
 pair("CF622F7PED", "CVSFVRG2E8", "«المقدّمة» vs «مقدمة ابن خلدون»: the same book on two cards (7 + 6 articles)"),
 pair("CR2GJDHYEA", "CGMCEDJB04", "Irshad al-Arib is the other title of Yaqut's Mu'jam al-Udaba'"),
 pair("C0KZX7J6P2", "CKR41NW7D9", "Bates, The Eastern Libyans 1914 and its 1970 reprint («Libyan»): one work"),
 br(20, "back reference resolved right (was 'missed' in the proof pack)"),
 br(35, "back reference resolved right by page continuity among three books by the author"),
 br(13, "back reference right at work level, but the sigle «S.R.C.» is not tied to its full citation"),
 br(44, "back reference wrong: a book titled 'Sartre' taken for Sartre the author"),
 br(40, "back reference wrong: op. cit. inside a full citation refers to its container"),
 br(51, "back reference missed: Arabic spelling of a Latin-script author"),
 br(58, "back reference missed: «Id» not recognised as a marker, chain broken"),
 br(50, "back reference missed: one earlier work by the author, found by the whole name"),
]
json.dump(ex, open(f"{OUT}/examples.json", "w"), ensure_ascii=False, indent=1)
print(len(ex))
