"""Experiment 47: the bibliographic and people layers — catalogue records (by 999$c), publications, every reading of
every metadata value (printed / D33-corrected / catalogue / Gemini front page), dates in both calendars, languages,
abstracts, keywords, subjects, journals / ISSNs / publishers / issues, external ids, byline mentions -> authorships ->
persons (authority ids first), affiliations -> institutions (experiment 46's inst46 reused), catalogue reports."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from common47 import (E46, OUT43, akey, calendar_of, country_iso, fill_pk, hashed_id, heading_display, heading_key, catalogue_holders, spk,
                      split_life, fold, greg_to_hijri, hijri_to_greg, insert, issn_clean, jdump, key,
                      latin_key, name_key, name_parts, now, ratio, script, split_titles, to_int, year_of)

sys.path.insert(0, str(E46))
import load46  # noqa: E402  (catalogue(), match_authors(), disagreements(), title_key())
import inst46  # noqa: E402
from parse46 import parse_article  # noqa: E402

EXPORT = "marc-2026-10-19"
TYPE = {"بحوث ومقالات": "article", "رسائل جامعية": "thesis", "بحوث المؤتمرات": "conference-paper",
        "عروض كتب": "book-review", "افتتاحيات": "editorial", "نصوص أدبية": "literary-text", "عروض رسائل": "thesis-review",
        "ببليوجرافية": "bibliography", "عروض ابحاث": "paper-review", "تشريعات": "legislation", "فتاوى": "fatwa",
        "اخرى": "other"}
ROLE = {"مؤلف": "author", "author": "author", "م. مشارك": "coauthor", "co-author": "coauthor", "co.author": "coauthor",
        "co - author": "coauthor", "co-auth": "coauthor", "مشرف": "supervisor", "advisor": "supervisor",
        "super": "supervisor", "supervisor": "supervisor", "عارض": "reviewer", "reviewer": "reviewer",
        "مترجم": "translator", "translator": "translator", "محقق": "editor-of-text", "محاور": "interviewer",
        "محرر": "editor", "editor": "editor", "معد": "compiler"}
COUNTRY = {"مصر": "EG", "الجزائر": "DZ", "العراق": "IQ", "السعودية": "SA", "المغرب": "MA", "سوريا": "SY",
           "الأردن": "JO", "الاردن": "JO", "لبنان": "LB", "الكويت": "KW", "الإمارات": "AE", "الامارات": "AE",
           "قطر": "QA", "البحرين": "BH", "عمان": "OM", "سلطنة عمان": "OM", "اليمن": "YE", "السودان": "SD",
           "ليبيا": "LY", "تونس": "TN", "فلسطين": "PS", "موريتانيا": "MR", "ماليزيا": "MY", "تركيا": "TR",
           "فرنسا": "FR", "المملكة المتحدة": "GB", "الولايات المتحدة": "US", "باكستان": "PK", "الهند": "IN",
           "إيران": "IR", "ايران": "IR", "نيجيريا": "NG", "إندونيسيا": "ID", "ألمانيا": "DE"}
LANG3 = {"ar": "ara", "en": "eng", "fr": "fre", "de": "ger", "es": "spa", "it": "ita", "fa": "per", "tr": "tur",
         "ara": "ara", "eng": "eng", "fre": "fre", "fra": "fre", "ger": "ger", "spa": "spa", "per": "per",
         "tur": "tur", "urd": "urd", "ita": "ita", "heb": "heb", "rus": "rus"}
FR_WORDS = set("le la les des du de et est une un dans pour par sur au aux qui que ne pas cette ces".split())
EN_WORDS = set("the of and in to is a for on that with as by this are from".split())


def lang_detect(t: str | None) -> tuple[str, str]:
    if not t:
        return "und", "none"
    if script(t) == "Arab":
        return "ara", "script"
    ws = re.findall(r"[a-zà-ÿ]+", t.lower())
    fr, en = sum(w in FR_WORDS for w in ws), sum(w in EN_WORDS for w in ws)
    return ("fre" if fr > en else "eng"), "script+stopwords"


# ------------------------------------------------------------------ registry of public ids
def public_id(con, kind: str, natural: str, load_id) -> str:
    """The public id of an entity, from its natural key: 'A'/'I'/'C' + a hash of the key (never a running count, so
    two clean builds in any order give the same ids). The registry keeps the first load that minted it."""
    r = con.execute("SELECT public_id FROM id_registry WHERE kind = ? AND natural_key = ?", (kind, natural)).fetchone()
    if r:
        return r[0]
    pre = {"person": "A", "institution": "I", "cited_work": "C"}[kind]
    n = 9
    pid = hashed_id(pre, kind, natural, n)
    while con.execute("SELECT 1 FROM id_registry WHERE public_id = ?", (pid,)).fetchone():
        n += 1                                         # a 45-bit collision: lengthen (never seen)
        pid = hashed_id(pre, kind, natural, n)
    con.execute("INSERT INTO id_registry VALUES (?,?,?,?)", (pid, kind, natural, load_id))
    return pid


# ------------------------------------------------------------------ catalogue
def put_record(con, mcon, rec: int) -> str | None:
    """marc.db record (by its row) -> catalogue_records (keyed by 999$c), its files, contributors and subjects."""
    r = mcon.execute("SELECT * FROM records WHERE rec = ?", (rec,)).fetchone()
    if not r or not r["c999"]:
        return None
    c = r["c999"]
    insert(con, "catalogue_records", [dict(
        c999=c, export_id=EXPORT, rec=r["rec"], record_id_001=r["record_id"], type=r["type"], title=r["title"],
        subtitle=r["subtitle"], title_en=r["title_en"], parallel_titles=r["parallel_titles"], language_raw=r["language"],
        year_raw=r["year"], year_int=r["year_int"], year_hijri=to_int(r["year_hijri"]) if r["year_hijri"] else None,
        month=r["month"], pages_raw=r["pages"], page_first=r["page_first"], page_last=r["page_last"],
        journal_code=r["journal_code"], journal_raw=r["journal"], issn_raw=r["issn"], volume_raw=r["volume"],
        issue_raw=r["issue"], issue_printed=r["issue_printed"], article_seq=to_int(r["article_seq"]), doi=r["doi"],
        databases=r["databases"], added=r["added"], thesis_json=r["thesis"], n_pdfs=r["n_pdfs"])])
    insert(con, "catalogue_record_documents", [dict(c999=c, stem=p["stem"], seq=p["seq"], label=p["label"])
                                               for p in mcon.execute("SELECT * FROM pdf_ids WHERE rec = ?", (rec,))])
    con.execute("DELETE FROM catalogue_contributors WHERE c999 = ?", (c,))
    rows = []
    for a in mcon.execute("SELECT * FROM authors WHERE rec = ? ORDER BY seq", (rec,)):
        rr = (a["role"] or "").strip()
        life = re.search(r"(?:ت\.|توفي|d\.)\s*[0-9٠-٩]{3,4}\s*(?:هـ|م)?", a["name"] or "")
        rows.append(dict(c999=c, seq=a["seq"], tag=a["tag"], name=a["name"], latin=a["latin"] or None, role_raw=rr or None,
                         role_code=ROLE.get(rr.lower(), "author" if not rr else ROLE.get(rr, "author")),
                         authority_id=a["authority_id"] or None, is_org=a["is_org"],
                         life_note=life.group(0) if life else None))
    insert(con, "catalogue_contributors", rows)
    con.execute("DELETE FROM record_subjects WHERE c999 = ?", (c,))
    subs = []
    for s in mcon.execute("SELECT * FROM subjects WHERE rec = ? ORDER BY seq", (rec,)):
        subs.append((s["source"], s["term"]))
    for f in (r["fields_of_study"] or "").split(" | "):
        if f.strip():
            subs.append(("field-of-study", f.strip()))
    for d in (r["databases"] or "").split(","):
        if d.strip():
            subs.append(("database", d.strip()))
    for k, (sch, term) in enumerate(subs):
        tk = key(term)
        if not tk:
            continue
        ar = term if script(term) == "Arab" else None
        insert(con, "subject_terms", [dict(scheme=sch, term_ar=ar, term_en=None if ar else term, term_key=tk)],
               "INSERT OR IGNORE")
        sid, have = con.execute("SELECT subject_id, coalesce(term_ar, term_en) FROM subject_terms WHERE scheme = ? AND "
                                "term_key = ?", (sch, tk)).fetchone()
        if have != term and _label_rank(term) < _label_rank(have):
            # fix round 2: the label is chosen by a rule (hamza written, then text order), never by which record
            # loaded first — «الإعاقة» over «الاعاقة» in every build
            con.execute(f"UPDATE subject_terms SET {'term_ar' if ar else 'term_en'} = ? WHERE subject_id = ?",
                        (term, sid))
        con.execute("INSERT OR IGNORE INTO record_subjects VALUES (?,?,?)", (c, sid, k))
    return c


def _label_rank(t):
    t = t or ""
    return (-sum(t.count(c) for c in "أإآؤئ"), t)


def stem_parts(stem: str):
    p = stem.split("-")
    return (p[0], p[1] if len(p) > 1 else None, p[2] if len(p) > 2 else None)


def ensure_journal_issue(con, mcon, code: str | None, vol: str | None, iss: str | None, rec_row=None):
    if not code:
        return None, None
    jid = f"J{code}"
    if not con.execute("SELECT 1 FROM journals WHERE journal_id = ?", (jid,)).fetchone():
        stats = mcon.execute("SELECT min(year_int), max(year_int), count(*) FROM records WHERE journal_code = ? AND "
                             "year_int > 0", (code,)).fetchone()
        tops = mcon.execute("SELECT journal, journal_en, journal_romanised, country, publisher, databases FROM records "
                            "WHERE journal_code = ? LIMIT 400", (code,)).fetchall()
        cc = Counter(COUNTRY.get((t["country"] or "").strip()) for t in tops if t["country"])
        dbs = sorted({d.strip() for t in tops for d in (t["databases"] or "").split(",") if d.strip()})
        con.execute("INSERT INTO journals VALUES (?,?,?,?,?,?)", (jid, code, (cc.most_common(1)[0][0] if cc else None),
                                                                  ",".join(dbs) or None, stats[0], stats[1]))
        for col, form in (("journal", "catalogue"), ("journal_en", "catalogue-en"), ("journal_romanised", "romanised")):
            c = Counter(t[col] for t in tops if t[col])
            for k, (title, n) in enumerate(c.most_common(5)):
                insert(con, "journal_titles", [dict(journal_id=jid, title=title, lang=None if form == "catalogue" and
                                                    script(title) == "Arab" else None, form=form, n=n,
                                                    source="catalogue", is_chosen=int(form == "catalogue" and k == 0))],
                       "INSERT OR IGNORE")
        for row in mcon.execute("SELECT issn, count(*) n FROM records WHERE journal_code = ? AND issn IS NOT NULL AND "
                                "issn <> '' GROUP BY issn", (code,)):
            iss_, ok = issn_clean(row["issn"])
            insert(con, "journal_issns", [dict(journal_id=jid, issn_raw=row["issn"], issn=iss_, valid_check=ok,
                                               kind="unknown", issn_l=None, n_records=row["n"], source="catalogue",
                                               note=None if ok else "check digit fails or not 8 characters")])
        pc = Counter(t["publisher"] for t in tops if t["publisher"])
        for name, n in pc.most_common(2):
            pid = "P" + hashlib.sha1(key(name).encode()).hexdigest()[:8]
            insert(con, "publishers", [dict(publisher_id=pid, name=name, name_en=None,
                                            country_code=cc.most_common(1)[0][0] if cc else None, inst_id=None)],
                   "INSERT OR IGNORE")
            insert(con, "journal_publishers", [dict(journal_id=jid, publisher_id=pid, from_year=None, to_year=None,
                                                    source=f"catalogue 260$b ({n} of the journal's first 400 records)")],
                   "INSERT OR IGNORE")
    iid = None
    if vol is not None and iss is not None:
        iid = f"{jid}/{vol}/{iss}"
        if not con.execute("SELECT 1 FROM issues WHERE issue_id = ?", (iid,)).fetchone():
            r = rec_row
            nums = [int(x) for x in re.findall(r"\d+", iss)]
            con.execute("INSERT INTO issues VALUES (?,?,?,?,?,?,?,?,?,?,?)", (
                iid, jid, (r["volume"] if r else None) or vol, to_int(vol) or None, (r["issue"] if r else None) or iss,
                r["issue_printed"] if r else None, 0, int("," in iss or len(nums) > 1),
                r["year_int"] if r else None, to_int(r["year_hijri"]) if r and r["year_hijri"] else None,
                r["month"] if r else None))
            insert(con, "issue_numbers", [dict(issue_id=iid, number=n) for n in nums], "INSERT OR IGNORE")
    return jid, iid


def ensure_catalogued_pub(con, mcon, c999: str, load_id=None) -> str | None:
    """A catalogue record we hold no scan of (a citation target) as a publication W<c999>, status catalogued-only."""
    pid = f"W{c999}"
    if con.execute("SELECT 1 FROM publications WHERE pub_id = ?", (pid,)).fetchone():
        return pid
    r = mcon.execute("SELECT * FROM records WHERE c999 = ? LIMIT 1", (c999,)).fetchone()
    if not r:
        return None
    put_record(con, mcon, r["rec"])
    st = mcon.execute("SELECT stem FROM pdf_ids WHERE rec = ? ORDER BY seq LIMIT 1", (r["rec"],)).fetchone()
    code, vol, iss = stem_parts(st["stem"]) if st else (r["journal_code"], None, None)
    jid, iid = ensure_journal_issue(con, mcon, r["journal_code"] or code, vol, iss, r)
    con.execute("INSERT INTO publications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, c999, jid, iid, to_int(r["article_seq"]), TYPE.get(r["type"], "other"), r["type"],
                 "catalogued-only", r["title"], r["year_int"], None))
    cat_assertions(con, pid, r, load_id)
    return pid


def cat_assertions(con, pid, r, load_id=None):
    con.execute("DELETE FROM metadata_assertions WHERE pub_id = ? AND form = 'catalogue'", (pid,))
    vals = [("title", r["title"], "ar" if script(r["title"]) == "Arab" else None), ("subtitle", r["subtitle"], None),
            ("title_translated", r["title_en"], "en"), ("fpage", r["page_first"], None),
            ("lpage", r["page_last"], None), ("volume", r["volume"], None), ("issue", r["issue"], None),
            ("year", r["year_int"], None), ("year_hijri", r["year_hijri"], None), ("doi", r["doi"], None),
            ("journal_title", r["journal"], None), ("language", r["language"], None)]
    rows = []
    for f, v, lang in vals:
        if v in (None, ""):
            continue
        rows.append(dict(pub_id=pid, field=f, value=str(v), value_norm=norm(f, v), lang=lang, script=script(str(v)),
                         form="catalogue", source="catalogue", export_id=EXPORT, confidence=None,
                         actor_id="catalogue:mandumah", is_chosen=0, created=now(), load_id=load_id))
    insert(con, "metadata_assertions", rows, "INSERT")


def norm(field, v):
    if v is None:
        return None
    s = str(v)
    if field in ("title", "subtitle", "journal_title"):
        return load46.title_key(s)
    if field == "title_translated":
        return latin_key(s)
    if field in ("fpage", "lpage", "volume", "issue", "year", "year_hijri"):
        n = to_int(s)
        return str(n) if n is not None else None
    if field == "doi":
        return s.lower().strip().replace("https://doi.org/", "")
    if field == "language":
        return ",".join(sorted({LANG3.get(x.strip().lower(), x.strip().lower()) for x in re.split(r"[,;]", s) if x.strip()}))
    return fold(s)


FIELD = {"translated title": "title_translated", "title_en": "title_translated", "trans-title": "title_translated",
         "first page": "fpage", "last page": "lpage", "pub_year": "year"}


def trans_title(jats: Path) -> str | None:
    """title-group/trans-title-group/trans-title (experiment 46 looked under article-meta and found none)."""
    from lxml import etree
    from parse46 import text_of
    try:
        r = etree.parse(str(jats)).getroot()
    except Exception:
        return None
    t = r.find(".//article-meta/title-group/trans-title-group/trans-title")
    return text_of(t) if t is not None else None


# ------------------------------------------------------------------ one document's publication layer
CHOOSE = {"person": 1, "judge": 2, "corrected": 3, "printed": 4, "catalogue": 5, "gemini-title": 6,
          "qdrant-payload": 7}


def refresh_stem(con, mcon, stem: str, load_id: int, S: Counter):
    vs = con.execute("SELECT v.*, r.kind FROM versions v JOIN runs r USING (run) WHERE stem = ? ORDER BY version_id",
                     (stem,)).fetchall()
    cur = next((v for v in vs if v["is_current"]), None)
    if not cur:
        return
    Rs = {}
    for v in vs:
        mdir = OUT43 / v["run"] / "masters"
        if (mdir / f"{stem}.jats.xml").exists():
            Rs[v["version_id"]] = parse_article(mdir, stem, v["run"])
    R = Rs[cur["version_id"]]
    art = R["article"]
    crow, cauth, ckw, csubj, cabs = load46.catalogue(mcon, stem, art)
    prim = next((c for c in crow if c["is_primary"]), None)
    for c in crow:
        put_record(con, mcon, c["rec"])
    code, vol, iss = stem_parts(stem)
    prow = mcon.execute("SELECT * FROM records WHERE rec = ?", (prim["rec"],)).fetchone() if prim else None
    jid, iid = ensure_journal_issue(con, mcon, code, vol, iss, prow)
    if prim and prim["c999"]:
        pid = f"W{prim['c999']}"
    else:
        pid = f"WS{stem}"
        S["uncatalogued"] += 1
    old = con.execute("SELECT pub_id FROM documents WHERE stem = ?", (stem,)).fetchone()
    if old and old[0] and old[0] != pid:
        con.execute("INSERT OR REPLACE INTO merged_ids VALUES (?,?, 'publication', 'merged-into', ?, ?, 'load47', NULL)",
                    (old[0], pid, now(), "the document's primary catalogue record changed"))
    level = con.execute("SELECT level FROM documents WHERE stem = ?", (stem,)).fetchone()[0]
    con.execute("""INSERT INTO publications VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(pub_id) DO UPDATE SET
                   journal_id = excluded.journal_id, issue_id = excluded.issue_id, status = excluded.status,
                   current_version = excluded.current_version, type = excluded.type, type_catalogue = excluded.type_catalogue""",
                (pid, prim["c999"] if prim else None, jid, iid, to_int(prow["article_seq"]) if prow else None,
                 TYPE.get(prow["type"], "other") if prow else "article", prow["type"] if prow else None, level, None,
                 None, cur["version_id"]))
    con.execute("UPDATE documents SET pub_id = ?, has_gemini_title = NULL WHERE stem = ?", (pid, stem))
    # other records naming this file: their own publications, and a report (one file, several records)
    for c in crow:
        if c is prim or not c["c999"]:
            continue
        ensure_catalogued_pub(con, mcon, c["c999"], load_id)
    # ---- metadata assertions: every version's print (and D33 corrections), the catalogue
    con.execute("DELETE FROM metadata_assertions WHERE pub_id = ? AND form IN ('printed', 'corrected', 'gemini-title')",
                (pid,))
    title_anchor = {}
    for vid, Rv in Rs.items():
        a = Rv["article"]
        t = con.execute("SELECT anchor_pk FROM blocks WHERE version_id = ? AND role = 'title' ORDER BY ord LIMIT 1",
                        (vid,)).fetchone()
        title_anchor[vid] = t[0] if t else None
        printed = dict(title=a["title_printed"] or a["title"], title_translated=a["title_en"], subtitle=a["subtitle"],
                       fpage=a["fpage"], lpage=a["lpage"], volume=a["volume"], issue=a["issue"], year=a["pub_year"],
                       doi=a["doi"], journal_title=Rv["journal_title"], language=a["language"])
        if not printed["title_translated"]:
            printed["title_translated"] = trans_title(OUT43 / con.execute(
                "SELECT masters_key FROM versions WHERE version_id = ?", (vid,)).fetchone()[0])
        ch = {FIELD.get(c["field"], c["field"]): c for c in Rv["metadata_changes"]}
        for f, c in ch.items():
            if f in printed and c["printed"] is not None:
                printed[f] = c["printed"]
        for f, v in printed.items():
            if v in (None, ""):
                continue
            lang = "ar" if f == "title" and script(str(v)) == "Arab" else ("en" if f == "title_translated" else None)
            pa = fill_pk("metadata_assertions", [dict(
                pub_id=pid, field=f, value=str(v), value_norm=norm(f, v), lang=lang, script=script(str(v)),
                form="printed", source="masters", version_id=vid, block_id=None,
                anchor_pk=title_anchor[vid] if f == "title" else None, actor_id="model:gemini-4-argon", is_chosen=0,
                created=now(), load_id=load_id)])[0]
            insert(con, "metadata_assertions", [pa], "INSERT")
            if f in ch and ch[f]["corrected"] is not None:
                c = ch[f]
                insert(con, "metadata_assertions", [dict(
                    pub_id=pid, field=f, value=str(c["corrected"]), value_norm=norm(f, c["corrected"]), lang=lang,
                    script=script(str(c["corrected"])), form="corrected", source="rule", version_id=vid,
                    rule=f"{c['rule']}: {c['change_source']}", reason=c["reason"], alternatives=c["alternatives"],
                    supersedes=pa["assert_pk"], actor_id="rule:d33", is_chosen=0, created=now(), load_id=load_id)],
                    "INSERT")
                S["d33"] += int(vid == cur["version_id"])
    if prow:
        cat_assertions(con, pid, prow, load_id)
    # the Gemini front page Azure's JSON may carry (the S3 gemini.title.json reading)
    azk = con.execute("SELECT azure_key FROM documents WHERE stem = ?", (stem,)).fetchone()[0]
    try:
        gp = json.loads((Path(__file__).resolve().parents[2] / azk).read_text(encoding="utf-8")).get(
            "gemini_front_page") if azk else None
    except Exception:
        gp = None
    if isinstance(gp, dict):
        con.execute("UPDATE documents SET has_gemini_title = 1 WHERE stem = ?", (stem,))
        for f, k in (("title", "title"), ("title_translated", "title_en")):
            v = gp.get(k)
            if v:
                lg = ("ar" if script(str(v)) == "Arab" else None) if f == "title" else "en"
                insert(con, "metadata_assertions", [dict(
                    pub_id=pid, field=f, value=str(v), value_norm=norm(f, v), lang=lg, script=script(str(v)),
                    form="gemini-title", source="azure-json:gemini_front_page", actor_id="model:gemini-front-page",
                    reason=f"read from the document's Azure JSON ({azk}), key gemini_front_page (the S3 "
                           f"gemini.title.json reading)", is_chosen=0, created=now(), load_id=load_id)], "INSERT")
                S["gemini_title"] += 1
    # choose one per (field, lang): person > judge > D33-corrected > printed (shown version) > catalogue > gemini
    con.execute("UPDATE metadata_assertions SET is_chosen = 0, chosen_rule = NULL WHERE pub_id = ?", (pid,))
    best = {}
    for r in con.execute("SELECT assert_pk, field, lang, form, version_id FROM metadata_assertions WHERE pub_id = ?",
                         (pid,)):
        if r["form"] in ("printed", "corrected") and r["version_id"] != cur["version_id"]:
            continue
        k = (r["field"], r["lang"])
        rk = CHOOSE.get(r["form"], 9)
        if k not in best or rk < best[k][0]:
            best[k] = (rk, r["assert_pk"], r["form"])
    for (f, lang), (rk, apk, form) in best.items():
        con.execute("UPDATE metadata_assertions SET is_chosen = 1, chosen_rule = ? WHERE assert_pk = ?",
                    (f"{form} (person > judge > corrected > printed > catalogue > gemini-title > qdrant)", apk))
    t = con.execute("SELECT value FROM metadata_assertions WHERE pub_id = ? AND field = 'title' AND is_chosen = 1 "
                    "ORDER BY lang = 'ar' DESC LIMIT 1", (pid,)).fetchone()
    y = con.execute("SELECT value FROM metadata_assertions WHERE pub_id = ? AND field = 'year' AND is_chosen = 1",
                    (pid,)).fetchone()
    con.execute("UPDATE publications SET title_shown = ?, year_shown = ? WHERE pub_id = ?",
                (t[0] if t else None, to_int(y[0]) if y else None, pid))
    # ---- dates, both calendars
    con.execute("UPDATE publication_dates SET pair_pk = NULL WHERE pub_id = ?", (pid,))
    con.execute("DELETE FROM publication_dates WHERE pub_id = ?", (pid,))
    dseen = Counter()
    for d in R["dates"]:
        y = d["year"]
        if not y:
            continue
        cal = calendar_of(d["printed"], y)
        dt = {"pub": "published"}.get(d["date_type"], d["date_type"] or "published")
        mo = None
        if d.get("iso") and re.match(r"^\d{4}-\d{2}", d["iso"]):
            mo = int(d["iso"][5:7])
        d1 = fill_pk("publication_dates", [dict(pub_id=pid, date_type=dt, calendar=cal, year=y, month=mo,
                                                 precision="month" if mo else "year", printed=d["printed"],
                                                 derivation="read")], dseen)[0]
        if cal == "hijri":
            S["hijri_dates"] += 1
            d2 = fill_pk("publication_dates", [dict(pub_id=pid, date_type=dt, calendar="gregorian",
                                                     year=hijri_to_greg(y), month=None, precision="year", printed=None,
                                                     derivation="converted", pair_pk=d1["date_pk"])], dseen)[0]
            d1["pair_pk"] = d2["date_pk"]
            insert(con, "publication_dates", [d1], "INSERT")
            insert(con, "publication_dates", [d2], "INSERT")
        else:
            insert(con, "publication_dates", [d1], "INSERT")
    if prow and prow["year_int"]:
        insert(con, "publication_dates", fill_pk("publication_dates", [dict(
            pub_id=pid, date_type="issue", calendar="gregorian", year=prow["year_int"], month=None, precision="year",
            printed=prow["year"], derivation="catalogue")], dseen), "INSERT")
        hy = to_int(prow["year_hijri"]) if prow["year_hijri"] else None
        if hy:
            insert(con, "publication_dates", fill_pk("publication_dates", [dict(
                pub_id=pid, date_type="issue", calendar="hijri", year=hy, month=None, precision="year",
                printed=prow["year_hijri"], derivation="catalogue")], dseen), "INSERT")
    # ---- languages, abstracts, keywords
    con.execute("DELETE FROM publication_languages WHERE pub_id = ?", (pid,))
    if art["language"]:
        insert(con, "publication_languages", [dict(pub_id=pid, lang=LANG3.get(art["language"][:2], "und"), role="text",
                                                   source="masters", method="jats-xml-lang", share=None)],
               "INSERT OR IGNORE")
    for x in (prow["language"] or "").split(",") if prow else []:
        if x.strip():
            insert(con, "publication_languages", [dict(pub_id=pid, lang=LANG3.get(x.strip().lower(), "und"),
                                                       role="text", source="catalogue", method="catalogue-041",
                                                       share=None)], "INSERT OR IGNORE")
    con.execute("DELETE FROM abstracts WHERE pub_id = ?", (pid,))
    babs = {}
    for a in R["abstracts"]:
        lg, how = lang_detect(a["text"])
        r = con.execute("SELECT anchor_pk FROM blocks WHERE version_id = ? AND block_id = ?",
                        (cur["version_id"], a["block_id"])).fetchone()
        insert(con, "abstracts", [dict(pub_id=pid, lang=lg, lang_method=f"{how} (printed label {a['lang']})",
                                       seq=a["seq"], text=a["text"], form="printed", version_id=cur["version_id"],
                                       block_id=a["block_id"], anchor_pk=r[0] if r else None)], "INSERT")
        babs[lg] = 1
    for a in cabs:
        lg, how = lang_detect(a["text"])
        insert(con, "abstracts", [dict(pub_id=pid, lang=lg, lang_method=how, seq=a["seq"], text=a["text"],
                                       form="catalogue", export_id=EXPORT)], "INSERT")
    con.execute("DELETE FROM publication_keywords WHERE pub_id = ?", (pid,))
    kwb = con.execute("SELECT anchor_pk FROM blocks WHERE version_id = ? AND role = 'keywords' LIMIT 1",
                      (cur["version_id"],)).fetchone()
    for k in R["keywords"] + ckw:
        tk = k["term_key"]
        if not tk:
            continue
        insert(con, "keyword_terms", [dict(term_key=tk, display=k["term"], lang=k["lang"])], "INSERT OR IGNORE")
        tid = con.execute("SELECT term_id FROM keyword_terms WHERE term_key = ?", (tk,)).fetchone()[0]
        insert(con, "publication_keywords", [dict(pub_id=pid, term_id=tid, source=k["source"], seq=k["seq"],
                                                  printed=k.get("term_printed") or k["term"],
                                                  version_id=cur["version_id"] if k["source"] == "masters" else None,
                                                  anchor_pk=kwb[0] if kwb and k["source"] == "masters" else None)],
               "INSERT OR IGNORE")
    # ---- external ids
    con.execute("DELETE FROM external_ids WHERE entity_kind = 'W' AND entity_id = ?", (pid,))
    ext = [("qdrant-doc", stem, "mandumah", "mandumah_v2 payload doc_id = stem"),
           ("s3-key", f"{stem}/{stem}.pdf", "mandumah", "s3://mandumah-source-docs")]
    if prow:
        ext += [("c999", prow["c999"], "mandumah", "catalogue 999$c"),
                ("001", prow["record_id"], "mandumah", "catalogue 001 (not unique)")]
        if prow["doi"]:
            ext.append(("doi", norm("doi", prow["doi"]), "mandumah", "catalogue 024"))
    if art["doi"]:
        ext.append(("doi", norm("doi", art["doi"]), "publisher", "printed on the page (masters)"))
    for sc, v, by, src in ext:
        if v:
            insert(con, "external_ids", [dict(entity_kind="W", entity_id=pid, scheme=sc, value=v, assigned_by=by,
                                              source=src, anchor_pk=None)], "INSERT OR IGNORE")
    # ---- authorships: the shown version's byline mentions + the primary record's contributors
    authorships(con, pid, cur["version_id"], R, prim, cauth, load_id, S)
    # ---- catalogue reports for this document (print vs catalogue, recomputed; plus record-level problems)
    con.execute("DELETE FROM catalogue_reports WHERE pub_id = ? AND status = 'open'", (pid,))
    authors = [dict(a) for a in R["authors"]]
    load46.match_authors(authors, cauth)
    reps = load46.disagreements(art, crow, cauth, authors, R["keywords"] + ckw, R["abstracts"] + cabs, cur["run"])
    KIND = {"title": "title", "title_en": "title", "authors": "author-count", "year": "year", "fpage": "page-range",
            "lpage": "page-range", "volume": "volume", "issue": "issue", "doi": "doi", "language": "language"}
    rrows = []
    for d in reps:
        f = d["field"]
        kind = KIND.get(f) or ("name-differs" if f.startswith("author ") and d["kind"] == "name" else
                               "missing-author" if f.startswith("author ") else
                               "missing-in-catalogue" if d["kind"] == "missing-in-catalogue" else f)
        who = "catalogue" if d["kind"] == "catalogue-fits-scan" else ("print" if d["kind"] in (
            "masters-fits-scan", "missing-in-catalogue") else "unknown")
        anc = title_anchor.get(cur["version_id"]) if kind == "title" else None
        if kind == "page-range":
            pg = 1 if f == "fpage" else con.execute("SELECT max(page) FROM pages WHERE stem = ?", (stem,)).fetchone()[0]
            r = con.execute("SELECT anchor_pk FROM page_regions WHERE version_id = ? AND page = ? AND role = 'pageNumber' "
                            "LIMIT 1", (cur["version_id"], pg)).fetchone()
            anc = r[0] if r else None
        rrows.append(dict(kind=kind, field=f, c999=d["c999"], pub_id=pid, stem=stem, version_id=cur["version_id"],
                          catalogue_value=d["catalogue_value"], our_value=d["masters_value"], who_is_right=who,
                          severity=d["severity"], evidence=d["kind"], anchor_pk=anc, found_in_export=EXPORT,
                          status="open", load_id=load_id, note=d["note"]))
        S["reports"] += 1
    if len([c for c in crow if c["c999"]]) > 1:
        rrows.append(dict(kind="stem-on-several-records", field="pdf_ids", c999=prim["c999"] if prim else None,
                          pub_id=pid, stem=stem, version_id=cur["version_id"],
                          catalogue_value=", ".join(c["c999"] for c in crow if c["c999"]), our_value=None,
                          who_is_right="unknown", severity="medium", evidence="one file named by several records",
                          anchor_pk=None, found_in_export=EXPORT, status="open", load_id=load_id,
                          note="; ".join((c["title"] or "")[:60] for c in crow)))
        S["reports"] += 1
    insert(con, "catalogue_reports", rrows, "INSERT")


EDITORIAL_ROLE = re.compile(r"^(?:رئيس|مدير|سكرتير|أمين|امين)\s+(?:ال)?تحرير|^المحرر$|^editor[- ]in[- ]chief$|^the editor$|"
                            r"^r[ée]dacteur en chef$", re.I)
EDITORIAL_BODY = re.compile(r"^(?:أسرة|اسرة|هيئة|هيئه|لجنة|لجنه|مجلس)\s+(?:ال)?(?:تحرير|مجلة|المجلة|التحرير)|^التحرير$|"
                            r"^editorial (?:board|team|committee)$|^the editors$|^la r[ée]daction$|^comit[ée] de r[ée]daction$",
                            re.I)


def _given_tokens(heading: str | None, latin: str | None) -> list:
    out = []
    for h in (heading, latin):
        h, _ = split_life(h or "")
        if not h:
            continue
        g = re.split(r"\s*[،,]\s*", h, maxsplit=1)[1] if re.search("[،,]", h) else h
        ws = [re.sub(r"^ال(?=\S{2,})", "", w) for w in akey(g).split()]
        if ws:
            out.append(ws[0] + ws[1] if ws[0] == "عبد" and len(ws) > 1 else ws[0])
    return out


def given_agrees(printed: str | None, heading: str | None, latin: str | None) -> bool:
    """A weak name match is only the same person when the catalogue's given name is in the printed name (or its
    initial is: «M. Seklani» = «Seklani, Mahmoud»). «بهي الدين حافظ» is not «حافظ، صلاح الدين»."""
    _, p = split_titles(printed or "")
    ws = [re.sub(r"^ال(?=\S{2,})", "", w) for w in akey(p).split()]
    joined = "".join(ws)
    toks = set(ws) | {a + b for a, b in zip(ws, ws[1:]) if a == "عبد"}
    for g in _given_tokens(heading, latin):
        if g in toks or (len(g) >= 4 and g in joined):
            return True
        if re.fullmatch(r"[a-z]", g[:1] or "") and any(len(w) == 1 and w == g[0] for w in ws):
            return True
    return False


def authorships(con, pid, vid, R, prim, cauth, load_id, S):
    """The shown version's bylines joined to the primary record's contributors. Person ids are given by
    refresh_persons (a global pass), except that an authority id in hand is written here already."""
    con.execute("DELETE FROM authorship_mentions WHERE authorship_pk IN (SELECT authorship_pk FROM authorships WHERE "
                "pub_id = ?)", (pid,))
    con.execute("DELETE FROM authorships WHERE pub_id = ?", (pid,))
    mentions = {r["byline_pos"]: r for r in con.execute("SELECT * FROM byline_mentions WHERE version_id = ?", (vid,))}
    authors = [dict(a) for a in R["authors"]]
    load46.match_authors(authors, cauth)
    c999 = prim["c999"] if prim else None
    groups = {}          # catalogue seq or own key -> list of authors
    for a in authors:
        k = ("c", a["catalogue_seq"]) if a["catalogue_seq"] is not None and a["match"] in (
            "name", "name-variant", "script-twin", "weak") else ("m", a["seq"])
        groups.setdefault(k, []).append(a)
    pos = 0
    used_c = set()
    rows, links = [], []
    for k, grp in groups.items():
        pos += 1
        a = grp[0]
        c = next((x for x in cauth if x["seq"] == a["catalogue_seq"]), None) if k[0] == "c" else None
        person, method, score, inst = None, None, None, None
        role = "author"
        why = None
        printed0 = " ".join(split_titles(a["printed_name"] or "")[1].split())
        if c:
            used_c.add(c["seq"])
            rr = (c["role"] or "").strip()
            role = ROLE.get(rr.lower(), ROLE.get(rr, "author"))
            weak = all(x["match"] in ("weak", "script-twin") for x in grp) and any(x["match"] == "weak" for x in grp)
            if weak and not any(given_agrees(x["printed_name"], c["name"], c["latin"]) for x in grp):
                method = "weak-name-rejected"
                why = "the catalogue's given name is not in the printed name; its authority id is not taken"
            elif c["authority_id"]:
                person = public_id(con, "person", f"auth:{c['authority_id']}", load_id)
                method = {"name": "exact" if (a["name_score"] or 0) >= 0.95 else "token-subset",
                          "name-variant": "transliteration", "script-twin": "script-twin",
                          "weak": "weak-name+given-name"}.get(a["match"], a["match"])
            else:
                method = "weak-name+given-name" if weak else a["match"]
            score = a["name_score"]
        if EDITORIAL_ROLE.search(printed0):
            role, method, person = "editor", "editorial-role", None
            why = "an editorial role printed as a byline, not a name"
        elif EDITORIAL_BODY.search(printed0):
            role, method, person = "corporate", "corporate-byline", None
            inst = public_id(con, "institution", f"byline-corp:{akey(printed0).replace(' ', '')}", load_id)
            con.execute("INSERT OR IGNORE INTO institutions (inst_id, kind, status, source) VALUES (?, 'committee', "
                        "'active', 'byline')", (inst,))
            con.execute("INSERT OR IGNORE INTO institution_names VALUES (?,?,?,?, 'printed', ?, 1, 'byline')",
                        (inst, printed0, "ar" if script(printed0) == "Arab" else None, script(printed0),
                         key(printed0)))
            why = "a corporate byline (the journal's editorial body)"
        r = dict(pub_id=pid, position=pos, role_code=role, role_raw=c["role"] if c else None, person_id=person,
                 inst_id=inst, c999=c999 if c else None, catalogue_seq=c["seq"] if c else None,
                 method=method or "provisional", score=score, asserted_by="link47",
                 evidence=jdump(dict(printed=[x["printed_name"] for x in grp], catalogue=c["name"] if c else None,
                                     latin=c["latin"] if c else None, match=a["match"],
                                     authority_not_taken=c["authority_id"] if c and method == "weak-name-rejected"
                                     else None, note=why)), from_version=vid)
        rows.append(r)
        for x in grp:
            m = mentions.get(x["seq"])
            if m:
                links.append(m["mention_pk"])
        links.append(None)
        S["authorships"] += 1
    fill_pk("authorships", rows)
    i = 0
    for r in rows:
        while links[i] is not None:
            con.execute("INSERT OR IGNORE INTO authorship_mentions VALUES (?,?)", (r["authorship_pk"], links[i]))
            i += 1
        i += 1
    insert(con, "authorships", rows, "INSERT")
    crow = []
    for c in cauth:
        if c["seq"] in used_c:
            continue
        pos += 1
        rr = (c["role"] or "").strip()
        role = ROLE.get(rr.lower(), ROLE.get(rr, "author"))
        inst = None
        person = None
        if c["is_org"]:
            inst = public_id(con, "institution", f"cat-corp:{c['authority_id'] or key(c['name']).replace(' ', '')}",
                             load_id)
            if not con.execute("SELECT 1 FROM institutions WHERE inst_id = ?", (inst,)).fetchone():
                con.execute("INSERT INTO institutions (inst_id, kind, status, catalogue_authority_id, source) VALUES "
                            "(?, 'committee', 'active', ?, 'catalogue')", (inst, c["authority_id"]))
                con.execute("INSERT OR IGNORE INTO institution_names VALUES (?,?,?,?, 'catalogue-heading', ?, 1, "
                            "'catalogue')", (inst, c["name"], None, script(c["name"]), key(c["name"])))
            role = "corporate"
        elif c["authority_id"]:
            person = public_id(con, "person", f"auth:{c['authority_id']}", load_id)
        else:
            person = public_id(con, "person", f"catalogue:{c999}|{c['seq']}", load_id)
        crow.append(dict(pub_id=pid, position=pos, role_code=role, role_raw=c["role"], person_id=person, inst_id=inst,
                         c999=c999, catalogue_seq=c["seq"], method="catalogue-only", score=None,
                         asserted_by="catalogue", evidence=jdump(dict(catalogue=c["name"])), from_version=vid))
        S["authorships_catalogue_only"] += 1
    insert(con, "authorships", crow, "INSERT OR IGNORE")


# ------------------------------------------------------------------ persons, names, institutions (global, cheap)
MIN_CLUSTER_TOKENS = 3     # a cited name joins an authority person by name alone only with at least 3 words


def _toks(name: str | None) -> list:
    _, s = split_titles(split_life(name or "")[0])
    return akey(s).split()


def refresh_persons(con, mcon, load_id):
    """Persons as a function of the whole database (never of the order steps ran in):
    1. an authority id in hand is the person (authorships, catalogue-only contributors, supervisions, cited authors
       found in a linked record);
    2. a printed name with no authority joins the one authority person carrying that folded name (when the
       catalogue gives that heading to no other authority id: no homonym); failing that, printed names with the same
       folded name AND a second signal (journal, institution, e-mail, a co-author) are one provisional person named
       after its first mention ('founder:<anchor>'); otherwise a person of its own mention (never a name alone);
    3. a cited author whose full name equals a byline name of an article citing the work is that byline's person
       (true self-citation), as is one whose >= 3-word name equals one authority person's name.
    Ids retired by this pass are written to merged_ids."""
    old_auth = {(r[0], r[1]): r[2] for r in con.execute("SELECT pub_id, position, person_id FROM authorships "
                                                         "WHERE person_id IS NOT NULL")}
    old_ids = {r[0] for r in con.execute("SELECT person_id FROM persons")}
    contrib = {(r["c999"], r["seq"]): dict(r) for r in con.execute(
        "SELECT c999, seq, name, latin, authority_id, is_org FROM catalogue_contributors")}
    # names carried by each authority (every heading in the db with that id)
    auth_names = defaultdict(set)
    for c in contrib.values():
        if c["authority_id"] and not c["is_org"]:
            for n in (c["name"], c["latin"]):
                if n:
                    auth_names[c["authority_id"]].add(heading_key(n))
    au = [dict(r) for r in con.execute(
        "SELECT a.authorship_pk, a.pub_id, a.position, a.c999, a.catalogue_seq, a.method, a.evidence, a.inst_id, "
        "a.role_code FROM authorships a ORDER BY a.pub_id, a.position")]
    mention_of = defaultdict(list)
    for r in con.execute("""SELECT am.authorship_pk, b.name_text, b.printed, ia.anchor_key, b.byline_pos FROM
                            authorship_mentions am JOIN byline_mentions b USING (mention_pk)
                            LEFT JOIN ink_anchors ia ON ia.anchor_pk = b.anchor_pk ORDER BY b.byline_pos, b.script"""):
        mention_of[r["authorship_pk"]].append(dict(r))
    assign = {}
    for a in au:
        c = contrib.get((a["c999"], a["catalogue_seq"])) if a["catalogue_seq"] is not None else None
        if a["method"] in ("editorial-role", "corporate-byline") or a["inst_id"]:
            assign[a["authorship_pk"]] = (None, a["method"], None)
        elif c and c["authority_id"] and not c["is_org"] and a["method"] != "weak-name-rejected":
            assign[a["authorship_pk"]] = (f"auth:{c['authority_id']}", a["method"], None)
            for m in mention_of.get(a["authorship_pk"], []):
                auth_names[c["authority_id"]].add(name_key(m["name_text"] or m["printed"]))
        elif c and a["method"] == "catalogue-only" and not c["is_org"]:
            assign[a["authorship_pk"]] = (f"catalogue:{c['c999']}|{c['seq']}", a["method"], None)
    key_auth = defaultdict(set)
    for aid, ks in auth_names.items():
        for k in ks:
            if k:
                key_auth[k].add(aid)
    homonym_cache = {}
    # fix round 2: who else in the WHOLE catalogue carries a printed / cited name (not only the target's heading)
    want = set()
    for a in au:
        for m in mention_of.get(a["authorship_pk"], []):
            want.add(name_key(m["name_text"] or m["printed"]))
        for n in (json.loads(a["evidence"] or "{}").get("printed") or []):
            want.add(name_key(n))
    for r in con.execute("SELECT printed FROM cited_work_authors"):
        want.add(name_key(r[0]))
    holders = catalogue_holders(mcon, want)
    n_clash = Counter()

    def clash(nk, aid):
        """the catalogue gives this folded name to an authority other than aid"""
        return bool(holders.get(nk, set()) - {aid})

    def homonym(aid):
        """the authority's own folded heading is held by another authority id in the catalogue too"""
        if aid not in homonym_cache:
            r = mcon.execute("SELECT count(DISTINCT b.authority_id) FROM authors a JOIN authors b ON b.name_folded = "
                             "a.name_folded WHERE a.authority_id = ? AND b.authority_id IS NOT NULL AND "
                             "b.authority_id <> ''", (aid,)).fetchone()
            homonym_cache[aid] = (r[0] or 0) > 1
        return homonym_cache[aid]

    # second signals for clustering names without an authority: journal, institution, e-mail, co-authors
    jour = {r[0]: r[1] for r in con.execute("SELECT pub_id, journal_id FROM publications")}
    aff_of = defaultdict(set)
    for r in con.execute("""SELECT am.authorship_pk, f.org_text, b.email FROM authorship_mentions am
                            JOIN byline_mentions b USING (mention_pk)
                            LEFT JOIN affiliation_mentions f ON f.mention_pk = b.mention_pk"""):
        if r["org_text"]:
            aff_of[r["authorship_pk"]].add("org:" + akey(r["org_text"]).replace(" ", ""))
        if r["email"]:
            aff_of[r["authorship_pk"]].add("mail:" + r["email"].strip().lower())
    pending = []
    for a in au:
        if a["authorship_pk"] in assign:
            continue
        ms = mention_of.get(a["authorship_pk"], [])
        names = [m["name_text"] or m["printed"] for m in ms] or (json.loads(a["evidence"] or "{}").get("printed") or [])
        hits = {x for n in names for x in key_auth.get(name_key(n), ())}
        if len(hits) == 1 and any(clash(name_key(n), next(iter(hits))) for n in names):
            n_clash["authorship"] += 1
        elif len(hits) == 1 and len(_toks(names[0] if names else "")) >= 2 and not homonym(next(iter(hits))):
            assign[a["authorship_pk"]] = (f"auth:{hits.pop()}", "name-key-to-authority", 0.7)
            continue
        best = max(names, key=lambda n: (len(_toks(n)), script(n) == "Arab")) if names else ""
        anc = ms[0]["anchor_key"] if ms and ms[0]["anchor_key"] else f"{a['pub_id']}|{a['position']}"
        a["_nk"], a["_anc"], a["_ntok"] = name_key(best), anc, len(_toks(best))
        a["_sig"] = {f"journal:{jour.get(a['pub_id'])}"} | aff_of.get(a["authorship_pk"], set())
        pending.append(a)
    names_of_pub = defaultdict(set)
    for a in pending:
        names_of_pub[a["pub_id"]].add(a["_nk"])
    for a in pending:
        a["_sig"] |= {"coauthor:" + k for k in names_of_pub[a["pub_id"]] if k != a["_nk"]}
    # the same folded name (>= 2 words) AND a second signal: one provisional person, named after its first mention
    uf = {}

    def find(x):
        while uf.get(x, x) != x:
            x = uf[x]
        return x
    by_nk = defaultdict(list)
    for a in pending:
        if a["_nk"] and a["_ntok"] >= 2:
            by_nk[a["_nk"]].append(a)
    for nk_, grp in by_nk.items():
        for i, x in enumerate(grp):
            for y in grp[:i]:
                if x["pub_id"] != y["pub_id"] and x["_sig"] & y["_sig"]:
                    rx, ry = find(x["authorship_pk"]), find(y["authorship_pk"])
                    if rx != ry:
                        uf[max(rx, ry)] = min(rx, ry)
    members = defaultdict(list)
    for a in pending:
        members[find(a["authorship_pk"])].append(a)
    for root, grp in members.items():
        if len(grp) > 1:
            founder = min(x["_anc"] for x in grp)
            for x in grp:
                assign[x["authorship_pk"]] = (f"founder:{founder}", "name-cluster+second-signal", 0.6)
        else:
            x = grp[0]
            assign[x["authorship_pk"]] = (f"mention:{x['_anc']}" if "|p" in x["_anc"] else f"byline:{x['_anc']}",
                                          "provisional", None)
    upd = []
    for a in au:
        nat, how, sc = assign[a["authorship_pk"]]
        pid = public_id(con, "person", nat, load_id) if nat else None
        a["person_id"] = pid
        if how in ("name-key-to-authority", "name-cluster+second-signal", "provisional") and \
                a["method"] != "weak-name-rejected":
            upd.append((pid, how, sc, a["authorship_pk"]))
        else:
            upd.append((pid, a["method"], None, a["authorship_pk"]))
    con.executemany("UPDATE authorships SET person_id = ?, method = ?, score = coalesce(?, score) WHERE "
                    "authorship_pk = ?", upd)
    # supervisions' people
    sup_ids = set()
    for r in con.execute("SELECT supervisor_person_id, student_person_id FROM supervisions"):
        sup_ids |= {r[0], r[1]} - {None}
    # cited authors
    con.execute("UPDATE cited_work_authors SET person_id = NULL, authority_id = NULL, match_method = NULL, "
                "match_score = NULL")
    cwa = [dict(r) for r in con.execute("SELECT cited_work_pk, seq, printed, name_key FROM cited_work_authors "
                                        "ORDER BY cited_work_pk, seq")]
    linked = defaultdict(list)
    for r in con.execute("""SELECT l.cited_work_pk, p.c999 FROM citation_links l JOIN publications p ON
                            p.pub_id = l.target_pub_id WHERE l.status = 'accepted' AND l.best = 1 AND
                            p.c999 IS NOT NULL"""):
        linked[r[0]].append(r[1])
    citing = defaultdict(set)
    for r in con.execute("""SELECT DISTINCT m.cited_work_pk, d.pub_id FROM cited_work_members m
                            JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk
                            JOIN versions v ON v.version_id = c.version_id AND v.is_current = 1
                            JOIN documents d ON d.stem = v.stem"""):
        citing[r[0]].add(r[1])
    by_pub = defaultdict(list)
    for a in au:
        if not a["person_id"]:
            continue
        ns = [m["name_text"] or m["printed"] for m in mention_of.get(a["authorship_pk"], [])]
        c = contrib.get((a["c999"], a["catalogue_seq"])) if a["catalogue_seq"] is not None else None
        if c and a["method"] != "weak-name-rejected":
            ns += [heading_display(c["name"]), heading_display(c["latin"])]
        for n in ns:
            if n and len(_toks(n)) >= 2:
                by_pub[a["pub_id"]].append((name_key(n), a["person_id"]))
    cu = []
    n_cited = Counter()
    for r in cwa:
        sn = [w for w in key(r["printed"]).split() if len(re.sub(r"^ال", "", w)) >= 3]
        got = None
        for c999 in linked.get(r["cited_work_pk"], []):
            for c in (x for x in contrib.values() if x["c999"] == c999 and x["authority_id"] and not x["is_org"]):
                ws = set(key(c["name"]).split()) | {re.sub(r"^ال", "", w) for w in key(c["name"]).split()} | \
                    set(akey(c["latin"] or "").split())
                if sn and any(s_ in ws or re.sub(r"^ال", "", s_) in ws for s_ in sn[-1:]):
                    got = (f"auth:{c['authority_id']}", c["authority_id"], "surname-in-linked-record", 0.9)
                    break
            if got:
                break
        nk = name_key(r["printed"])
        if not got and len(_toks(r["printed"])) >= 2:
            for pub in sorted(citing.get(r["cited_work_pk"], ())):
                hit = sorted({p for k, p in by_pub.get(pub, []) if k == nk})
                if len(hit) == 1:
                    got = (None, None, "name-equals-citing-byline", 0.85, hit[0])
                    break
        if not got and len(_toks(r["printed"])) >= MIN_CLUSTER_TOKENS and len(key_auth.get(nk, ())) == 1 and \
                not homonym(next(iter(key_auth[nk]))):
            aid = next(iter(key_auth[nk]))
            if clash(nk, aid):
                n_clash["cited"] += 1
            else:
                got = (f"auth:{aid}", aid, "name-key-to-authority", 0.7)
        if got:
            pid = got[4] if len(got) > 4 else public_id(con, "person", got[0], load_id)
            cu.append((pid, got[1], got[2], got[3], r["cited_work_pk"], r["seq"]))
            n_cited[got[2]] += 1
    con.executemany("UPDATE cited_work_authors SET person_id = ?, authority_id = ?, match_method = ?, match_score = ? "
                    "WHERE cited_work_pk = ? AND seq = ?", cu)
    # the persons table
    ids = {r[0] for r in con.execute("SELECT person_id FROM authorships WHERE person_id IS NOT NULL UNION "
                                     "SELECT person_id FROM cited_work_authors WHERE person_id IS NOT NULL")} | sup_ids
    nat = {r[0]: r[1] for r in con.execute("SELECT public_id, natural_key FROM id_registry WHERE kind = 'person'")}
    con.execute("DELETE FROM person_names")
    con.execute("DELETE FROM person_authorities")
    con.execute("DELETE FROM persons")
    names = defaultdict(Counter)
    for a in au:
        for m in mention_of.get(a["authorship_pk"], []):
            if a["person_id"]:
                names[a["person_id"]][(m["name_text"], "printed")] += 1
        c = contrib.get((a["c999"], a["catalogue_seq"])) if a["catalogue_seq"] is not None else None
        if c and a["person_id"] and a["method"] != "weak-name-rejected":
            names[a["person_id"]][(c["name"], "catalogue-heading")] += 1
            if c["latin"]:
                names[a["person_id"]][(c["latin"], "catalogue-latin")] += 1
    for r in con.execute("""SELECT s.supervisor_person_id, s.student_person_id, s.c999 FROM supervisions s"""):
        for pid_, roles in ((r[0], ("supervisor",)), (r[1], ("author", "coauthor"))):
            if not pid_:
                continue
            nk_ = nat.get(pid_, "")
            for c in contrib.values():
                if (nk_.startswith("auth:") and c["authority_id"] == nk_[5:]) or nk_ == f"catalogue:{c['c999']}|{c['seq']}":
                    names[pid_][(c["name"], "catalogue-heading")] += 1
                    if c["latin"]:
                        names[pid_][(c["latin"], "catalogue-latin")] += 1
    for r in con.execute("SELECT person_id, printed FROM cited_work_authors WHERE person_id IS NOT NULL"):
        names[r["person_id"]][(r["printed"], "cited")] += 1
    prow, nrow, arow = [], [], []
    for pid in sorted(ids):
        nk = nat.get(pid, "")
        src = "catalogue-authority" if nk.startswith("auth:") else ("catalogue" if nk.startswith("catalogue:")
                                                                     else "cluster")
        ns = names.get(pid, Counter())
        if nk.startswith("auth:") and not any(f == "catalogue-heading" for (_, f) in ns):
            h = mcon.execute("SELECT name, latin FROM authors WHERE authority_id = ? AND name IS NOT NULL "
                             "GROUP BY name ORDER BY count(*) DESC, name LIMIT 1", (nk[5:],)).fetchone()
            if h:
                ns[(h["name"], "catalogue-heading")] += 1
                if h["latin"]:
                    ns[(h["latin"], "catalogue-latin")] += 1
        order = sorted(ns.items(), key=lambda x: (-x[1], x[0][1], x[0][0] or ""))
        heads = [n for (n, f), _ in order if f == "catalogue-heading" and n]
        ar = heads or [n for (n, f), _ in order if n and script(n) == "Arab"]
        la = [n for (n, f), _ in order if n and script(n) == "Latn" and f != "catalogue-heading"] or \
             [n for (n, f), _ in order if n and script(n) == "Latn"]
        life = {}
        for h in heads:
            life = split_life(h)[1]
            if life:
                break
        pref_ar = heading_display(ar[0]) if ar else None
        pref_la = heading_display(la[0]) if la else None
        prow.append(dict(person_id=pid, status="active" if src != "cluster" else "provisional",
                         preferred_name_ar=pref_ar, preferred_name_lat=pref_la,
                         birth_year_h=life.get("birth_year_h"), birth_year_g=life.get("birth_year_g"),
                         death_year_h=life.get("death_year_h"), death_year_g=life.get("death_year_g"),
                         source=src, created_load=load_id))
        for (n, f), k in sorted(ns.items(), key=lambda x: (x[0][1], x[0][0] or "")):
            if not n:
                continue
            pp = name_parts(n)
            nrow.append(dict(person_id=pid, full_form=n, script=script(n), lang=None, form_type=f, ism=pp["ism"],
                             nasab=pp["nasab"], nisba=pp["nisba"], laqab=pp["laqab"], kunya=pp["kunya"],
                             family=pp["family"] or pp["shuhra"], name_key=name_key(split_life(n)[0]), n_seen=k,
                             source="catalogue" if f.startswith("catalogue") else "masters"))
        if nk.startswith("auth:"):
            aid = nk[5:]
            n = mcon.execute("SELECT count(*), max(name) FROM authors WHERE authority_id = ?", (aid,)).fetchone()
            arow.append(dict(authority_id=aid, person_id=pid, heading=n[1], n_records=n[0], relation="same",
                             asserted_by="catalogue", reason="Mandumah authority id (a cataloguer's decision)"))
    # created_load: the load that first minted the id (the registry), not this pass
    reg = {r[0]: r[1] for r in con.execute("SELECT public_id, created_load FROM id_registry WHERE kind = 'person'")}
    for r in prow:
        r["created_load"] = reg.get(r["person_id"]) or load_id
    insert(con, "persons", prow)
    insert(con, "person_names", nrow, "INSERT OR IGNORE")
    insert(con, "person_authorities", arow)
    # retired ids: a person an authorship had before this pass that is gone now
    newp = {(a["pub_id"], a["position"]): a["person_id"] for a in au}
    for k, op in sorted(old_auth.items()):
        if op in old_ids and op not in ids and newp.get(k):
            con.execute("INSERT OR IGNORE INTO merged_ids VALUES (?,?, 'person', 'merged-into', ?, ?, 'load47', NULL)",
                        (op, newp[k], now(), "re-clustered: an authority id or a shared full name now joins it"))
    return len(prow)


