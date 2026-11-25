#!/usr/bin/env python3
"""Export scan-read articles from a Desk release as one JSON file per article (schema "twin-1").

Asked for by the AI-Search session on 2026-11-10 for the owner's twin-journal experiment (same RAG engine, our
Azure + Gemini reading against AI-Search's stored text). Reads the release read-only; writes only under --out.
Private data: the output never goes to git or a public link.

Run:  nice -n 19 ionice -c3 python3 ops/export_twin.py --ids <frozen_doc_ids.txt> --out /home/appuser/data/exports/twin

Left out on purpose: Desk decisions, evidence text, reviewer/actor names, the corrections ledger, judge findings,
e-mail addresses and contacts, and anything about people beyond the printed byline and the reconciled ids.
"""
import argparse, hashlib, json, os, sqlite3, sys
from datetime import datetime

RELEASE = "/home/appuser/data/desk/releases/R20261104T151029.db"
RULE = ("versions.is_current = 1 AND versions.content_in_db = 1 AND versions.complete = 1 AND "
        "runs.model = 'gemini-4-argon' (scan route: Azure words + Gemini 4 Argon structure); ids from the frozen list")
BOX_NOTE = ("boxes are x, y, w, h in page-image pixels of the Azure page at pages.dpi (300), origin top-left, "
            "x to the right, y down; divide by pages.width_px / height_px for page fractions")


def rows(c, sql, *a):
    cur = c.execute(sql, a)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def loads(s):
    if s is None:
        return None
    try:
        return json.loads(s)
    except Exception:
        return s


