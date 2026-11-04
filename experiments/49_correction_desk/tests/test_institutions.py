"""Institution decisions (experiment 64): a body's record, merges, splits, a row that names no body, country, parent,
which bodies a printed affiliation names (current, former, educated at; inferred), and their application by the
release step with its constraint checks, on a small reading built here with platform v2's own schema."""
from __future__ import annotations

import sqlite3

import pytest

from conftest import add_actor
from desk import db, index_pages, ops, release
from desk.keys import authority_inst_id, split_inst_id
from desk.reading import Reading

LIB = "agent:librarian-test"
CAIRO, CAIRO_EN, FAC, MOE, NONAME, CENTRE = "IC0000CAIR", "IC0000CAEN", "IF0000FACU", "IM0000MOED", "IN0000NONE", \
    "IZ0000CENT"
SANAA, KW, BH = authority_inst_id("L-ye-sanaa"), authority_inst_id("L-kw-moe"), authority_inst_id("L-bh-moe")
AFF = {  # key -> (stem, byline_pos, script, printed, machine links)
    "a1": ("A-001-001", 0, "Arab", "كلية الآداب جامعة القاهرة", [(CAIRO, "org"), (FAC, "faculty")]),
    "a2": ("B-002-002", 0, "Latn", "Faculty of Arts, Cairo University", [(CAIRO_EN, "org")]),
    "a3": ("C-003-003", 0, "Arab", "كلية الآداب", [(FAC, "faculty")]),
    "a4": ("A-001-001", 1, "Arab", "وزارة التربية الكويت", [(MOE, "org")]),
    "a5": ("B-002-002", 1, "Arab", "وزارة التربية البحرين", [(MOE, "org")]),
    "a6": ("C-003-003", 1, "Arab", "بالكلية", [(NONAME, "org")]),
    "a7": ("A-001-001", 2, "Arab", "نائب رئيس جامعة القاهرة سابقا", [(CAIRO, "org")]),
    "a8": ("B-002-002", 2, "Arab", "مركز الدراسات، جامعتى القاهرة وصنعاء", [(CENTRE, "org")]),
}


def key(a):
    s, b, scr, _, _ = AFF[a]
    return f"aff:{s}|b{b}|{scr}|a1"


@pytest.fixture(scope="module")
def reading(test_dir):
    """An empty platform v2 (its schema copied from the real reading, read-only) with three articles, eight printed
    affiliations and six machine rows that show the machine's known faults."""
    p = test_dir / "inst_reading.db"
    src = sqlite3.connect(f"file:{db.reading_path()}?mode=ro", uri=True)
    con = sqlite3.connect(p)
    for (sql,) in src.execute("""SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'search_fts%'
                                 ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, rowid"""):
        con.execute(sql)
    src.close()
    x = con.execute
    for i, stem in enumerate(["A-001-001", "B-002-002", "C-003-003"], 1):
        x("INSERT INTO publications (pub_id, status, journal_id) VALUES (?, 'shown', 'J1')", (f"W{i}",))
        x("INSERT INTO documents (stem, level, pub_id) VALUES (?, 'final', ?)", (stem, f"W{i}"))
        x("INSERT INTO versions (version_id, version_key, stem, run, content_in_db, is_current) VALUES (?,?,?,?,1,1)",
          (i, f"{stem}|r", stem, "r"))
    for kind_, iid, name, country in [("university", CAIRO, "جامعة القاهرة", "EG"),
                                      ("university", CAIRO_EN, "Cairo University", None),
                                      ("faculty", FAC, "كلية الآداب", None), ("ministry", MOE, "وزارة التربية", None),
                                      ("organisation", NONAME, "بالكلية", None), ("centre", CENTRE, "مركز الدراسات", None)]:
        x("INSERT INTO institutions (inst_id, kind, country_code, status, source) VALUES (?, ?, ?, 'active', 'masters')",
          (iid, kind_, country))
        x("INSERT INTO institution_names (inst_id, name, script, type, n_seen, source) VALUES (?, ?, ?, 'printed', 3, "
          "'masters')", (iid, name, "Latn" if name.isascii() else "Arab"))
    for n, (a, (stem, b, scr, printed, links)) in enumerate(AFF.items(), 1):
        vid = {"A": 1, "B": 2, "C": 3}[stem[0]]
        x("INSERT INTO byline_mentions (mention_pk, version_id, byline_pos, script, printed) VALUES (?, ?, ?, ?, ?)",
          (n, vid, b, scr, printed))
        x("INSERT INTO affiliation_mentions (aff_pk, mention_pk, seq, printed) VALUES (?, ?, 1, ?)", (100 + n, n, printed))
        for iid, lvl in links:
            x("INSERT INTO affiliation_links (aff_pk, inst_id, level, method, asserted_by) VALUES (?, ?, ?, 'inst46', "
              "'link47')", (100 + n, iid, lvl))
    con.commit()
    con.close()
    return p