def refresh_institutions(con, load_id):
    """inst46.rebuild (experiment 46) run on the shown versions' affiliations in a scratch db; its keys are turned
    into stable I-ids through the id registry."""
    mem = sqlite3.connect(":memory:")
    mem.row_factory = sqlite3.Row
    mem.executescript("""CREATE TABLE affiliations (stem, author_seq, seq, printed, orgname, dept, city, country, org_key,
        faculty_key, dept_key, aff_pk); CREATE TABLE article_authors (stem, seq, person_key);
        CREATE TABLE institutions (inst_key, level, name, parent_key, country, script, n, n_variants, source);
        CREATE TABLE institution_variants (inst_key, variant, n);""")
    rows = con.execute("""SELECT v.stem, b.byline_pos, am.seq, am.printed, am.org_text, am.dept_text, am.city,
                          am.country_printed, am.aff_pk, b.mention_pk FROM affiliation_mentions am
                          JOIN byline_mentions b USING (mention_pk) JOIN versions v ON v.version_id = b.version_id
                          WHERE v.is_current = 1 ORDER BY v.stem, b.byline_pos, b.script, am.seq""").fetchall()
    mem.executemany("INSERT INTO affiliations VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL,?)",
                    [(r["stem"], r["byline_pos"], r["seq"], r["printed"], r["org_text"], r["dept_text"], r["city"],
                      r["country_printed"], r["aff_pk"]) for r in rows])
    pk = {r["mention_pk"]: r for r in con.execute("""SELECT am.mention_pk, a.person_id FROM authorship_mentions am
                                                    JOIN authorships a USING (authorship_pk)""")}
    mem.executemany("INSERT INTO article_authors VALUES (?,?,?)",
                    [(r["stem"], r["byline_pos"], pk[r["mention_pk"]]["person_id"] if r["mention_pk"] in pk else None)
                     for r in rows])
    st = inst46.rebuild(mem)
    old_links = {(r[0], r[1]): r[2] for r in con.execute("SELECT aff_pk, level, inst_id FROM affiliation_links")}
    old_live = {r[0] for r in con.execute("SELECT inst_id FROM institutions")}
    con.execute("DELETE FROM affiliation_links")
    con.execute("DELETE FROM institution_relations")
    con.execute("DELETE FROM institution_names WHERE source = 'masters'")
    con.execute("DELETE FROM institutions WHERE source = 'masters'")
    con.execute("""DELETE FROM institution_names WHERE source = 'byline' AND inst_id NOT IN (SELECT inst_id FROM
                   authorships WHERE inst_id IS NOT NULL)""")
    con.execute("""DELETE FROM institutions WHERE source = 'byline' AND inst_id NOT IN (SELECT inst_id FROM
                   authorships WHERE inst_id IS NOT NULL)""")
    # numbered universities («جامعة قسنطينة 2», «Université d'Alger 3») are separate institutions: inst46 folds the
    # number away, so an affiliation naming one gets an institution of its own under the same key + number
    NUM = re.compile(r"(?:جامع\S*|univ\S*)[^0-9٠-٩|]{0,40}?\s([1-9١-٩])(?![0-9٠-٩])", re.I)
    numbered = {}
    for r in mem.execute("SELECT aff_pk, orgname, printed, org_key FROM affiliations"):
        m = NUM.search(fold(r["orgname"] or "") or "") or NUM.search(fold(r["printed"] or ""))
        if m and r["org_key"]:
            numbered[r["aff_pk"]] = (r["org_key"], fold(m.group(1)))
    iid = {}
    rows_i = list(mem.execute("SELECT * FROM institutions ORDER BY inst_key"))
    for r in rows_i:
        iid[r["inst_key"]] = public_id(con, "institution", f"inst46:{r['inst_key']}", load_id)
    KIND = [(r"جامع|univ", "university"), (r"وزار|ministr", "ministry"), (r"مركز|cent|معهد|institut", "centre"),
            (r"جمعي|societ|associat|اتحاد|union|نقاب", "society"), (r"دار\s|press|مطبع", "press")]
    for r in rows_i:
        k = {"faculty": "faculty", "department": "department"}.get(r["level"])
        if not k:
            k = next((v for p, v in KIND if re.search(p, fold(r["name"]), re.I)), "organisation")
        con.execute("INSERT OR REPLACE INTO institutions (inst_id, kind, parent_id, country_code, status, source) VALUES "
                    "(?,?,?,?, 'active', 'masters')", (iid[r["inst_key"]], k, iid.get(r["parent_key"]),
                                                       country_iso(r["country"])))
        if r["parent_key"] in iid:
            con.execute("INSERT OR IGNORE INTO institution_relations VALUES (?,?, 'parent', NULL, NULL, 'masters', ?)",
                        (iid[r["inst_key"]], iid[r["parent_key"]], "printed as part of it in an affiliation"))
    for r in mem.execute("SELECT * FROM institution_variants ORDER BY inst_key, variant"):
        con.execute("INSERT OR IGNORE INTO institution_names VALUES (?,?,?,?, 'printed', ?, ?, 'masters')",
                    (iid[r["inst_key"]], r["variant"], "ar" if script(r["variant"]) == "Arab" else None,
                     script(r["variant"]), inst46.norm_key(r["variant"]), r["n"]))
    n = 0
    split = {}
    fac_rows = []
    for aff, (ok, num) in sorted(numbered.items()):
        if ok not in iid:
            continue
        canon = mem.execute("SELECT name FROM institutions WHERE inst_key = ?", (ok,)).fetchone()
        if canon and re.search(rf"(?<![0-9]){num}(?![0-9])", fold(canon[0] or "")):
            continue                     # the institution's own name carries the number already
        # the numbered university may be an institution of its own already («جامعة قسنطينة 2 - عبد الحميد مهري»)
        base_t = set(fold(canon[0] or "").split()) if canon else set()
        own = [r_ for r_ in rows_i if r_["inst_key"] != ok and r_["level"] == "organisation" and base_t and
               base_t <= set(fold(r_["name"] or "").split()) and
               re.search(rf"(?<![0-9]){num}(?![0-9])", fold(r_["name"] or ""))]
        nid = iid[own[0]["inst_key"]] if own else public_id(con, "institution", f"inst46:{ok}#{num}", load_id)
        nm = mem.execute("SELECT orgname, printed FROM affiliations WHERE aff_pk = ?", (aff,)).fetchone()
        v = (nm[0] or nm[1] or "").split(" | ")[0]
        con.execute("DELETE FROM institution_names WHERE inst_id = ? AND name = ?", (iid[ok], v))
        for (nm2,) in con.execute("SELECT name FROM institution_names WHERE inst_id = ?", (iid[ok],)).fetchall():
            if re.search(rf"(?<![0-9]){num}(?![0-9])", fold(nm2)):      # «جامعة قسنطينة 2» is not «جامعة قسنطينة»
                con.execute("DELETE FROM institution_names WHERE inst_id = ? AND name = ?", (iid[ok], nm2))
                con.execute("INSERT OR IGNORE INTO institution_names VALUES (?,?,?,?, 'printed', ?, 1, 'masters')",
                            (nid, nm2, "ar" if script(nm2) == "Arab" else None, script(nm2),
                             inst46.norm_key(nm2) + f" {num}"))
        con.execute("INSERT OR IGNORE INTO institution_names VALUES (?,?,?,?, 'printed', ?, 1, 'masters')",
                    (nid, v, "ar" if script(v) == "Arab" else None, script(v), inst46.norm_key(v) + f" {num}"))
        if not own and nid not in split.values():
            base = con.execute("SELECT kind, parent_id, country_code FROM institutions WHERE inst_id = ?",
                               (iid[ok],)).fetchone()
            con.execute("INSERT OR REPLACE INTO institutions (inst_id, kind, parent_id, country_code, status, source) "
                        "VALUES (?,?,?,?, 'active', 'masters')", (nid, base[0], base[1], base[2]))
            con.execute("INSERT OR IGNORE INTO institution_relations VALUES (?,?, 'split-from', NULL, NULL, 'masters', ?)",
                        (nid, iid[ok], f"a numbered university (number {num}) printed in the affiliation"))
        split[aff] = nid
        # fix round 2: the faculty and department of a numbered university are its own, not the base's (inst46's
        # «fac:org:<base>/…» keys drop the number too): same key + number, parent the numbered university
        fk = mem.execute("SELECT faculty_key, dept_key FROM affiliations WHERE aff_pk = ?", (aff,)).fetchone()
        parent = nid
        for lvl, col in (("faculty", "faculty_key"), ("dept", "dept_key")):
            k_ = fk[col]
            if not k_ or k_ not in iid:
                continue
            sid = public_id(con, "institution", f"inst46:{k_}#{num}", load_id)
            base = con.execute("SELECT kind, country_code FROM institutions WHERE inst_id = ?", (iid[k_],)).fetchone()
            con.execute("INSERT OR REPLACE INTO institutions (inst_id, kind, parent_id, country_code, status, source) "
                        "VALUES (?,?,?,?, 'active', 'masters')", (sid, base[0], parent, base[1]))
            con.execute("INSERT OR IGNORE INTO institution_relations VALUES (?,?, 'parent', NULL, NULL, 'masters', ?)",
                        (sid, parent, f"printed as part of a numbered university (number {num}) in an affiliation"))
            con.execute("""INSERT OR IGNORE INTO institution_names SELECT ?, name, lang, script, type, name_key, n_seen,
                           source FROM institution_names WHERE inst_id = ?""", (sid, iid[k_]))
            split[(aff, lvl)] = sid
            parent = sid
    for r in mem.execute("SELECT * FROM affiliations ORDER BY aff_pk"):
        for lvl, col in (("org", "org_key"), ("faculty", "faculty_key"), ("dept", "dept_key")):
            if r[col] and r[col] in iid:
                tgt = split.get(r["aff_pk"] if lvl == "org" else (r["aff_pk"], lvl), iid[r[col]])
                con.execute("INSERT OR IGNORE INTO affiliation_links VALUES (?,?,?, ?, NULL, 'link47', ?)",
                            (r["aff_pk"], tgt, lvl, "inst46-pieces+folded-key" if tgt == iid[r[col]] else
                             "inst46-pieces+folded-key+university-number", jdump(dict(key=r[col]))))
                n += 1
        fac = mem.execute("SELECT name FROM institutions WHERE inst_key = ?", (r["faculty_key"],)).fetchone()
        if fac:
            fac_rows.append((fac[0], r["aff_pk"]))
    # an institution of the masters that nothing points at any more (a faculty moved under its numbered university)
    # is dropped, with its names and relations
    while True:
        dead = [r[0] for r in con.execute("""SELECT i.inst_id FROM institutions i WHERE i.source = 'masters' AND
                   i.inst_id NOT IN (SELECT inst_id FROM affiliation_links) AND
                   i.inst_id NOT IN (SELECT parent_id FROM institutions WHERE parent_id IS NOT NULL) AND
                   i.inst_id NOT IN (SELECT inst_id FROM authorships WHERE inst_id IS NOT NULL) AND
                   i.inst_id NOT IN (SELECT inst_id FROM publishers WHERE inst_id IS NOT NULL) AND
                   i.inst_id NOT IN (SELECT inst_id FROM supervisions WHERE inst_id IS NOT NULL)""")]
        if not dead:
            break
        for d in dead:
            con.execute("DELETE FROM institution_names WHERE inst_id = ?", (d,))
            con.execute("DELETE FROM institution_relations WHERE from_id = ? OR to_id = ?", (d, d))
            con.execute("DELETE FROM institutions WHERE inst_id = ?", (d,))
    live = {r[0] for r in con.execute("SELECT inst_id FROM institutions")}
    new_links = {(r[0], r[1]): r[2] for r in con.execute("SELECT aff_pk, level, inst_id FROM affiliation_links")}
    for k, oi in sorted(old_links.items()):
        ni = new_links.get(k)
        if oi in old_live and oi not in live and ni in live:
            con.execute("INSERT OR IGNORE INTO merged_ids VALUES (?,?, 'institution', 'merged-into', ?, ?, 'link47', "
                        "NULL)", (oi, ni, now(), "its affiliations now sit under a numbered university"))
    # the faculty inst46 reads out of an affiliation, for the shown versions only (the printed parts are never
    # overwritten, so a version shown once and then replaced keeps exactly what it was loaded with)
    con.execute("UPDATE affiliation_mentions SET faculty_text = NULL")
    con.executemany("UPDATE affiliation_mentions SET faculty_text = ? WHERE aff_pk = ?", fac_rows)
    return dict(institutions=len(iid), links=n, cross_script=len(st.get("cross_script") or []))


