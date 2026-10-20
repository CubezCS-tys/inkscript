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

from common47 import (E46, OUT43, calendar_of, fold, greg_to_hijri, hijri_to_greg, insert, issn_clean, jdump, key,
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
    r = con.execute("SELECT public_id FROM id_registry WHERE kind = ? AND natural_key = ?", (kind, natural)).fetchone()
    if r:
        return r[0]
    pre, width = {"person": ("A", 6), "institution": ("I", 6), "cited_work": ("C", 7)}[kind]
    n = con.execute("SELECT count(*) FROM id_registry WHERE kind = ?", (kind,)).fetchone()[0] + 1
    pid = f"{pre}{n:0{width}d}"
    while con.execute("SELECT 1 FROM id_registry WHERE public_id = ?", (pid,)).fetchone():
        n += 1
        pid = f"{pre}{n:0{width}d}"
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
        con.execute("INSERT OR IGNORE INTO subject_terms (scheme, term_ar, term_en, term_key) VALUES (?,?,?,?)",
                    (sch, ar, None if ar else term, tk))
        sid = con.execute("SELECT subject_id FROM subject_terms WHERE scheme = ? AND term_key = ?", (sch, tk)).fetchone()[0]
        con.execute("INSERT OR IGNORE INTO record_subjects VALUES (?,?,?)", (c, sid, k))
    return c


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


def ensure_catalogued_pub(con, mcon, c999: str) -> str | None:
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
    cat_assertions(con, pid, r)
    return pid


def cat_assertions(con, pid, r):
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
                         actor_id="catalogue:mandumah", is_chosen=0, created=now()))
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
        ensure_catalogued_pub(con, mcon, c["c999"])
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
            cu = con.execute("""INSERT INTO metadata_assertions (pub_id, field, value, value_norm, lang, script, form, source,
                                version_id, block_id, anchor_pk, actor_id, is_chosen, created, load_id)
                                VALUES (?,?,?,?,?,?, 'printed', 'masters', ?, NULL, ?, 'model:gemini-4-argon', 0, ?, ?)""",
                             (pid, f, str(v), norm(f, v), lang, script(str(v)), vid,
                              title_anchor[vid] if f == "title" else None, now(), load_id))
            if f in ch and ch[f]["corrected"] is not None:
                c = ch[f]
                con.execute("""INSERT INTO metadata_assertions (pub_id, field, value, value_norm, lang, script, form,
                               source, version_id, rule, reason, alternatives, supersedes, actor_id, is_chosen, created,
                               load_id) VALUES (?,?,?,?,?,?, 'corrected', 'rule', ?, ?, ?, ?, ?, 'rule:d33', 0, ?, ?)""",
                            (pid, f, str(c["corrected"]), norm(f, c["corrected"]), lang, script(str(c["corrected"])),
                             vid, f"{c['rule']}: {c['change_source']}", c["reason"], c["alternatives"], cu.lastrowid,
                             now(), load_id))
                S["d33"] += int(vid == cur["version_id"])
    if prow:
        cat_assertions(con, pid, prow)
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
                con.execute("INSERT INTO metadata_assertions (pub_id, field, value, value_norm, lang, script, form, "
                            "source, is_chosen, created, load_id) VALUES (?,?,?,?,?,?, 'gemini-title', "
                            "'s3-gemini-title', 0, ?, ?)", (pid, f, str(v), norm(f, v), lg, script(str(v)), now(),
                                                             load_id))
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
    for d in R["dates"]:
        y = d["year"]
        if not y:
            continue
        cal = calendar_of(d["printed"], y)
        dt = {"pub": "published"}.get(d["date_type"], d["date_type"] or "published")
        mo = None
        if d.get("iso") and re.match(r"^\d{4}-\d{2}", d["iso"]):
            mo = int(d["iso"][5:7])
        c1 = con.execute("INSERT INTO publication_dates (pub_id, date_type, calendar, year, month, precision, printed, "
                         "derivation) VALUES (?,?,?,?,?,?,?, 'read')", (pid, dt, cal, y, mo, "month" if mo else "year",
                                                                     d["printed"]))
        if cal == "hijri":
            S["hijri_dates"] += 1
            c2 = con.execute("INSERT INTO publication_dates (pub_id, date_type, calendar, year, precision, printed, "
                             "pair_pk, derivation) VALUES (?,?, 'gregorian', ?, 'year', NULL, ?, 'converted')",
                             (pid, dt, hijri_to_greg(y), c1.lastrowid))
            con.execute("UPDATE publication_dates SET pair_pk = ? WHERE date_pk = ?", (c2.lastrowid, c1.lastrowid))
    if prow and prow["year_int"]:
        con.execute("INSERT INTO publication_dates (pub_id, date_type, calendar, year, precision, printed, derivation) "
                    "VALUES (?, 'issue', 'gregorian', ?, 'year', ?, 'catalogue')", (pid, prow["year_int"], prow["year"]))
        hy = to_int(prow["year_hijri"]) if prow["year_hijri"] else None
        if hy:
            con.execute("INSERT INTO publication_dates (pub_id, date_type, calendar, year, precision, printed, "
                        "derivation) VALUES (?, 'issue', 'hijri', ?, 'year', ?, 'catalogue')", (pid, hy,
                                                                                               prow["year_hijri"]))
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
        con.execute("INSERT OR IGNORE INTO keyword_terms (term_key, display, lang) VALUES (?,?,?)", (tk, k["term"],
                                                                                                     k["lang"]))
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
        con.execute("""INSERT INTO catalogue_reports (kind, field, c999, pub_id, stem, version_id, catalogue_value,
                       our_value, who_is_right, severity, evidence, anchor_pk, found_in_export, status, load_id, note)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'open', ?, ?)""",
                    (kind, f, d["c999"], pid, stem, cur["version_id"], d["catalogue_value"], d["masters_value"], who,
                     d["severity"], d["kind"], anc, EXPORT, load_id, d["note"]))
        S["reports"] += 1
    if len([c for c in crow if c["c999"]]) > 1:
        con.execute("""INSERT INTO catalogue_reports (kind, field, c999, pub_id, stem, version_id, catalogue_value,
                       who_is_right, severity, evidence, found_in_export, status, load_id, note)
                       VALUES ('stem-on-several-records', 'pdf_ids', ?, ?, ?, ?, ?, 'unknown', 'medium', ?, ?, 'open',
                       ?, ?)""", (prim["c999"] if prim else None, pid, stem, cur["version_id"],
                                  ", ".join(c["c999"] for c in crow if c["c999"]), "one file named by several records",
                                  EXPORT, load_id, "; ".join((c["title"] or "")[:60] for c in crow)))
        S["reports"] += 1


