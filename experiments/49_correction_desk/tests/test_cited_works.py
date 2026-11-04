"""Cited-work decisions (experiment 67): editions of one work, a card that is not a work (dropped, retitled, one
card per citation), a collective book and its chapters, a thesis and the article drawn from it, links to Mandumah
publications (the work itself, or the same text in another journal) and relations, applied by the release step with
its constraint checks, on a small reading built here with platform v2's own schema."""
from __future__ import annotations

import json
import sqlite3

import pytest

from conftest import add_actor
from desk import db, index_pages, ops, release
from desk.keys import defined_work_id, split_card_id
from desk.reading import Reading

LIB = "agent:librarian-works-test"
STEMS = ["A-001-001", "B-002-002", "C-003-003"]
# card -> (pub_type, title, [(mention n, stem index, printed, parsed)], edition)
CARDS = {
    "CLISAN0001": ("book", "لسان العرب", [(1, 0, "ابن منظور، لسان العرب", {})], None),
    "CLISAN0002": ("book", "اللسان", [(2, 1, "اللسان، مادة قرأ", {})], None),
    "CDSM500001": ("book", "DSM-5", [(3, 0, "APA (2013). DSM-5.", {}), (17, 1, "APA. DSM-5.", {})], ("2013", "APA")),
    "CDSM400001": ("book", "DSM-IV-TR", [(4, 2, "APA (2000). DSM-IV-TR.", {})], ("2000", "APA")),
    "CJOURNAL01": ("journal", "مجلة الطفولة العربية", [
        (5, 0, "الهذلي (2014). فاعلية الرسوم المتحركة. مجلة الطفولة العربية، 63.", {"source_title": "مجلة الطفولة العربية"}),
        (6, 1, "سالم (2016). اللعب والتعلم. مجلة الطفولة العربية، 70.", {"source_title": "مجلة الطفولة العربية"})], None),
    "CDROP00001": ("journal", "مجلة", [(7, 2, "مجلة", {})], None),
    "CRETITLE01": ("journal", "Personality and Individual Differences", [
        (8, 0, "Parker (2004). Emotional intelligence and academic success. Personality and Individual Differences.",
         {"source_title": "Personality and Individual Differences"})], None),
    "CMIX000001": ("book", "علم النفس التربوي", [(9, 0, "منصور، علم النفس التربوي", {}),
                                                 (10, 2, "نشواتي، علم النفس التربوي", {})], ("2005", "الرسالة")),
    "COTHER0001": ("book", "علم النفس التربوي", [(11, 1, "نشواتي (2005)، علم النفس التربوي", {})], None),
    "CCHAPTER01": ("book", "الثقافة العربية", [(12, 0, "عبد الدايم (2003). الثقافة العربية", {})], None),
    "CCHAPTER02": ("book", "الثقافة العربية", [(13, 1, "سليم (2003). الثقافة العربية", {})], None),
    "CTHESIS001": ("thesis", "فاعلية طرق تعليم طفل الروضة", [(14, 0, "البسيوني (2002) رسالة دكتوراه", {})], None),
    "CARTICLE01": ("journal", "فاعلية طرق تعليم طفل الروضة", [(15, 1, "البسيوني (2003) مجلة الطفولة", {})], None),
    "CSAMETEXT1": ("journal", "قائمة تقدير المهارات", [(16, 2, "عبد القوي (2016). قائمة تقدير المهارات", {})], None),
}
BOOK = dict(natural="الثقافة العربية|مركز دراسات الوحدة العربية|2003", title="الثقافة العربية: أسئلة التطور والمستقبل",
            publisher="مركز دراسات الوحدة العربية", year="2003")
RECORD = dict(c999="900", rec=9, title="فاعلية طرق تعليم طفل الروضة", type="بحوث ومقالات", year_int=2003,
              journal="مجلة الطفولة والتنمية", journal_code="0900", authors=[dict(seq=1, name="البسيوني، مها")])


def mid(n):
    for _, _, ms, _ in CARDS.values():
        for (k, si, _, _) in ms:
            if k == n:
                return f"{STEMS[si]}|p1|w{n}-{n + 1}|1"


def W(c):
    return f"work:{c}"