def refresh_supervisions(con, load_id):
    con.execute("DELETE FROM supervisions")
    for r in con.execute("""SELECT c.c999, c.seq, c.authority_id, r.thesis_json, r.year_int, r.year_hijri
                            FROM catalogue_contributors c JOIN catalogue_records r USING (c999)
                            WHERE c.role_code = 'supervisor'""").fetchall():
        sup = public_id(con, "person", f"auth:{r['authority_id']}" if r["authority_id"] else
                        f"catalogue:{r['c999']}|{r['seq']}", load_id)
        stu = con.execute("SELECT authority_id, seq FROM catalogue_contributors WHERE c999 = ? AND role_code IN "
                          "('author', 'coauthor') ORDER BY seq LIMIT 1", (r["c999"],)).fetchone()
        sp = public_id(con, "person", f"auth:{stu[0]}" if stu[0] else f"catalogue:{r['c999']}|{stu[1]}", load_id) \
            if stu else None
        th = json.loads(r["thesis_json"]) if r["thesis_json"] else {}
        con.execute("INSERT OR IGNORE INTO supervisions VALUES (?,?,?,?, NULL, NULL, ?, ?, 'catalogue')",
                    (r["c999"], sup, sp, jdump(th) if th else None, r["year_int"], r["year_hijri"]))