def authorships(con, pid, vid, R, prim, cauth, load_id, S):
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
    for k, grp in groups.items():
        pos += 1
        a = grp[0]
        c = next((x for x in cauth if x["seq"] == a["catalogue_seq"]), None) if k[0] == "c" else None
        person, method, score = None, None, None
        role = "author"
        if c:
            used_c.add(c["seq"])
            rr = (c["role"] or "").strip()
            role = ROLE.get(rr.lower(), ROLE.get(rr, "author"))
            if c["authority_id"] and a["match"] != "weak":
                person = public_id(con, "person", f"auth:{c['authority_id']}", load_id)
                method = {"name": "exact" if (a["name_score"] or 0) >= 0.95 else "token-subset",
                          "name-variant": "transliteration", "script-twin": "script-twin"}.get(a["match"], a["match"])
            else:
                method = "weak-name" if a["match"] == "weak" else a["match"]
            score = a["name_score"]
        if person is None:
            # a printed name equal (folded) to a name of a person with an authority id seen elsewhere
            nk = name_key(a["printed_name"])
            r = con.execute("SELECT p.person_id FROM person_names n JOIN persons p USING (person_id) WHERE n.name_key = ? "
                            "AND p.source = 'catalogue-authority' LIMIT 2", (nk,)).fetchall() if nk else []
            if len(r) == 1:
                person, method, score = r[0][0], "name-key-to-authority", 0.7
            else:
                m = mentions.get(a["seq"])
                anc = con.execute("SELECT anchor_key FROM ink_anchors WHERE anchor_pk = ?", (m["anchor_pk"],)).fetchone() \
                    if m and m["anchor_pk"] else None
                nat = f"mention:{anc[0]}" if anc else f"byline:{R['article']['stem']}|{a['seq']}"
                person = public_id(con, "person", nat, load_id)
                method = method or "provisional"
        cu = con.execute("""INSERT INTO authorships (pub_id, position, role_code, role_raw, person_id, c999, catalogue_seq,
                            method, score, asserted_by, evidence, from_version) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (pid, pos, role, c["role"] if c else None, person, c999 if c else None,
                          c["seq"] if c else None, method, score, "link47",
                          jdump(dict(printed=[x["printed_name"] for x in grp], catalogue=c["name"] if c else None,
                                     latin=c["latin"] if c else None, match=a["match"])), vid))
        for x in grp:
            m = mentions.get(x["seq"])
            if m:
                con.execute("INSERT OR IGNORE INTO authorship_mentions VALUES (?,?)", (cu.lastrowid, m["mention_pk"]))
        S["authorships"] += 1
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
        con.execute("""INSERT OR IGNORE INTO authorships (pub_id, position, role_code, role_raw, person_id, inst_id, c999,
                       catalogue_seq, method, score, asserted_by, evidence, from_version)
                       VALUES (?,?,?,?,?,?,?,?, 'catalogue-only', NULL, 'catalogue', ?, ?)""",
                    (pid, pos, role, c["role"], person, inst, c999, c["seq"], jdump(dict(catalogue=c["name"])), vid))
        S["authorships_catalogue_only"] += 1


# ------------------------------------------------------------------ persons, names, institutions (global, cheap)
def refresh_persons(con, mcon, load_id):
    ids = {r[0] for r in con.execute("SELECT person_id FROM authorships WHERE person_id IS NOT NULL UNION "
                                     "SELECT person_id FROM cited_work_authors WHERE person_id IS NOT NULL UNION "
                                     "SELECT supervisor_person_id FROM supervisions UNION "
                                     "SELECT student_person_id FROM supervisions WHERE student_person_id IS NOT NULL")}
    nat = {r[0]: r[1] for r in con.execute("SELECT public_id, natural_key FROM id_registry WHERE kind = 'person'")}
    con.execute("DELETE FROM person_names")
    con.execute("DELETE FROM person_authorities")
    con.execute("DELETE FROM persons")
    names = defaultdict(Counter)
    for r in con.execute("""SELECT a.person_id, b.printed, b.name_text, b.script FROM authorships a
                            JOIN authorship_mentions am USING (authorship_pk) JOIN byline_mentions b USING (mention_pk)"""):
        names[r["person_id"]][(r["name_text"], "printed")] += 1
    for r in con.execute("""SELECT a.person_id, c.name, c.latin FROM authorships a JOIN catalogue_contributors c
                            ON c.c999 = a.c999 AND c.seq = a.catalogue_seq WHERE a.person_id IS NOT NULL"""):
        names[r["person_id"]][(r["name"], "catalogue-heading")] += 1
        if r["latin"]:
            names[r["person_id"]][(r["latin"], "catalogue-latin")] += 1
    for r in con.execute("SELECT person_id, printed FROM cited_work_authors WHERE person_id IS NOT NULL"):
        names[r["person_id"]][(r["printed"], "cited")] += 1
    prow, nrow, arow = [], [], []
    for pid in sorted(ids):
        nk = nat.get(pid, "")
        src = "catalogue-authority" if nk.startswith("auth:") else ("catalogue" if nk.startswith("catalogue:")
                                                                     else "cluster")
        ns = names.get(pid, Counter())
        ar = [n for (n, f), _ in ns.most_common() if f == "catalogue-heading"] or \
             [n for (n, f), _ in ns.most_common() if script(n) == "Arab"]
        la = [n for (n, f), _ in ns.most_common() if script(n) == "Latn"]
        pref_ar = None
        if ar:
            pref_ar = ar[0]
            if re.search("[،,]", pref_ar):
                a_, b_ = re.split(r"\s*[،,]\s*", pref_ar, maxsplit=1)
                pref_ar = f"{b_} {a_}".strip()
        prow.append(dict(person_id=pid, status="active" if src != "cluster" else "provisional",
                         preferred_name_ar=pref_ar, preferred_name_lat=la[0] if la else None, source=src,
                         created_load=load_id))
        for (n, f), k in ns.items():
            if not n:
                continue
            pp = name_parts(n)
            nrow.append(dict(person_id=pid, full_form=n, script=script(n), lang=None, form_type=f, ism=pp["ism"],
                             nasab=pp["nasab"], nisba=pp["nisba"], laqab=pp["laqab"], kunya=pp["kunya"],
                             family=pp["family"] or pp["shuhra"], name_key=name_key(n), n_seen=k,
                             source="catalogue" if f.startswith("catalogue") else "masters"))
        if nk.startswith("auth:"):
            aid = nk[5:]
            n = mcon.execute("SELECT count(*), max(name) FROM authors WHERE authority_id = ?", (aid,)).fetchone()
            arow.append(dict(authority_id=aid, person_id=pid, heading=n[1], n_records=n[0], relation="same",
                             asserted_by="catalogue", reason="Mandumah authority id (a cataloguer's decision)"))
    insert(con, "persons", prow)
    insert(con, "person_names", nrow, "INSERT OR IGNORE")
    insert(con, "person_authorities", arow)
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
                          WHERE v.is_current = 1""").fetchall()
    mem.executemany("INSERT INTO affiliations VALUES (?,?,?,?,?,?,?,?,NULL,NULL,NULL,?)",
                    [(r["stem"], r["byline_pos"], r["seq"], r["printed"], r["org_text"], r["dept_text"], r["city"],
                      r["country_printed"], r["aff_pk"]) for r in rows])
    pk = {r["mention_pk"]: r for r in con.execute("""SELECT am.mention_pk, a.person_id FROM authorship_mentions am
                                                    JOIN authorships a USING (authorship_pk)""")}
    mem.executemany("INSERT INTO article_authors VALUES (?,?,?)",
                    [(r["stem"], r["byline_pos"], pk[r["mention_pk"]]["person_id"] if r["mention_pk"] in pk else None)
                     for r in rows])
    st = inst46.rebuild(mem)
    con.execute("DELETE FROM affiliation_links")
    con.execute("DELETE FROM institution_relations")
    con.execute("DELETE FROM institution_names WHERE source = 'masters'")
    con.execute("DELETE FROM institutions WHERE source = 'masters'")
    iid = {}
    for r in mem.execute("SELECT * FROM institutions"):
        iid[r["inst_key"]] = public_id(con, "institution", f"inst46:{r['inst_key']}", load_id)
    KIND = [(r"جامع|univ", "university"), (r"وزار|ministr", "ministry"), (r"مركز|cent|معهد|institut", "centre"),
            (r"جمعي|societ|associat|اتحاد|union|نقاب", "society"), (r"دار\s|press|مطبع", "press")]
    for r in mem.execute("SELECT * FROM institutions"):
        k = {"faculty": "faculty", "department": "department"}.get(r["level"])
        if not k:
            k = next((v for p, v in KIND if re.search(p, fold(r["name"]), re.I)), "organisation")
        con.execute("INSERT OR REPLACE INTO institutions (inst_id, kind, parent_id, country_code, status, source) VALUES "
                    "(?,?,?,?, 'active', 'masters')", (iid[r["inst_key"]], k, iid.get(r["parent_key"]), r["country"]))
        if r["parent_key"] in iid:
            con.execute("INSERT OR IGNORE INTO institution_relations VALUES (?,?, 'parent', NULL, NULL, 'masters', ?)",
                        (iid[r["inst_key"]], iid[r["parent_key"]], "printed as part of it in an affiliation"))
    for r in mem.execute("SELECT * FROM institution_variants"):
        con.execute("INSERT OR IGNORE INTO institution_names VALUES (?,?,?,?, 'printed', ?, ?, 'masters')",
                    (iid[r["inst_key"]], r["variant"], "ar" if script(r["variant"]) == "Arab" else None,
                     script(r["variant"]), inst46.norm_key(r["variant"]), r["n"]))
    n = 0
    for r in mem.execute("SELECT * FROM affiliations"):
        for lvl, col in (("org", "org_key"), ("faculty", "faculty_key"), ("dept", "dept_key")):
            if r[col] and r[col] in iid:
                con.execute("INSERT OR IGNORE INTO affiliation_links VALUES (?,?,?, 'inst46-pieces+folded-key', NULL, "
                            "'link47', ?)", (r["aff_pk"], iid[r[col]], lvl, jdump(dict(key=r[col]))))
                n += 1
        org = mem.execute("SELECT name FROM institutions WHERE inst_key = ?", (r["org_key"],)).fetchone()
        fac = mem.execute("SELECT name FROM institutions WHERE inst_key = ?", (r["faculty_key"],)).fetchone()
        dep = mem.execute("SELECT name FROM institutions WHERE inst_key = ?", (r["dept_key"],)).fetchone()
        con.execute("UPDATE affiliation_mentions SET org_text = coalesce(?, org_text), faculty_text = ?, dept_text = "
                    "coalesce(?, dept_text), kind = CASE WHEN ? IS NOT NULL OR ? IS NOT NULL OR ? IS NOT NULL THEN "
                    "'institution' ELSE kind END WHERE aff_pk = ?",
                    (org[0] if org else None, fac[0] if fac else None, dep[0] if dep else None, r["org_key"],
                     r["faculty_key"], r["dept_key"], r["aff_pk"]))
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