def R_of(path):
    return Reading(sqlite3.connect(f"file:{path}?mode=ro", uri=True))


def names(ar, en=None):
    out = [dict(name=ar, lang="ar", script="Arab", type="label")]
    if en:
        out.append(dict(name=en, lang="en", script="Latn", type="label"))
    return out


def link(*bodies):
    return dict(institutions=[dict(inst=f"inst:{i}", role=r, country=c) for i, r, c in bodies])


def test_decide_validates_and_owns(pg, reading):
    add_actor(pg, LIB)
    add_actor(pg, "person:other")
    R = R_of(reading)
    d = lambda op, keys, payload=None, actor=LIB: ops.decide(pg, actor, op, keys, payload or {}, state=R)  # noqa: E731
    with pytest.raises(ops.OpError, match="minted from its authority id"):
        d("define_institution", ["inst:IXXXXXXXXX"], dict(authority="L-ye-sanaa", kind="university",
                                                          names=names("جامعة صنعاء")))
    with pytest.raises(ops.OpError, match="kind must be one of"):
        d("define_institution", [f"inst:{SANAA}"], dict(authority="L-ye-sanaa", kind="castle", names=names("x")))
    with pytest.raises(ops.OpError, match="no such institution"):
        d("set_inst_country", [f"inst:{SANAA}"], dict(country="YE"))       # not defined yet
    d("define_institution", [f"inst:{CAIRO}"], dict(authority="L-eg-cairo", kind="university",
                                                    names=names("جامعة القاهرة", "Cairo University")))
    for iid, L, ar, en in [(SANAA, "L-ye-sanaa", "جامعة صنعاء", "Sana'a University"),
                           (KW, "L-kw-moe", "وزارة التربية (الكويت)", "Ministry of Education (Kuwait)"),
                           (BH, "L-bh-moe", "وزارة التربية والتعليم (البحرين)", "Ministry of Education (Bahrain)")]:
        x = d("define_institution", [f"inst:{iid}"], dict(authority=L, kind="university" if "صنعاء" in ar else
                                                          "ministry", names=names(ar, en)))
        assert x["payload"]["new"] is True and x["status"] == "accepted"
    with pytest.raises(ops.OpError, match="two-letter ISO"):
        d("set_inst_country", [f"inst:{SANAA}"], dict(country="Yemen"))
    with pytest.raises(ops.OpError, match="role must be one of"):
        d("link_affiliation", [key("a1"), f"inst:{CAIRO}"], dict(institutions=[dict(inst=f"inst:{CAIRO}",
                                                                                    role="alumnus")]))
    with pytest.raises(ops.OpError, match="order of subject_keys"):
        d("link_affiliation", [key("a1"), f"inst:{CAIRO}"], dict(institutions=[dict(inst=f"inst:{SANAA}")]))
    with pytest.raises(ops.OpError, match="no such printed affiliation"):
        d("not_an_institution", ["aff:Z-999-999|b0|Arab|a1"])
    d("link_affiliation", [key("a1"), f"inst:{CAIRO}"], link((CAIRO, "current", "EG")))
    # someone else's decision on the same affiliation is refused: they leave a note instead
    with pytest.raises(ops.NotOwner, match="leave a note"):
        d("not_an_institution", [key("a1")], actor="person:other")
    # and a second answer of the owner's must supersede the first
    with pytest.raises(ops.OpError, match="supersede it"):
        d("not_an_institution", [key("a1")])
    pg.commit()


