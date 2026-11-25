#!/usr/bin/env python3
"""Experiment 97: copy the pipeline's output for the 60 exam articles out of the release database, once, read-only.

The scorer and the R1/R2 scripts then work from out/cache/<stem>.json and never touch the database again (the box
also serves a live database; a few full-table scans here instead of one per scoring run).
Run:  nice -n 19 ionice -c3 python3 extract97.py        (skips articles already cached)
"""
import json, os, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
DB = "/home/appuser/data/desk/releases/R20261104T151029.db"
OUT = f"{HERE}/out/cache"
os.makedirs(OUT, exist_ok=True)
L = json.load(open(f"{HERE}/LOCKED_EVAL.json"))
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
c.row_factory = sqlite3.Row


def rows(sql, args=()):
    return [dict(r) for r in c.execute(sql, args)]


if sys.argv[1:] == ["--refresh-affiliations"]:      # add affiliation columns to caches made before they were copied
    for a in L["articles"]:
        p = f"{OUT}/{a['stem']}.json"
        d = json.load(open(p))
        mp = [b["mention_pk"] for b in d["bylines"]]
        d["affiliations"] = rows(f"""select aff_pk, mention_pk, seq, printed, position_title, org_text, faculty_printed, dept_text, lang
                                     from affiliation_mentions where mention_pk in ({','.join('?' * len(mp))})""", mp) if mp else []
        json.dump(d, open(p + ".tmp", "w"), ensure_ascii=False)
        os.replace(p + ".tmp", p)
    sys.exit("affiliations refreshed")
todo = [a for a in L["articles"] if not os.path.exists(f"{OUT}/{a['stem']}.json")]
if not todo:
    sys.exit("all cached")
pub = {a["stem"]: c.execute("select pub_id from documents where stem = ?", (a["stem"],)).fetchone()[0] for a in todo}
pubs = list(pub.values())
q = ",".join("?" * len(pubs))
# tables without a usable index on pub_id: one scan each for all articles
abstracts = rows(f"select * from abstracts where pub_id in ({q})", pubs)
dates = rows(f"select * from publication_dates where pub_id in ({q})", pubs)
kws = rows(f"""select pk.pub_id, pk.seq, pk.printed, pk.source, pk.version_id, kt.display, kt.lang from publication_keywords pk
               left join keyword_terms kt on kt.term_id = pk.term_id where pk.pub_id in ({q})""", pubs)
for a in todo:
    s, v, p = a["stem"], a["version_id"], pub[a["stem"]]
    d = dict(stem=s, version_id=v, pub_id=p)
    d["pages"] = rows("select * from pages where stem = ? order by page", (s,))
    d["azure_lines"] = rows("select page, line_no, x, y, w, h, n_words, wc_min, text from azure_lines where stem = ? order by page, line_no", (s,))
    d["line_map"] = rows("select alto_line_id, page, azure_line_no, block_id, region_id, x, y, w, h, map_method from line_map where version_id = ?", (v,))
    d["blocks"] = rows("""select block_id, ord, page, last_page, role, section_id, note_id, figure_id, lang, text, role_source, text_source
                          from blocks where version_id = ? order by ord""", (v,))
    d["block_parts"] = rows("select block_id, part, page, x, y, w, h, first_line_id, last_line_id from block_parts where version_id = ?", (v,))
    d["page_regions"] = rows("select region_id, page, role, text, x, y, w, h, decided_by from page_regions where version_id = ?", (v,))
    d["sections"] = rows("select * from sections where version_id = ?", (v,))
    d["notes"] = rows("select note_id, kind, label, label_int, ord, page, first_block_id, text, written_by from notes where version_id = ?", (v,))
    d["note_calls"] = rows("select call_seq, call_text, block_id, char_offset, status from note_calls where version_id = ?", (v,))
    d["note_call_targets"] = rows("select call_seq, note_id from note_call_targets where version_id = ?", (v,))
    d["figures"] = rows("""select figure_id, kind, page, x, y, w, h, caption_block_id, anchor_block_id, label, caption, fig_type, specific_use
                           from figures where version_id = ?""", (v,))
    d["table_cells"] = rows("select figure_id, row, col, rowspan, colspan, is_header, block_id, text from table_cells where version_id = ?", (v,))
    d["citation_mentions"] = rows("""select mention_id, container_kind, container_id, reading_ord, seq_in_container, kind, marker, printed,
                                     printed_fixed, parsed, cited_volume, cited_pages, page, block_id from citation_mentions where version_id = ?
                                     order by reading_ord""", (v,))
    d["metadata"] = rows("select field, value, lang, script, form, source, version_id, block_id, is_chosen from metadata_assertions where pub_id = ?", (p,))
    d["abstracts"] = [r for r in abstracts if r["pub_id"] == p]
    d["dates"] = [r for r in dates if r["pub_id"] == p]
    d["keywords"] = [r for r in kws if r["pub_id"] == p]
    d["bylines"] = rows("select mention_pk, byline_pos, printed, titles, name_text, script, block_id, position from byline_mentions where version_id = ? order by byline_pos", (v,))
    mp = [b["mention_pk"] for b in d["bylines"]]
    d["affiliations"] = rows(f"select aff_pk, mention_pk, seq, printed, position_title, org_text, faculty_printed, dept_text, lang from affiliation_mentions where mention_pk in ({','.join('?' * len(mp))})", mp) if mp else []
    json.dump(d, open(f"{OUT}/{s}.json.tmp", "w"), ensure_ascii=False)
    os.replace(f"{OUT}/{s}.json.tmp", f"{OUT}/{s}.json")
    print(s, len(d["blocks"]), "blocks", flush=True)