@pytest.fixture(scope="module")
def reading(test_dir):
    p = test_dir / "works_reading.db"
    src = sqlite3.connect(f"file:{db.reading_path()}?mode=ro", uri=True)
    con = sqlite3.connect(p)
    for (sql,) in src.execute("""SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'search_fts%'
                                 ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, rowid"""):
        con.execute(sql)
    src.close()
    x = con.execute
    x("INSERT INTO catalogue_exports (export_id, built) VALUES ('marc-test', '2026-10-19')")
    x("INSERT INTO journals (journal_id, code) VALUES ('J1', '1')")
    x("INSERT INTO role_codes (code) VALUES ('author')")
    for i, stem in enumerate(STEMS, 1):
        x("INSERT INTO publications (pub_id, status, journal_id, title_shown) VALUES (?, 'final', 'J1', ?)",
          (f"W{i}", f"article {i}"))
        x("INSERT INTO documents (stem, level, pub_id) VALUES (?, 'final', ?)", (stem, f"W{i}"))
        x("INSERT INTO versions (version_id, version_key, stem, run, content_in_db, is_current) VALUES (?,?,?,?,1,1)",
          (i, f"{stem}|r", stem, "r"))
    for pk, (cid, (typ, title, ms, ed)) in enumerate(CARDS.items(), 1):
        x("INSERT INTO cited_works (cited_work_pk, cited_work_id, pub_type, title, status) VALUES (?, ?, ?, ?, 'active')",
          (pk, cid, typ, title))
        epk = None
        if ed:
            epk = 1000 + pk
            x("INSERT INTO cited_work_editions (edition_pk, cited_work_pk, edition_key, year_printed, publisher, "
              "n_members) VALUES (?, ?, ?, ?, ?, 1)", (epk, pk, f"|{ed[0]}|{ed[1]}", ed[0], ed[1]))
        for n, si, printed, parsed in ms:
            x("INSERT INTO citation_mentions (mention_pk, mention_id, version_id, container_kind, kind, printed, "
              "parsed, reading_ord, seq_in_container) VALUES (?, ?, ?, 'ref-list', 'full', ?, ?, ?, 1)",
              (n, mid(n), si + 1, printed, json.dumps(parsed, ensure_ascii=False), n))
            x("INSERT INTO cited_work_members (full_mention_pk, cited_work_pk, method, asserted_by, edition_pk) "
              "VALUES (?, ?, 'link47', 'link47', ?)", (n, pk, epk if n != 17 else None))   # 17 names no edition
    # the machine linked «اللسان» to a review of it, and the same-text card to nothing
    x("INSERT INTO citation_links (link_pk, cited_work_pk, target_kind, target_pub_id, status, best, score, method, "
      "asserted_by) VALUES (1, 2, 'publication', 'W2', 'accepted', 1, 0.9, 'catalogue-fts+validate', 'link47')")
    con.commit()
    con.close()
    return p


def R_of(path):
    return Reading(sqlite3.connect(f"file:{path}?mode=ro", uri=True))


def test_decide_validates_and_owns(pg, reading):
    add_actor(pg, LIB)
    add_actor(pg, "person:other")
    R = R_of(reading)
    d = lambda op, keys, payload=None, actor=LIB: ops.decide(pg, actor, op, keys, payload or {}, state=R)  # noqa: E731
    with pytest.raises(ops.OpError, match="the two keys are the same"):
        d("edition_of", [W("CDSM500001"), W("CDSM500001")])
    with pytest.raises(ops.OpError, match="action must be one of"):
        d("not_a_work", [W("CDROP00001")], dict(action="burn"))
    with pytest.raises(ops.OpError, match="not a publication in the current state"):
        d("link_publication", [W("CARTICLE01"), "pub:W900"], {"as": "work"})
    with pytest.raises(ops.OpError, match="catalogue record of pub:W900"):
        d("link_publication", [W("CARTICLE01"), "pub:W900"], {"as": "work", "record": dict(c999="901", title="x")})
    with pytest.raises(ops.OpError, match="as must be one of"):
        d("link_publication", [W("CARTICLE01"), "pub:W3"], {"as": "maybe"})
    with pytest.raises(ops.OpError, match="relation must be one of"):
        d("relate_works", [W("CARTICLE01"), W("CTHESIS001")], dict(relation="cousin_of"))
    with pytest.raises(ops.OpError, match="minted from its natural key"):
        d("define_work", ["work:CXXXXXXXXX"], dict(BOOK))
    with pytest.raises(ops.OpError, match="should be a pub key"):
        d("relate_publication", [W("CLISAN0002"), W("CLISAN0001")], dict(relation="reviewed_in"))
    d("link_publication", [W("CARTICLE01"), "pub:W900"], {"as": "work", "record": RECORD})
    with pytest.raises(ops.NotOwner, match="leave a note"):        # someone else's link on the same card
        d("link_publication", [W("CARTICLE01"), "pub:W3"], {"as": "work"}, actor="person:other")
    with pytest.raises(ops.OpError, match="supersede it"):         # one link answer per card
        d("link_publication", [W("CARTICLE01"), "pub:W3"], {"as": "work"})
    pg.commit()