def test_release_applies_institutions(pg, reading, test_dir):
    R = R_of(reading)
    d = lambda op, keys, payload=None, actor=LIB: ops.decide(pg, actor, op, keys, payload or {}, state=R)  # noqa: E731
    d("same_institution", [f"inst:{CAIRO}", f"inst:{CAIRO_EN}"])
    d("not_an_institution_row", [f"inst:{NONAME}"])
    for iid, c in [(CAIRO, "EG"), (SANAA, "YE"), (KW, "KW"), (BH, "BH")]:
        d("set_inst_country", [f"inst:{iid}"], dict(country=c))
    d("set_inst_parent", [f"inst:{CENTRE}", f"inst:{CAIRO}"])
    d("link_affiliation", [key("a2"), f"inst:{CAIRO_EN}"], link((CAIRO_EN, "current", "EG")))   # a merged id
    d("link_affiliation", [key("a3"), f"inst:{SANAA}"], link((SANAA, "current", "YE")))
    d("link_affiliation", [key("a4"), f"inst:{KW}"], link((KW, "current", "KW")))
    d("link_affiliation", [key("a5"), f"inst:{BH}"], link((BH, "current", "BH")))
    d("not_an_institution", [key("a6")])
    d("link_affiliation", [key("a7"), f"inst:{CAIRO}"], link((CAIRO, "former", "EG")))
    d("link_affiliation", [key("a8"), f"inst:{CAIRO}", f"inst:{SANAA}"],
      dict(institutions=[dict(inst=f"inst:{CAIRO}", role="current", country="EG",
                              inferred={"from": "journal", "why": "test"}),
                         dict(inst=f"inst:{SANAA}", role="current", country="YE")]))
    fac = d("not_same_institution", [f"inst:{FAC}"], dict(lumped_faculty=True, groups=[
        dict(body=f"inst:{CAIRO}", affiliations=[key("a1")]), dict(body=f"inst:{SANAA}", affiliations=[key("a3")])]))
    d("not_same_institution", [f"inst:{MOE}"], dict(groups=[dict(body=f"inst:{KW}", affiliations=[key("a4")]),
                                                           dict(body=f"inst:{BH}", affiliations=[key("a5")])]))
    # a later decision that cannot hold: a parent cycle (Cairo under its own centre)
    add_actor(pg, "person:cycle")
    cyc = d("set_inst_parent", [f"inst:{CAIRO}", f"inst:{CENTRE}"], actor="person:cycle")
    pg.commit()
    rel = release.build_release(pg, reading, test_dir / "inst_releases", keep=5)
    assert rel["n_orphaned"] == 0
    assert rel["n_conflict"] == 1                      # the cycle; everything else applied
    assert rel["checks"]["decisions_hold"] and rel["checks"]["fk_ok"]
    st = pg.execute("SELECT status, detail FROM applications WHERE release_id = %s AND decision_id = %s",
                    (rel["release_id"], cyc["decision_id"])).fetchone()
    assert st["status"] == "conflict" and "cycle" in st["detail"]["why"]

    S = R_of(rel["path"])
    aff = {a: S.aff(key(a)[4:])["aff_pk"] for a in AFF}
    links = lambda a: {(r["inst_id"], r["level"]) for r in S.aff_links(aff[a])}  # noqa: E731
    assert S.inst(CAIRO_EN)["status"] == "merged" and S.resolve_inst(CAIRO_EN)[0] == CAIRO
    assert S.inst(CAIRO)["parent_id"] is None
    assert links("a2") == {(CAIRO, "org")}
    assert links("a1") == {(CAIRO, "org"), (FAC, "faculty")} and S.inst(FAC)["parent_id"] == CAIRO
    new_fac = split_inst_id(str(fac["decision_id"]), 1)
    assert links("a3") == {(SANAA, "org"), (new_fac, "faculty")}
    assert S.inst(new_fac)["parent_id"] == SANAA and S.inst(new_fac)["country_code"] == "YE"
    assert links("a4") == {(KW, "org")} and links("a5") == {(BH, "org")}
    assert links("a6") == set() and S.inst(NONAME)["status"] == "not-an-institution"
    assert links("a7") == {(CAIRO, "former")}
    # two bodies, two countries; the centre the machine took for the institution stays as Cairo's unit
    assert links("a8") == {(CAIRO, "org"), (SANAA, "org"), (CENTRE, "dept")}
    assert {S.inst(i)["country_code"] for i in (CAIRO, SANAA)} == {"EG", "YE"}
    assert S.inst(SANAA)["source"].startswith("desk") and S.inst_name(SANAA) == "جامعة صنعاء"
    after = rel["counts_after"]
    assert after["institutions_linked_org"] == 4 and after["affiliation_links_former"] == 1
    assert after["institutions_merged"] == 1

    # the index counts current posts only, every body of a statement
    lst = {r["inst_id"]: r for r in index_pages.institutions(rel["path"])}
    assert set(lst) == {CAIRO, SANAA, KW, BH}
    assert lst[CAIRO]["articles"] == 2 and lst[SANAA]["articles"] == 2      # a7 (former) is not Cairo's output
    assert lst[CAIRO]["name"] == "جامعة القاهرة"
    page = index_pages.institution(rel["path"], CAIRO)
    assert page["counts"]["articles"] == 2

    # a second build reproduces the first exactly
    rel2 = release.build_release(pg, reading, test_dir / "inst_releases", keep=5)
    assert rel2["fingerprint"] == rel["fingerprint"]

    # undo: the owner reverts the former post; the machine's link comes back
    ops.revert(pg, LIB, pg.execute("SELECT decision_id FROM decisions WHERE op = 'link_affiliation' AND "
                                   "subject_keys[1] = %s", (key("a7"),)).fetchone()["decision_id"])
    pg.commit()
    rel3 = release.build_release(pg, reading, test_dir / "inst_releases", keep=5)
    S3 = R_of(rel3["path"])
    assert {(r["inst_id"], r["level"]) for r in S3.aff_links(aff["a7"])} == {(CAIRO, "org")}