def refresh_translit(con, mcon):
    """Arabic↔Latin name tokens learned from the catalogue's own headings: an author row with both an Arabic heading
    «surname، given» and a Latin one «Surname, Given» whose parts have the same number of words pairs them word by
    word (all 1.08M such rows of marc.db; pairs seen at least 3 times kept)."""
    if con.execute("SELECT 1 FROM translit_pairs LIMIT 1").fetchone():
        return None
    pairs, tot = Counter(), Counter()
    for name, lat in mcon.execute("SELECT name, latin FROM authors WHERE latin IS NOT NULL AND latin <> '' AND "
                                  "is_org = 0"):
        a = [p.split() for p in re.split(r"\s*[،,]\s*", name or "")]
        b = [p.split() for p in re.split(r"\s*,\s*", lat or "")]
        if len(a) != len(b):
            continue
        for x, y in zip(a, b):
            if len(x) != len(y):
                continue
            for u, v in zip(x, y):
                u, v = key(u), latin_key(v)
                if u and v and script(u) == "Arab" and script(v) == "Latn":
                    pairs[(u, v)] += 1
                    tot[u] += 1
    rows = [dict(arabic=u, latin=v, n=n, share=round(n / tot[u], 4), source="catalogue-latin")
            for (u, v), n in pairs.items() if n >= 3]
    insert(con, "translit_pairs", rows)
    return len(rows)


