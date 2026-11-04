"""Every field the platform holds for one article, flat (2026-10-23, the Article page's "All fields" tab).

Each row says what the field is, its value, where the value came from and, when the reading has one, the ink it was
read from:

- `source` is one of
  - `page`: read from the scanned page (Azure's words, Gemini's structure: the masters);
  - `catalogue`: Mandumah's MARC record (or the journal / issue built from it);
  - `corrected`: a rule (D33 folios, ...) or a person changed it;
  - `derived`: counted or computed by our code from the above.
- `by` is who gave it (model:gemini-4-argon, catalogue:mandumah, rule:d33, person:...), when known;
- `chosen` marks the value the platform shows, when a field has several;
- `anchor` (an ink anchor key) or `page` + `block` point at the ink, which `/evidence/crop` cuts.
- `wos` is the Web of Science field tag the row answers to, where there is one (TI, AU, C1, SO, PY, DI, ...).

Groups come in the order of experiment 51's inventory (metadata, authors and affiliations, document level,
abstracts and keywords, page furniture, body structure, references, quality). Built on `pages.article` plus the
tables it does not read (abstracts, keywords, dates, languages, subjects, ISSN, publisher, ids, page regions,
Quran citations, catalogue contributors, catalogue reports)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from . import pages as P

GROUPS = [
    ("identity", "Identity"),
    ("title", "Title"),
    ("source", "Journal, issue and pages"),
    ("doctype", "Document type and what it is"),
    ("authors", "Authors and affiliations"),
    ("abstract", "Abstracts, keywords and subjects"),
    ("pages", "Page marks"),
    ("structure", "Body structure"),
    ("references", "References and citations"),
    ("quality", "Quality and corrections"),
]
META = {  # metadata_assertions.field -> (group, label, WoS tag)
    "title": ("title", "Title", "TI"), "subtitle": ("title", "Subtitle", None),
    "title_translated": ("title", "Translated title", None),
    "journal_title": ("source", "Journal title", "SO"), "volume": ("source", "Volume", "VL"),
    "issue": ("source", "Issue", "IS"), "year": ("source", "Year", "PY"), "year_hijri": ("source", "Year (Hijri)", None),
    "fpage": ("source", "First page", "BP"), "lpage": ("source", "Last page", "EP"),
    "language": ("source", "Language", "LA"), "doi": ("identity", "DOI", "DI"),
    "doc_type": ("doctype", "Document type", "DT"),
    "conference.name": ("doctype", "Conference name", "CT"), "conference.place": ("doctype", "Conference place", "CL"),
    "conference.date": ("doctype", "Conference date", "CY"),
    "thesis.degree": ("doctype", "Thesis degree", None), "thesis.university": ("doctype", "Thesis university", None),
    "thesis.year": ("doctype", "Thesis year", None), "thesis.supervisor": ("doctype", "Thesis supervisor", None),
    "reviewed_book.title": ("doctype", "Reviewed book: title", None),
    "reviewed_book.authors": ("doctype", "Reviewed book: authors", None),
    "reviewed_book.publisher": ("doctype", "Reviewed book: publisher", None),
    "reviewed_book.place": ("doctype", "Reviewed book: place", None),
    "reviewed_book.year": ("doctype", "Reviewed book: year", None),
    "reviewed_book.date": ("doctype", "Reviewed book: date", None),
    "original.title": ("doctype", "Translated from: title", None),
    "original.author": ("doctype", "Translated from: author", None),
    "original.lang": ("doctype", "Translated from: language", None),
    "series_part": ("doctype", "Part of a series", None),
}
FORM = {"printed": "page", "reader": "page", "gemini-title": "page", "catalogue": "catalogue",
        "corrected": "corrected", "person": "corrected"}
DATE = {"published": "Published", "received": "Received", "accepted": "Accepted", "revised": "Revised",
        "reviewed": "Reviewed", "online": "Online", "issue": "Issue date", "pub-hijri": "Published (Hijri)"}


def _src_of_actor(by: str | None, default: str) -> str:
    if by and (by.startswith("person:") or by.startswith("rule:")):
        return "corrected"
    return default


def article_fields(path: Path, stem: str) -> dict | None:
    a = P.article(path, stem)
    if a is None:
        return None
    rows: list[dict] = []

    def add(group, label, value, source, by=None, chosen=None, anchor=None, page=None, block=None, wos=None,
            note=None, key=None):
        if value is None or value == "" or value == []:
            return
        rows.append(dict(id=f"f{len(rows) + 1}", key=key or label, group=group, label=label, value=str(value),
                         source=source, by=by, chosen=chosen, anchor=anchor, page=page, block=block, wos=wos,
                         note=note))

    pub, cat, doc, ver = a.get("publication") or {}, a.get("catalogue") or {}, a["document"], a["version"]
    # ---- identity
    add("identity", "Stem (scan file)", stem, "catalogue", by="catalogue:mandumah", key="stem")
    add("identity", "Publication id", a["pub_id"], "derived", wos="UT", key="pub_id")
    add("identity", "Catalogue record (999$c)", cat.get("c999"), "catalogue", by="catalogue:mandumah", key="c999")
    add("identity", "Record type", pub.get("type"), "derived", key="pub_type")
    add("identity", "Level", doc.get("level"), "derived", key="level")
    add("identity", "Part kind", doc.get("part_kind"), "derived", key="part_kind")
    add("identity", "Reading version", ver.get("run"), "derived", note=ver.get("current_reason"), key="run")
    add("identity", "Pages read / expected", f"{ver.get('pages_covered')} / {ver.get('pages_expected')}"
        if ver.get("pages_expected") else None, "derived", key="coverage")
    add("identity", "Pages in the scan", doc.get("scan_pages"), "derived", key="scan_pages")

    # ---- every metadata assertion (title, journal, issue, pages, doc type, about...)
    seen = set()
    for field, rs in sorted(a["metadata"].items(), key=lambda kv: list(META).index(kv[0]) if kv[0] in META else 999):
        g, label, wos = META.get(field, ("doctype" if "." in field else "source", field.replace("_", " "), None))
        for r in rs:
            k = (field, r["form"], r["value"])
            if k in seen and not r["is_chosen"]:
                continue
            seen.add(k)
            src = _src_of_actor(r.get("actor_id"), FORM.get(r["form"], "page"))
            add(g, label, r["value"], src, by=r.get("actor_id") or r.get("rule"), chosen=bool(r["is_chosen"]),
                anchor=r.get("anchor"), wos=wos, note=r.get("rule") or r.get("reason"), key=field)
    # drop the unchosen twin of a chosen value (the same field, form and value loaded twice)
    chosen_k = {(x["key"], x["source"], x["value"]) for x in rows if x["chosen"]}
    rows[:] = [x for x in rows if x["chosen"] or (x["key"], x["source"], x["value"]) not in chosen_k]
    add("title", "Title shown", a["title"].get("shown"), "derived", key="title_shown",
        note="the value the platform shows (printed, else corrected, else catalogue)")
    j = a.get("journal") or {}
    add("source", "Journal id", j.get("id"), "derived", key="journal_id")
    add("source", "Journal country", j.get("country_code"), "catalogue", key="journal_country")
    iss = a.get("issue") or {}
    add("source", "Issue id", iss.get("issue_id"), "derived", key="issue_id")
    if iss.get("is_special"):
        add("source", "Special issue", "yes", "catalogue", key="is_special")
    if iss.get("is_joint"):
        add("source", "Joint issue", "yes", "catalogue", key="is_joint")
    add("source", "Pages (catalogue, as written)", cat.get("pages_raw"), "catalogue", by="catalogue:mandumah",
        key="pages_raw")

    con = P.open_ro(path)
    try:
        pid = a["pub_id"]
        if j.get("id") and P._has_table(con, "journal_issns"):
            for r in P._rows(con, "SELECT issn, issn_raw, kind, valid_check, source FROM journal_issns WHERE journal_id = ?",
                             (j["id"],)):
                add("source", "ISSN", r["issn"] or r["issn_raw"], "catalogue", wos="SN", key="issn",
                    note=f"{r['kind']}{'' if r['valid_check'] else ' · check digit fails'}")
        if j.get("id") and P._has_table(con, "journal_publishers"):
            for r in P._rows(con, "SELECT p.name, p.name_en, p.country_code, jp.source FROM journal_publishers jp "
                                  "JOIN publishers p ON p.publisher_id = jp.publisher_id WHERE jp.journal_id = ?", (j["id"],)):
                add("source", "Publisher", r["name"] or r["name_en"], "catalogue", wos="PU", key="publisher",
                    note=r["source"])
        if pid and P._has_table(con, "publication_dates"):
            for r in P._rows(con, "SELECT d.date_type, d.calendar, d.year, d.month, d.day, d.printed, d.derivation, "
                                  "i.anchor_key FROM publication_dates d LEFT JOIN ink_anchors i ON "
                                  "i.anchor_pk = d.anchor_pk WHERE d.pub_id = ? ORDER BY d.date_type", (pid,)):
                v = r["printed"] or "-".join(str(x) for x in (r["year"], r["month"], r["day"]) if x)
                src = {"read": "page", "catalogue": "catalogue"}.get(r["derivation"], "derived")
                add("source", f"Date: {DATE.get(r['date_type'], r['date_type'])}", f"{v} ({r['calendar']})", src,
                    anchor=r["anchor_key"], key=f"date.{r['date_type']}", note=r["derivation"])
        if pid and P._has_table(con, "publication_languages"):
            for r in P._rows(con, "SELECT lang, role, source, method, share FROM publication_languages WHERE pub_id = ?",
                             (pid,)):
                add("source", f"Language ({r['role']})", r["lang"], "page" if r["source"] == "masters" else "catalogue",
                    key="lang", note=r["method"])
        if pid:
            for r in P._rows(con, "SELECT scheme, value, assigned_by, source FROM external_ids WHERE entity_kind = 'W' "
                                  "AND entity_id = ? ORDER BY scheme", (pid,)):
                if r["scheme"] in ("doi", "001"):
                    add("identity", {"doi": "DOI (registered)", "001": "Catalogue 001"}[r["scheme"]], r["value"],
                        "catalogue", by=r["assigned_by"], key=f"id.{r['scheme']}", wos="DI" if r["scheme"] == "doi" else None)

        # ---- document type and about
        dt = a.get("doc_type") or {}
        add("doctype", "Document type shown", (dt.get("shown") or "").replace("_", " ") or None, "derived",
            wos="DT", key="doc_type_shown", note=f"from the {dt.get('shown_from')}" if dt.get("shown_from") else None)
        for d in dt.get("disagreement") or []:
            add("doctype", "Type: the page and the catalogue disagree", f"page {d['our_value']} · catalogue "
                f"{d['catalogue_value']}", "derived", key="doc_type_disagree", note=d.get("status"))

        # ---- authors and affiliations
        for au in a["authors"]:
            who = f"Author {au['position']}"
            add("authors", f"{who}: name", au["name"], "derived" if au["person_id"] else "page", wos="AU",
                key="author.name", note=f"person {au['person_id']}" if au["person_id"] else None)
            add("authors", f"{who}: role", au.get("role_name") or au.get("role_code"), "catalogue"
                if au.get("c999") else "page", key="author.role")
            add("authors", f"{who}: matched by", au.get("method"), "derived", key="author.method",
                note=f"score {au['score']:.2f}" if au.get("score") else None)
            add("authors", f"{who}: catalogue heading", au.get("cat_name"), "catalogue", by="catalogue:mandumah",
                key="author.catalogue")
            add("authors", f"{who}: authority id", au.get("authority_id"), "catalogue", key="author.authority")
            for x in au.get("ids") or []:
                add("authors", f"{who}: {x['scheme']}", x["value"], "page" if x.get("assigned_by") != "catalogue"
                    else "catalogue", wos="OI" if x["scheme"].lower() == "orcid" else None, key="author.id",
                    note=x.get("source"))
            for b in au["bylines"]:
                add("authors", f"{who}: byline as printed", b["printed"], "page", anchor=b.get("anchor"), wos="AF",
                    key="byline", note="the same person printed again in another script" if b.get("twin") else None)
                add("authors", f"{who}: titles", b.get("titles"), "page", anchor=b.get("anchor"), key="byline.titles")
                add("authors", f"{who}: e-mail", b.get("email"), "page", anchor=b.get("anchor"), wos="EM",
                    key="byline.email")
                if b.get("is_corresponding"):
                    add("authors", f"{who}: corresponding author", "yes", "page", anchor=b.get("anchor"), wos="RP",
                        key="byline.corresponding")
                add("authors", f"{who}: contribution", b.get("contrib_type") if b.get("contrib_type") != "author"
                    else None, "page", key="byline.contrib")
                add("authors", f"{who}: role as printed", b.get("role_phrase"), "page", anchor=b.get("anchor"),
                    key="byline.role_phrase")
                for k, v in (b.get("ids") or {}).items():
                    add("authors", f"{who}: {k}", v, "page", anchor=b.get("anchor"), key="byline.id",
                        wos="OI" if k.lower() == "orcid" else None)
                for f in b["affiliations"]:
                    an = f.get("anchor") or b.get("anchor")
                    add("authors", f"{who}: affiliation as printed", f["printed"], "page", anchor=an, wos="C1",
                        key="aff.printed", note="assembled from its printed parts" if f.get("assembled") else None)
                    for k, lab in (("position_title", "position"), ("org_text", "organisation"),
                                   ("faculty_printed", "faculty"), ("faculty_text", "faculty"),
                                   ("dept_text", "department"), ("city", "city"), ("country_code", "country")):
                        if k == "faculty_text" and f.get("faculty_printed"):
                            continue
                        add("authors", f"{who}: {lab}", f.get(k), "page", anchor=an, key=f"aff.{lab}")
                    for i in f["institutions"]:
                        add("authors", f"{who}: institution", f"{i['name']} ({i['inst_id']})", "derived",
                            key="aff.institution", note=f"{i['level']} · {i['method']}")
        if cat.get("c999"):
            for r in P._rows(con, "SELECT seq, tag, name, latin, role_raw, authority_id, life_note FROM "
                                  "catalogue_contributors WHERE c999 = ? ORDER BY seq", (cat["c999"],)):
                add("authors", f"Catalogue contributor {r['seq'] + 1} ({r['tag']})",
                    " · ".join(x for x in (r["name"], r["latin"]) if x), "catalogue", by="catalogue:mandumah",
                    key="catalogue.contributor", note=" · ".join(str(x) for x in (r["role_raw"], r["authority_id"] and
                                                                                 f"authority {r['authority_id']}",
                                                                                 r["life_note"]) if x) or None)

        # ---- abstracts, keywords, subjects
        if pid and P._has_table(con, "abstracts"):
            for r in P._rows(con, "SELECT x.lang, x.text, x.form, x.block_id, x.version_id, i.anchor_key, i.page FROM "
                                  "abstracts x LEFT JOIN ink_anchors i ON i.anchor_pk = x.anchor_pk WHERE x.pub_id = ? "
                                  "AND (x.version_id IS NULL OR x.version_id = ?) ORDER BY x.form DESC, x.seq",
                             (pid, ver["version_id"])):
                add("abstract", f"Abstract ({r['lang']})", r["text"], FORM.get(r["form"], "page"), wos="AB",
                    anchor=r["anchor_key"] if not r["block_id"] else None, page=r["page"], block=r["block_id"],
                    key="abstract")
        if pid and P._has_table(con, "publication_keywords"):
            for r in P._rows(con, "SELECT k.printed, k.source, t.display, t.lang, i.anchor_key FROM publication_keywords k "
                                  "LEFT JOIN keyword_terms t ON t.term_id = k.term_id LEFT JOIN ink_anchors i ON "
                                  "i.anchor_pk = k.anchor_pk WHERE k.pub_id = ? AND (k.version_id IS NULL OR "
                                  "k.version_id = ?) ORDER BY k.source DESC, k.seq", (pid, ver["version_id"])):
                add("abstract", "Keyword", r["display"] or r["printed"], "page" if r["source"] == "masters" else
                    "catalogue", anchor=r["anchor_key"], wos="DE", key="keyword",
                    note=f"printed «{r['printed']}»" if r["printed"] and r["printed"] != r["display"] else None)
        if cat.get("c999") and P._has_table(con, "record_subjects"):
            for r in P._rows(con, "SELECT t.term_ar, t.term_en, t.scheme FROM record_subjects s JOIN subject_terms t ON "
                                  "t.subject_id = s.subject_id WHERE s.c999 = ? ORDER BY s.seq", (cat["c999"],)):
                add("abstract", f"Subject (MARC {r['scheme']})", r["term_ar"] or r["term_en"], "catalogue",
                    by="catalogue:mandumah", wos="ID", key="subject")

        # ---- page marks: each page's printed folio (with the page number's ink), the running heads (one row per
        # distinct text, with the pages it is on), the other article, ornaments, show-through; scan problems
        regions = []
        if P._has_table(con, "page_regions"):
            from .scan import REGIONS
            regions = P._rows(con, "SELECT r.page, r.role, r.text, r.decided_by, i.anchor_key FROM page_regions r "
                                   "LEFT JOIN ink_anchors i ON i.anchor_pk = r.anchor_pk WHERE r.version_id = ? AND "
                                   f"r.role IN ({','.join('?' * len(REGIONS))}) ORDER BY r.page, r.y",
                              (ver["version_id"], *REGIONS))
        numbers = {}
        for r in regions:
            if r["role"] == "pageNumber":
                numbers.setdefault(r["page"], r)
        for p in a["pages"]:
            nr = numbers.get(p["page"]) or {}
            add("pages", f"Page {p['page']}: printed folio", p.get("printed_folio"), "page", key="page.folio",
                page=p["page"], anchor=nr.get("anchor_key"),
                note=f"printed «{nr['text']}»" if nr.get("text") and nr["text"] != p.get("printed_folio") else None)
        groups: dict = {}
        for r in regions:
            if r["role"] != "pageNumber":
                groups.setdefault((r["role"], (r["text"] or "").strip()), []).append(r)
        for (role, text), rs in sorted(groups.items(), key=lambda kv: kv[1][0]["page"]):
            pgs = sorted({r["page"] for r in rs})
            where = f"page {pgs[0]}" if len(pgs) == 1 else f"{len(pgs)} pages, {pgs[0]}–{pgs[-1]}"
            add("pages", REGIONS[role].capitalize(), text or "(no text)", "page", by=rs[0]["decided_by"],
                anchor=rs[0]["anchor_key"], page=rs[0]["page"], key=f"region.{role}",
                note=f"{where} · kept out of the article's text")
        for m in a.get("page_marks") or []:
            add("pages", f"Page {m['page']}: {m['kind'].replace('-', ' ')}", (m.get("problem") or m.get("text") or "")
                .replace("_", " "), "page", anchor=m.get("anchor"), page=m["page"], key=f"mark.{m['kind']}")

        # ---- body structure (counted)
        roles = Counter(b["role"] for b in a["blocks"])
        add("structure", "Blocks", len(a["blocks"]), "derived", key="n.blocks")
        for r, n in roles.most_common():
            add("structure", f"Blocks: {r}", n, "derived", key=f"n.role.{r}")
        add("structure", "Sections", len(a["sections"]), "derived", key="n.sections")
        depth = max((s["level"] or 0 for s in a["sections"]), default=0)
        add("structure", "Section depth", depth or None, "derived", key="n.depth")
        add("structure", "Notes", len(a["notes"]), "derived", key="n.notes")
        for k, n in Counter(x["kind"] for x in a["notes"]).most_common():
            add("structure", f"Notes: {k}", n, "derived", key=f"n.note.{k}")
        add("structure", "Note calls", len(a["calls"]), "derived", key="n.calls")
        add("structure", "Note calls tied to their note", sum(1 for c in a["calls"] if c["targets"]), "derived",
            key="n.calls_tied")
        for k, n in Counter(f["kind"] for f in a["figures"]).most_common():
            add("structure", f"Figures: {k}", n, "derived", key=f"n.fig.{k}")
        for k, n in Counter(f.get("fig_type") for f in a["figures"] if f.get("fig_type")).most_common():
            add("structure", f"Figure kind: {k}", n, "page", key=f"n.figtype.{k}")
        add("structure", "Table cells", sum(len(f["cells"]) for f in a["figures"]), "derived", key="n.cells")
        add("structure", "Verse lines", sum(len(b.get("verses") or []) for b in a["blocks"]) or None, "derived", key="n.verses")
        if P._has_table(con, "quran_citations"):
            n = con.execute("SELECT count(*), count(DISTINCT sura) FROM quran_citations WHERE version_id = ?",
                            (ver["version_id"],)).fetchone()
            add("structure", "Quran citations (suras)", f"{n[0]} ({n[1]})" if n[0] else None, "derived", key="n.quran")
        add("structure", "Words fixed by the reader", sum(b.get("n_fixes") or 0 for b in a["blocks"]) or None,
            "derived", key="n.fixes")
        add("structure", "Misprints kept as printed", sum(b.get("n_misprints") or 0 for b in a["blocks"]) or None,
            "derived", key="n.misprints")

        # ---- references and citations
        refs = a["citations"]
        add("references", "References (all mentions)", len(refs), "derived", wos="NR", key="n.refs")
        for k, n in Counter(c["kind"] for c in refs).most_common():
            add("references", f"References: {k}", n, "derived", key=f"n.ref.{k}")
        add("references", "On a work card", sum(1 for c in refs if c["card"]), "derived", key="n.ref_card")
        add("references", "Linked to a held article", sum(1 for c in refs if c.get("link")), "derived", key="n.ref_link")
        add("references", "Back references resolved", sum(1 for c in refs if c.get("target")), "derived",
            key="n.backref")
        add("references", "Cited by (articles here)", len(a.get("cited_by") or []), "derived", wos="TC",
            key="n.cited_by")

        # ---- quality
        add("quality", "Flags", len(a["flags"]), "derived", key="n.flags")
        for k, n in Counter(x["kind"] for x in a["flags"]).most_common():
            add("quality", f"Flags: {k}", n, "derived", key=f"n.flag.{k}")
        add("quality", "Judge findings", len(a["judge_findings"]), "derived", key="n.findings")
        add("quality", "Letter corrections", len(a["corrections"]), "corrected", by="rule:lettersfix",
            key="n.corrections")
        if pid and P._has_table(con, "catalogue_reports"):
            for r in P._rows(con, "SELECT r.kind, r.field, r.catalogue_value, r.our_value, r.who_is_right, r.status, "
                                  "r.note, i.anchor_key FROM catalogue_reports r LEFT JOIN ink_anchors i ON "
                                  "i.anchor_pk = r.anchor_pk WHERE r.pub_id = ? ORDER BY r.kind", (pid,)):
                add("quality", f"Catalogue report: {r['kind']}", f"catalogue «{r['catalogue_value'] or '—'}» · page "
                    f"«{r['our_value'] or '—'}»", "derived", anchor=r["anchor_key"], key=f"report.{r['kind']}",
                    note=" · ".join(x for x in (r["who_is_right"] and f"right: {r['who_is_right']}", r["status"],
                                                r["note"]) if x))
    finally:
        con.close()
    order = [g for g, _ in GROUPS]
    rows.sort(key=lambda x: order.index(x["group"]))          # stable: within a group, the order added
    for i, x in enumerate(rows):
        x["ord"] = i
    counts = Counter(x["source"] for x in rows)
    return dict(stem=stem, pub_id=a["pub_id"], groups=[dict(id=g, title=t) for g, t in GROUPS], fields=rows,
                counts=dict(fields=len(rows), with_ink=sum(1 for x in rows if x["anchor"] or x["block"]),
                            **{f"source_{k}": v for k, v in counts.items()}))