def refresh(con, mcon, stems, load_id) -> dict:
    S = Counter()
    for i, stem in enumerate(stems):
        refresh_stem(con, mcon, stem, load_id, S)
        if (i + 1) % 50 == 0:
            con.commit()
            print(f"  biblio {i + 1}/{len(stems)}", flush=True)
    refresh_supervisions(con, load_id)
    S["persons"] = refresh_persons(con, mcon, load_id)
    S.update({f"inst_{k}": v for k, v in refresh_institutions(con, load_id).items()})
    # ISSNs that fail their check digit: a report per journal
    con.execute("DELETE FROM catalogue_reports WHERE kind = 'invalid-issn' AND status = 'open'")
    for r in con.execute("SELECT journal_id, issn_raw, n_records FROM journal_issns WHERE valid_check = 0 OR "
                         "issn IS NULL").fetchall():
        con.execute("INSERT INTO catalogue_reports (kind, field, catalogue_value, who_is_right, severity, evidence, "
                    "found_in_export, status, load_id, note) VALUES ('invalid-issn', '773$x', ?, 'catalogue', 'low', "
                    "?, ?, 'open', ?, ?)", (r["issn_raw"], f"check digit (ISSN ISO 3297) fails; journal {r['journal_id']}",
                                           EXPORT, load_id, f"{r['n_records']} records carry it"))
        S["reports_issn"] += 1
    t = refresh_translit(con, mcon)
    if t is not None:
        S["translit_pairs"] = t
    return dict(S)