def article(c, stem):
    v = rows(c, """select v.version_id, v.run, v.complete, v.pages_covered, v.pages_expected, v.jats_sha, v.alto_sha,
                          r.model, d.pub_id
                   from versions v join runs r on r.run = v.run join documents d on d.stem = v.stem
                   where v.stem = ? and v.is_current = 1 and v.content_in_db = 1""", stem)
    if len(v) != 1:
        raise SystemExit(f"{stem}: {len(v)} current versions")
    v = v[0]
    if v["model"] != "gemini-4-argon" or v["complete"] != 1:
        raise SystemExit(f"{stem}: not a complete scan-route version")
    vid, pub = v["version_id"], v["pub_id"]
    p = rows(c, """select p.c999, p.type, p.type_catalogue, p.doc_type, p.doc_type_source, p.title_shown, p.year_shown,
                          j.code, i.volume_raw, i.issue_raw, i.issue_printed, i.year_greg, i.year_hijri, i.date_printed
                   from publications p join journals j on j.journal_id = p.journal_id
                   left join issues i on i.issue_id = p.issue_id where p.pub_id = ?""", pub)[0]
    cat = rows(c, "select page_first, page_last, pages_raw, doi from catalogue_records where c999 = ?", p["c999"])
    cat = cat[0] if cat else {}
    chosen = rows(c, """select field, value, lang, form, source from metadata_assertions
                        where pub_id = ? and is_chosen = 1 order by field, lang, assert_pk""", pub)
    one = lambda f: next((m["value"] for m in chosen if m["field"] == f), None)
    doi = one("doi") or cat.get("doi")
    if not doi:
        x = c.execute("select value from external_ids where scheme = 'doi' and entity_id = ?", (pub,)).fetchone()
        doi = x[0] if x else None

    out = dict(schema="twin-1", doc_id=stem, c999=p["c999"], pub_id=pub, journal_code=p["code"],
               record_type=p["doc_type"], record_type_source=p["doc_type_source"], type_catalogue=p["type_catalogue"],
               year=p["year_shown"],
               issue=dict(volume=p["volume_raw"], issue=p["issue_raw"], issue_printed=p["issue_printed"],
                          year_greg=p["year_greg"], year_hijri=p["year_hijri"], date_printed=p["date_printed"]),
               pages=dict(first=one("fpage") or cat.get("page_first"), last=one("lpage") or cat.get("page_last"),
                          catalogue_raw=cat.get("pages_raw")),
               doi=doi,
               version=dict(version_id=vid, run=v["run"], complete=v["complete"], pages_covered=v["pages_covered"],
                            pages_expected=v["pages_expected"], jats_sha=v["jats_sha"], alto_sha=v["alto_sha"]))
    out["titles"] = [dict(lang=m["lang"], text=m["value"], form=m["form"], field=m["field"], source=m["source"])
                     for m in chosen if m["field"] in ("title", "subtitle", "title_translated")]
    out["abstracts"] = rows(c, """select lang, seq, text, form, block_id from abstracts
                                  where pub_id = ? and (version_id = ? or version_id is null)
                                  order by form desc, lang, seq""", pub, vid)
    out["keywords"] = rows(c, """select t.lang, k.printed, t.display, k.source, k.seq from publication_keywords k
                                 join keyword_terms t on t.term_id = k.term_id
                                 where k.pub_id = ? and (k.version_id = ? or k.version_id is null)
                                 order by k.source, t.lang, k.seq""", pub, vid)
    out["metadata_chosen"] = [dict(field=m["field"], value=m["value"], lang=m["lang"], source=m["source"])
                              for m in chosen]

    # authors: the reconciled authorships, with the printed byline(s) each was tied to
    affs = {}
    for a in rows(c, """select am.mention_pk, am.seq, am.printed, am.org_text org, am.faculty_text faculty,
                               am.dept_text dept, am.city, am.country_code, am.kind,
                               (select l.inst_id from affiliation_links l where l.aff_pk = am.aff_pk
                                order by l.score desc limit 1) inst_id
                        from affiliation_mentions am join byline_mentions b on b.mention_pk = am.mention_pk
                        where b.version_id = ? order by am.mention_pk, am.seq""", vid):
        affs.setdefault(a.pop("mention_pk"), []).append(a)
    bylines = rows(c, """select mention_pk, byline_pos, position, printed, titles, name_text, script, contrib_type,
                                is_corresponding, block_id, twin_of_pk from byline_mentions
                         where version_id = ? order by byline_pos, mention_pk""", vid)
    by_pk = {b["mention_pk"]: b for b in bylines}
    authors, used = [], set()
    for a in rows(c, """select a.authorship_pk, a.position, a.role_code, a.is_corresponding, a.person_id, a.method,
                               pe.preferred_name_ar name_ar, pe.preferred_name_lat name_lat,
                               (select pa.authority_id from person_authorities pa where pa.person_id = a.person_id
                                order by pa.n_records desc limit 1) authority_id
                        from authorships a left join persons pe on pe.person_id = a.person_id
                        where a.pub_id = ? order by a.position, a.authorship_pk""", pub):
        ms = [r[0] for r in c.execute("select mention_pk from authorship_mentions where authorship_pk = ? order by 1",
                                      (a.pop("authorship_pk"),)) if r[0] in by_pk]
        used.update(ms)
        a["printed"] = [by_pk[m]["printed"] for m in ms]
        a["byline_block_ids"] = [by_pk[m]["block_id"] for m in ms]
        a["affiliations"] = [x for m in ms for x in affs.get(m, [])]
        a["match_method"] = a.pop("method")
        authors.append(a)
    out["authors"] = authors
    out["bylines_unlinked"] = [dict(byline_pos=b["byline_pos"], printed=b["printed"], name_text=b["name_text"],
                                    script=b["script"], contrib_type=b["contrib_type"], block_id=b["block_id"],
                                    is_twin_of_another_script=b["twin_of_pk"] is not None,
                                    affiliations=affs.get(b["mention_pk"], []))
                               for b in bylines if b["mention_pk"] not in used]

    out["sections"] = rows(c, """select section_id, parent_id, level, ord, heading, heading_block_id from sections
                                 where version_id = ? order by ord""", vid)
    boxes = {}
    for b in rows(c, "select block_id, part, page, x, y, w, h from block_parts where version_id = ? order by block_id, part", vid):
        boxes.setdefault(b.pop("block_id"), []).append(dict(page=b["page"], x=b["x"], y=b["y"], w=b["w"], h=b["h"]))
    blocks = rows(c, """select block_id, ord, role, section_id, lang, text, page, last_page, note_id, figure_id,
                               n_flags, n_fixes, n_misprints, trust from blocks where version_id = ? order by ord""", vid)
    for b in blocks:
        b["boxes"] = boxes.get(b["block_id"], [])
    out["blocks"] = blocks
    out["box_units"] = BOX_NOTE
    out["page_list"] = rows(c, """select page, width_px, height_px, image_w, image_h, dpi, angle, printed_folio,
                                         page_image_key from pages where stem = ? order by page""", stem)

    calls = {}
    for k in rows(c, """select t.note_id, n.block_id, n.char_offset, n.call_text from note_call_targets t
                        join note_calls n on n.version_id = t.version_id and n.call_seq = t.call_seq
                        where t.version_id = ? order by t.call_seq""", vid):
        calls.setdefault(k.pop("note_id"), []).append(k)
    notes = rows(c, "select note_id, kind, label, page, first_block_id, text from notes where version_id = ? order by ord", vid)
    for n in notes:
        n["calls"] = calls.get(n["note_id"], [])
    out["notes"] = notes

    cells = {}
    for k in rows(c, """select figure_id, row, col, rowspan, colspan, is_header, text, block_id from table_cells
                        where version_id = ? order by figure_id, row, col""", vid):
        cells.setdefault(k.pop("figure_id"), []).append(k)
    figs = []
    for f in rows(c, """select figure_id, kind, fig_type, label, caption, caption_block_id, page, x, y, w, h, tex, mathml
                        from figures where version_id = ? order by page, y, figure_id""", vid):
        f["box"] = dict(page=f["page"], x=f.pop("x"), y=f.pop("y"), w=f.pop("w"), h=f.pop("h"))
        f["cells"] = cells.get(f["figure_id"], [])
        figs.append(f)
    out["figures"] = figs

    refs = rows(c, """select m.mention_pk, m.kind, m.container_kind, m.container_id, m.reading_ord, m.marker,
                             coalesce(m.printed_fixed, m.printed) printed, m.parsed, m.page, m.block_id,
                             m.full_mention_pk, m.trust,
                             (select w.cited_work_id from cited_work_members cm join cited_works w
                                on w.cited_work_pk = cm.cited_work_pk
                              where cm.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk) limit 1) cited_work_id,
                             (select cm.cited_work_pk from cited_work_members cm
                              where cm.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk) limit 1) cw_pk
                      from citation_mentions m where m.version_id = ? order by m.reading_ord, m.mention_pk""", vid)
    for r in refs:
        r["parsed"] = loads(r["parsed"])
        cw = r.pop("cw_pk")
        r["link"] = None
        if cw is not None:
            l = c.execute("""select l.status, l.target_pub_id, p.c999,
                                    (select group_concat(d.stem, ' ') from documents d where d.pub_id = l.target_pub_id)
                             from citation_links l left join publications p on p.pub_id = l.target_pub_id
                             where l.cited_work_pk = ? and l.status = 'accepted' and l.target_kind = 'publication'
                             order by l.best desc, l.score desc limit 1""", (cw,)).fetchone()
            if l:
                r["link"] = dict(status=l[0], target_pub_id=l[1], target_c999=l[2], target_stem=l[3])
    out["references"] = refs

    flags = rows(c, "select kind, severity, page, block_id from flags where version_id = ? order by page, flag_id", vid)
    out["flags_summary"] = {s: sum(1 for f in flags if f["severity"] == s) for s in ("high", "medium", "low")}
    out["flags"] = flags
    return out, vid, pub, p["c999"], p["code"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--release", default=RELEASE)
    a = ap.parse_args()
    if os.path.exists(os.path.join(a.out, "manifest.json")):
        raise SystemExit("manifest.json already exists: this export is frozen; write a new folder instead")
    ids = [l.strip() for l in open(a.ids) if l.strip()]
    c = sqlite3.connect(f"file:{a.release}?mode=ro", uri=True)
    arts, counts = [], {}
    for n, stem in enumerate(ids, 1):
        d, vid, pub, c999, code = article(c, stem)
        if not stem.startswith(code + "-"):
            raise SystemExit(f"{stem}: journal code {code} does not match the id")
        os.makedirs(os.path.join(a.out, code), exist_ok=True)
        raw = json.dumps(d, ensure_ascii=False, indent=1, sort_keys=False).encode("utf-8")
        with open(os.path.join(a.out, code, stem + ".json"), "wb") as f:
            f.write(raw)
        arts.append(dict(doc_id=stem, code=code, c999=c999, pub_id=pub, version_id=vid,
                         sha256=hashlib.sha256(raw).hexdigest()))
        for k in ("blocks", "sections", "notes", "figures", "references", "authors", "page_list", "flags"):
            counts[k] = counts.get(k, 0) + len(d[k])
        counts["tables"] = counts.get("tables", 0) + sum(1 for f in d["figures"] if f["kind"] == "table")
        counts["table_cells"] = counts.get("table_cells", 0) + sum(len(f["cells"]) for f in d["figures"])
        counts["references_full"] = counts.get("references_full", 0) + sum(1 for r in d["references"] if r["kind"] == "full")
        counts["references_linked"] = counts.get("references_linked", 0) + sum(1 for r in d["references"] if r["link"])
        counts["articles_" + code] = counts.get("articles_" + code, 0) + 1
        if n % 40 == 0:
            print(n, "of", len(ids), file=sys.stderr, flush=True)
    counts["articles"] = len(arts)
    man = dict(schema="twin-1", release=os.path.basename(a.release).replace(".db", ""),
               built=datetime.now().astimezone().isoformat(timespec="seconds"), rule=RULE, box_units=BOX_NOTE,
               ids_file_sha256=hashlib.sha256(open(a.ids, "rb").read()).hexdigest(), articles=arts, counts=counts)
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, ensure_ascii=False, indent=1)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