def test_release_applies_cited_works(pg, reading, test_dir):
    R = R_of(reading)
    d = lambda op, keys, payload=None, actor=LIB: ops.decide(pg, actor, op, keys, payload or {}, state=R)  # noqa: E731
    sp = d("split_work", [W("CMIX000001")], dict(groups=[dict(members=[mid(9)]), dict(members=[mid(10)])]))
    g1 = sp["payload"]["groups"][1]["card_id"]
    assert g1 == split_card_id(str(sp["decision_id"]), 1)
    # a same_work on the split-off group: its members are the group's, not the card's the state still shows
    sw = d("same_work", [W(g1), W("COTHER0001")])
    assert sw["evidence"]["members"][W(g1)] == [mid(10)]
    d("same_work", [W("CLISAN0001"), W("CLISAN0002")])
    d("edition_of", [W("CDSM500001"), W("CDSM400001")], dict(edition_b="DSM-IV-TR"))
    opc = d("not_a_work", [W("CJOURNAL01")], dict(action="one_per_citation",
                                                   titles={mid(5): "فاعلية الرسوم المتحركة", mid(6): "اللعب والتعلم"}))
    d("not_a_work", [W("CDROP00001")], dict(action="drop"))
    d("not_a_work", [W("CRETITLE01")], dict(action="retitle", titles={mid(8): "Emotional intelligence and academic "
                                                                                "success"}))
    book = defined_work_id(BOOK["natural"])
    d("define_work", [W(book)], dict(BOOK))
    for ch in ("CCHAPTER01", "CCHAPTER02"):
        d("set_work_type", [W(ch)], dict(type="chapter"))
        d("relate_works", [W(ch), W(book)], dict(relation="part_of"))
    d("relate_works", [W("CARTICLE01"), W("CTHESIS001")], dict(relation="derived_from"))
    d("link_publication", [W("CSAMETEXT1"), "pub:W3"], {"as": "same_text", "cited_as": "مجلة الفيوم 2016"})
    d("relate_publication", [W("CLISAN0002"), "pub:W2"], dict(relation="reviewed_in"))
    # a relation between two cards another decision made one work cannot hold: a conflict
    add_actor(pg, "person:late")
    late = d("relate_works", [W("CLISAN0001"), W("CLISAN0002")], dict(relation="related"), actor="person:late")
    pg.commit()
    rel = release.build_release(pg, reading, test_dir / "works_releases", keep=5)
    assert rel["n_orphaned"] == 0
    assert rel["n_conflict"] == 1, pg.execute("SELECT detail FROM applications WHERE release_id = %s AND status = "
                                              "'conflict'", (rel["release_id"],)).fetchall()
    assert rel["checks"]["decisions_hold"] and rel["checks"]["fk_ok"]
    st = pg.execute("SELECT status, detail FROM applications WHERE release_id = %s AND decision_id = %s",
                    (rel["release_id"], late["decision_id"])).fetchone()
    assert st["status"] == "conflict" and "one card" in st["detail"]["why"]

    S = R_of(rel["path"])
    card = S.card_of_mention
    assert card(mid(1)) == card(mid(2)) == "CLISAN0001"
    assert card(mid(10)) == card(mid(11)) != card(mid(9))
    # editions of one work, each kept
    assert card(mid(3)) == card(mid(4)) == "CDSM500001"
    eds = {r[0]: r[1] for r in S.q("SELECT c.mention_id, e.edition_printed FROM cited_work_members cm JOIN "
                                     "citation_mentions c ON c.mention_pk = cm.full_mention_pk JOIN cited_work_editions e"
                                     " ON e.edition_pk = cm.edition_pk WHERE c.mention_pk IN (3, 4, 17)")}
    assert eds[mid(4)] == "DSM-IV-TR" and eds[mid(3)] is None and mid(17) not in eds   # 17 still names none
    # every edition a work shows is named by its citations; a citation that moved took its edition along
    assert not S.q("SELECT 1 FROM cited_work_editions e JOIN cited_works w USING (cited_work_pk) WHERE w.status = "
                   "'active' AND n_members <> (SELECT count(*) FROM cited_work_members m WHERE m.edition_pk = "
                   "e.edition_pk)")
    assert S.q1("SELECT w.cited_work_id FROM cited_work_members m JOIN cited_work_editions e ON e.edition_pk = "
                "m.edition_pk JOIN cited_works w ON w.cited_work_pk = e.cited_work_pk WHERE m.full_mention_pk = 10")[0] \
        == card(mid(10))
    # not a work
    assert card(mid(7)) is None and S.card("CDROP00001")["status"] == "not-a-work"
    assert S.card("CRETITLE01")["title"] == "Emotional intelligence and academic success"
    c5, c6 = card(mid(5)), card(mid(6))
    assert c5 != c6 and {c5, c6} == {"CJOURNAL01", opc["payload"]["groups"][1]["card_id"]}
    assert {S.card(c)["title"] for c in (c5, c6)} == {"فاعلية الرسوم المتحركة", "اللعب والتعلم"}
    # the collective book holds its two chapters; a thesis and its article are two works, related
    rels = {(a, r, b) for a, r, b in S.q("""SELECT s.cited_work_id, r.relation, o.cited_work_id FROM work_relations r
               JOIN cited_works s ON s.cited_work_pk = r.subject_cited_work_pk
               JOIN cited_works o ON o.cited_work_pk = r.object_cited_work_pk""")}
    assert {("CCHAPTER01", "is_part_of", book), ("CCHAPTER02", "is_part_of", book),
            ("CARTICLE01", "is_derived_from", "CTHESIS001")} <= rels
    assert S.card(book)["title"] == BOOK["title"] and S.card("CCHAPTER01")["pub_type"] == "chapter"
    # links: a new catalogued-only publication; the same text marked; the machine's review link rejected
    assert S.best_link("CARTICLE01")["target_pub_id"] == "W900"
    assert S.pub("W900")["status"] == "catalogued-only" and S.pub("W900")["journal_id"] == "J0900"
    st = S.best_link("CSAMETEXT1")
    assert st["target_pub_id"] == "W3" and json.loads(st["evidence"])["link_as"] == "same_text"
    assert S.best_link("CLISAN0001") is None
    assert S.q1("SELECT status FROM citation_links WHERE link_pk = 1")[0] == "rejected"
    after = rel["counts_after"]
    assert after["citation_links_person"] == 3 and after["cited_works_not_a_work"] == 1   # 2 links, 1 rejected
    # the index reads it: the dropped citation counts for no work, two references land in Mandumah
    ov = {n["key"]: n for n in index_pages.overview(rel["path"])["numbers"]}
    assert ov["cited_works"]["value"] == 12
    assert "2 references" in ov["held"]["sub"]

    # a second build reproduces the first exactly
    rel2 = release.build_release(pg, reading, test_dir / "works_releases", keep=5)
    assert rel2["fingerprint"] == rel["fingerprint"]

    # undo: the owner reverts the relation; the machine's link comes back
    ops.revert(pg, LIB, pg.execute("SELECT decision_id FROM decisions WHERE op = 'relate_publication'").fetchone()[
        "decision_id"])
    pg.commit()
    rel3 = release.build_release(pg, reading, test_dir / "works_releases", keep=5)
    S3 = R_of(rel3["path"])
    assert S3.best_link("CLISAN0001")["target_pub_id"] == "W2"