def refresh_global(con, mcon, load_id) -> dict:
    """Everything that depends on the whole database rather than one document: supervisions, persons, institutions,
    the per-journal ISSN reports and the transliteration pairs. load47 and link47 both end with it, so the result does
    not depend on which step ran last."""
    S = Counter()
    refresh_supervisions(con, load_id)
    S["persons"] = refresh_persons(con, mcon, load_id)
    S.update({f"inst_{k}": v for k, v in refresh_institutions(con, load_id).items()})
    # ISSNs that fail their check digit: a report per journal
    con.execute("DELETE FROM catalogue_reports WHERE kind = 'invalid-issn' AND status = 'open'")
    rows = []
    for r in con.execute("SELECT journal_id, issn_raw, n_records FROM journal_issns WHERE valid_check = 0 OR "
                         "issn IS NULL ORDER BY journal_id, issn_raw").fetchall():
        rows.append(dict(kind="invalid-issn", field="773$x", c999=None, pub_id=None, stem=None, version_id=None,
                         catalogue_value=r["issn_raw"], our_value=None, who_is_right="catalogue", severity="low",
                         evidence=f"check digit (ISSN ISO 3297) fails; journal {r['journal_id']}",
                         found_in_export=EXPORT, status="open", load_id=load_id,
                         note=f"{r['n_records']} records carry it"))
        S["reports_issn"] += 1
    insert(con, "catalogue_reports", rows, "INSERT")
    # keyword terms: only those a publication uses, shown in their first printed form
    con.execute("DELETE FROM keyword_terms WHERE term_id NOT IN (SELECT term_id FROM publication_keywords)")
    con.execute("""UPDATE keyword_terms SET display = coalesce((SELECT min(k.printed) FROM publication_keywords k
                   WHERE k.term_id = keyword_terms.term_id), display)""")
    t = refresh_translit(con, mcon)
    if t is not None:
        S["translit_pairs"] = t
    return dict(S)


def refresh(con, mcon, stems, load_id) -> dict:
    S = Counter()
    for i, stem in enumerate(stems):
        refresh_stem(con, mcon, stem, load_id, S)
        if (i + 1) % 50 == 0:
            con.commit()
            print(f"  biblio {i + 1}/{len(stems)}", flush=True)
    S.update(refresh_global(con, mcon, load_id))
    return dict(S)
