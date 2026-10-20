"""Experiment 47: load one run's masters into the platform v2 database /home/yassine/data/platform_v2/platform_v2.db
(schema47.sql), from the same sources as experiment 46: the masters (JATS + ALTO + sidecars) of
experiments/43_rehearsal/out/<run>/masters, the run's flags / patches / judge answers / raw chunk files, each
document's Azure JSON (the ink: the same for every run), and marc.db (read only).

    .venv/bin/python experiments/47_platform_v2/load47.py --run v33_300
    .venv/bin/python experiments/47_platform_v2/load47.py --run v2_55
    .venv/bin/python experiments/47_platform_v2/load47.py --run v33_300_judged --stem 0368-000-013-009
    .venv/bin/python experiments/47_platform_v2/load47.py --run v33_300_final
    .venv/bin/python experiments/47_platform_v2/load47.py --run v33_300b            # an exam: loads beside, never shown
    .venv/bin/python experiments/47_platform_v2/link47.py                           # then link

Every run is its own reading ("version") of a document, kept side by side; one version per document is shown
(is_current), chosen by person > complete > purpose (final > judged > base > exam > sample) > newest, with the reason.
Idempotent and incremental: a version whose inputs (JATS, ALTO, D33 and patches sidecars, stamp) have the same sha is
skipped; a new or changed one replaces only its own rows (same version_id). Run-level files (flags, patches, judge
answers, raw chunk costs) are re-read on every call and replaced for that run only. Sources are never edited."""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import biblio47  # noqa: E402
import ink47  # noqa: E402
import parse47  # noqa: E402
from common47 import (DB, E43, OUT43, connect, country_iso, fill_pk, fold, insert, jdump, marc, now, sha_file, sha_files,  # noqa: E402
                      spk, stemmed, AYAT, SURAS)

PURPOSE = {"final": 1, "judged": 2, "base": 3, "exam": 4, "sample": 5, "replay": 6}
VERSION_TABLES = ["line_map", "sections", "block_parts", "blocks", "page_regions", "note_call_targets", "note_calls",
                  "notes", "table_cells", "figures", "verse_lines", "text_corrections", "quran_citations", "flags",
                  "abstracts", "publication_keywords"]
REGION_STATIC = None


def run_kind(run: str) -> str:
    if re.search(r"300b", run):
        return "exam"
    if run.endswith("_final"):
        return "final"
    if "_judged" in run:
        return "judged"
    if run.startswith("v2_"):
        return "sample"
    if "replay" in run:
        return "replay"
    return "base"


def parent_of(run: str) -> str | None:
    p = re.sub(r"_(judged|fixed|patched|final)\w*$", "", run)
    return p if p != run else None


# ------------------------------------------------------------------ static rows
def static(con):
    insert(con, "storage_roots", [
        dict(root_id="local-43", kind="local", base=str(OUT43), note="experiment 43 run folders (masters, flags, "
             "patches, raw chunks, judge answers); keys below are relative to it"),
        dict(root_id="local-repo", kind="local", base=str(E43.parents[1]), note="the repository (Azure JSON copies "
             "of the sampled documents sit in several experiments' out/ folders)"),
        dict(root_id="local-pages", kind="local", base=str(OUT43 / "pages"), note="page images <stem>_pNNN.jpg "
             "(300 of the 354 documents)"),
        dict(root_id="s3-source-docs", kind="s3", base="s3://mandumah-source-docs", note="<id>/<id>.pdf | .json | "
             ".html | .gemini.title.json; legacy/<id>/<id>.pdf (experiment 44)"),
        dict(root_id="s3-qdrant", kind="s3", base="s3://mandumah-qdrant-backups", note="Qdrant snapshots and MySQL "
             "dumps (ai_search_feedback); not read by this build")], "INSERT OR IGNORE")
    insert(con, "actors", [
        dict(actor_id="agent:load47", kind="agent", name="experiments/47_platform_v2/load47.py", note=None),
        dict(actor_id="agent:link47", kind="agent", name="experiments/47_platform_v2/link47.py", note=None),
        dict(actor_id="agent:link46", kind="agent", name="experiments/46_platform_db/link46.py", note="v46 links"),
        dict(actor_id="agent:agent-46", kind="agent", name="experiment 46 hand checker", note="link_checks"),
        dict(actor_id="agent:judge-verdicts43", kind="agent", name="experiment 43 agent's look at judge findings",
             note="judge_verdicts43.json"),
        dict(actor_id="person:owner", kind="person", name="the owner", note="gold / hand checks"),
        dict(actor_id="model:gemini-4-argon", kind="model", name="gemini-4-argon", note="the reader (masters)"),
        dict(actor_id="model:gemini-3.8-flash", kind="model", name="gemini-3.8-flash", note="judge"),
        dict(actor_id="rule:d33", kind="rule", name="docs/decisions.md D33", note="metadata corrected, printed kept"),
        dict(actor_id="catalogue:mandumah", kind="agent", name="Mandumah catalogue (marc.db)", note=None),
        dict(actor_id="model:gemini-front-page", kind="model", name="Gemini front-page reader (S3 gemini.title.json)",
             note="the reading carried in each document's Azure JSON under gemini_front_page; the model version is "
                  "not recorded there")],
        "INSERT OR IGNORE")
    insert(con, "role_codes", [
        dict(code=c, name_ar=a, name_en=e, counts_as_author=k) for c, a, e, k in (
            ("author", "مؤلف", "author", 1), ("coauthor", "مؤلف مشارك", "co-author", 1),
            ("translator", "مترجم", "translator", 0), ("reviewer", "عارض", "reviewer of a book", 1),
            ("editor", "محرر", "editor", 0), ("supervisor", "مشرف", "thesis supervisor", 0),
            ("interviewer", "محاور", "interviewer", 1), ("compiler", "معد", "compiler", 1),
            ("original-author", "صاحب النص", "author of the edited text", 0),
            ("editor-of-text", "محقق", "editor of a text (tahqiq)", 1),
            ("corporate", "هيئة", "corporate body", 1))], "INSERT OR IGNORE")
    insert(con, "languages", [
        dict(code=c, code1=c1, code2t=c2, name_ar=a, name_en=e) for c, c1, c2, a, e in (
            ("ara", "ar", "ara", "العربية", "Arabic"), ("eng", "en", "eng", "الإنجليزية", "English"),
            ("fre", "fr", "fra", "الفرنسية", "French"), ("ger", "de", "deu", "الألمانية", "German"),
            ("spa", "es", "spa", "الإسبانية", "Spanish"), ("ita", "it", "ita", "الإيطالية", "Italian"),
            ("per", "fa", "fas", "الفارسية", "Persian"), ("tur", "tr", "tur", "التركية", "Turkish"),
            ("urd", "ur", "urd", "الأردية", "Urdu"), ("heb", "he", "heb", "العبرية", "Hebrew"),
            ("rus", "ru", "rus", "الروسية", "Russian"), ("und", None, "und", "غير محددة", "undetermined"))],
        "INSERT OR IGNORE")
    if not con.execute("SELECT 1 FROM quran_ayat LIMIT 1").fetchone():
        insert(con, "quran_ayat", [dict(sura=s, aya=a, text_uthmani=None, text_simple=None, text_key=None,
                                        sura_name_ar=SURAS[s - 1],
                                        source="structure only: 114 suras, 6,236 ayat (Hafs numbering); text not "
                                               "loaded until the owner picks a reference text and its licence",
                                        licence=None)
                                   for s in range(1, 115) for a in range(1, AYAT[s - 1] + 1)])
    m = marc()
    meta = {r["k"]: r["v"] for r in m.execute("SELECT k, v FROM meta")}
    insert(con, "catalogue_exports", [dict(export_id="marc-2026-10-19", file=meta.get("source"),
                                           sha256=meta.get("source_sha256"), records=int(meta.get("records") or 0),
                                           built=meta.get("built"), latest_995d=meta.get("latest_995d_added"))],
           "INSERT OR IGNORE")


EXPORT = "marc-2026-10-19"


# ------------------------------------------------------------------ helpers
_uid = [None]


def next_uid(con) -> int:
    if _uid[0] is None:
        hw = [r[0] or 0 for r in con.execute("SELECT max(uid) FROM blocks UNION ALL SELECT max(uid) FROM search_units")]
        for (j,) in con.execute("SELECT rows_by_table FROM load_events WHERE rows_by_table IS NOT NULL"):
            try:
                hw.append(int(json.loads(j).get("_uid_hwm") or 0))
            except Exception:
                pass
        _uid[0] = max(hw + [0])
    _uid[0] += 1
    return _uid[0]


def anchor_pks(con, anchors: dict) -> dict:
    """Insert the anchors (run-independent, never deleted) and return anchor_key -> anchor_pk."""
    rows = list(anchors.values())
    # word-exact anchors (from Azure's own words) replace a line-union one a flag may have made for the same key, so
    # the box does not depend on which run or file came first
    rows = fill_pk("ink_anchors", [dict(a) for a in rows])
    if rows:
        cols = list(rows[0])
        # the same key from another run or file: the box is Azure's (identical); the method kept is the most precise
        con.executemany(f"""INSERT INTO ink_anchors ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})
            ON CONFLICT(anchor_key) DO UPDATE SET x = excluded.x, y = excluded.y, w = excluded.w, h = excluded.h,
            text_azure = excluded.text_azure, wc_min = excluded.wc_min,
            method = CASE WHEN instr('words line box page', excluded.method) < instr('words line box page',
                     ink_anchors.method) THEN excluded.method ELSE ink_anchors.method END""",
                        [tuple(r.get(c) for c in cols) for r in rows])
    out = {}
    keys = [a["anchor_key"] for a in rows]
    for i in range(0, len(keys), 500):
        ch = keys[i:i + 500]
        for k, pk in con.execute(f"SELECT anchor_key, anchor_pk FROM ink_anchors WHERE anchor_key IN "
                                 f"({','.join('?' * len(ch))})", ch):
            out[k] = pk
    return out


def pages_text(pages: list[int]) -> str:
    pages = sorted(set(pages))
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(f"{pages[i]}-{pages[j]}" if j > i else str(pages[i]))
        i = j + 1
    return ",".join(out)


# ------------------------------------------------------------------ the document (ink) layer
def ensure_document(con, stem: str, az: dict, azpath: Path, load_id: int):
    sha = sha_file(azpath)
    d = con.execute("SELECT azure_sha FROM documents WHERE stem = ?", (stem,)).fetchone()
    if d and d["azure_sha"] == sha:
        return
    pdf = azpath.with_suffix(".pdf")
    rel = str(azpath.relative_to(E43.parents[1])) if str(azpath).startswith(str(E43.parents[1])) else str(azpath)
    con.execute("""INSERT INTO documents (stem, level, in_main_bucket, legacy_only, has_azure_json, scan_pages, pdf_sha,
                   azure_sha, root_id, scan_key, azure_key, qdrant_doc_id, first_load, part_label, part_kind, part_seq)
                   VALUES (?, 'azure', 1, 0, 1, ?, ?, ?, 'local-repo', ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(stem) DO UPDATE SET scan_pages = excluded.scan_pages, azure_sha = excluded.azure_sha,
                   azure_key = excluded.azure_key""",
                (stem, len(az["pages"]), sha_file(pdf) if pdf.exists() else None, sha,
                 f"s3://mandumah-source-docs/{stem}/{stem}.pdf", rel, stem, load_id,
                 *thesis_part(stem)))
    con.execute("DELETE FROM azure_lines WHERE stem = ?", (stem,))
    rows, lines = [], []
    for p, P in sorted(az["pages"].items()):
        img = OUT43 / "pages" / f"{stem}_p{p:03d}.jpg"
        iw = ih = None
        if img.exists():
            iw, ih = jpeg_size(img)
        rows.append(dict(stem=stem, page=p, width_px=round(P["width"], 1), height_px=round(P["height"], 1),
                         image_w=iw, image_h=ih, dpi=300, page_image_key=img.name if img.exists() else None,
                         n_words=P["n_words"], wc_mean=round(P["wc_mean"], 4) if P["wc_mean"] else None,
                         wc_min=P["wc_min"], n_low_wc=P["n_low"], angle=P["angle"]))
        for L in P["lines"]:
            lines.append(dict(stem=stem, page=p, line_no=L["line_no"], x=round(L["x"], 1), y=round(L["y"], 1),
                              w=round(L["w"], 1), h=round(L["h"], 1), first_word=L["first"], last_word=L["last"],
                              n_words=L["n_words"], wc_min=L["wc_min"], text=L["text"]))
    insert(con, "pages", rows)
    insert(con, "azure_lines", lines)


def jpeg_size(path: Path):
    """(width, height) from a JPEG's SOF marker (no imaging library needed)."""
    import struct
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            return None, None
        while True:
            b = f.read(1)
            while b and b != b"\xff":
                b = f.read(1)
            while b == b"\xff":
                b = f.read(1)
            if not b:
                return None, None
            m = b[0]
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                continue
            ln_ = struct.unpack(">H", f.read(2))[0]
            if 0xC0 <= m <= 0xCF and m not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">xHH", f.read(5))
                return w, h
            f.seek(ln_ - 2, 1)


def thesis_part(stem: str):
    m = re.match(r"^98\d\d-\d+-\d+-\d+-(\w+)$", stem)
    if not m:
        return (None, "article", None)
    lab = m.group(1)
    kind = {"T": "title-page", "A": "abstract", "C": "contents", "F": "conclusion", "R": "references",
            "O": "other"}.get(lab, "chapter")
    return (lab, kind, int(lab) if lab.isdigit() else None)


# ------------------------------------------------------------------ one version
def delete_version(con, vid: int):
    for (uid, f, s) in con.execute("SELECT uid, folded, stemmed FROM search_units WHERE version_id = ?", (vid,)).fetchall():
        con.execute("INSERT INTO search_fts(search_fts, rowid, folded, stemmed) VALUES ('delete', ?, ?, ?)", (uid, f, s))
    con.execute("DELETE FROM search_units WHERE version_id = ?", (vid,))
    mp = "SELECT mention_pk FROM byline_mentions WHERE version_id = ?"
    con.execute(f"DELETE FROM affiliation_links WHERE aff_pk IN (SELECT aff_pk FROM affiliation_mentions WHERE "
                f"mention_pk IN ({mp}))", (vid,))
    con.execute(f"DELETE FROM affiliation_mentions WHERE mention_pk IN ({mp})", (vid,))
    con.execute(f"DELETE FROM authorship_mentions WHERE mention_pk IN ({mp})", (vid,))
    con.execute("DELETE FROM byline_mentions WHERE version_id = ?", (vid,))
    cp = "SELECT mention_pk FROM citation_mentions WHERE version_id = ?"
    con.execute(f"DELETE FROM cited_work_members WHERE full_mention_pk IN ({cp})", (vid,))
    con.execute(f"UPDATE citation_links SET via_mention_pk = NULL WHERE via_mention_pk IN ({cp})", (vid,))
    con.execute("DELETE FROM citation_mentions WHERE version_id = ?", (vid,))
    for t in VERSION_TABLES:
        con.execute(f"DELETE FROM {t} WHERE version_id = ?", (vid,))
    con.execute("DELETE FROM metadata_assertions WHERE version_id = ?", (vid,))
    con.execute("DELETE FROM anchor_links WHERE owner_key LIKE ?", (f"{vid}:%",))
    con.execute("DELETE FROM link_run_versions WHERE version_id = ?", (vid,))


def write_version(con, V: dict, vid: int, vkey: str) -> dict:
    A = anchor_pks(con, V["anchors"])

    def ap(k):
        return A.get(k) if k else None

    def strip(rows, extra=None):
        out = []
        for r in rows:
            d = {k: v for k, v in r.items() if not k.startswith("_") and k != "anchor_key"}
            d["version_id"] = vid
            if "anchor_key" in r:
                d["anchor_pk"] = ap(r["anchor_key"])
            if extra:
                d.update(extra)
            out.append(d)
        return out

    n = {}
    blocks = []
    for b in V["blocks"]:
        d = {k: v for k, v in b.items() if not k.startswith("_") and k != "anchor_key"}
        d.update(version_id=vid, uid=spk("uid", vkey, "block", b["block_id"]), anchor_pk=ap(b["anchor_key"]), n_flags=0)
        blocks.append(d)
    n["blocks"] = insert(con, "blocks", blocks)
    n["block_parts"] = insert(con, "block_parts", strip(V["block_parts"]))
    n["page_regions"] = insert(con, "page_regions", strip(V["page_regions"]))
    n["line_map"] = insert(con, "line_map", strip(V["line_map"]))
    n["sections"] = insert(con, "sections", strip(V["sections"]))
    n["notes"] = insert(con, "notes", strip(V["notes"]))
    n["note_calls"] = insert(con, "note_calls", strip(V["note_calls"]))
    n["note_call_targets"] = insert(con, "note_call_targets", strip(V["note_call_targets"]))
    n["figures"] = insert(con, "figures", strip(V["figures"]))
    n["table_cells"] = insert(con, "table_cells", strip(V["table_cells"]))
    n["verse_lines"] = insert(con, "verse_lines", strip(V["verse_lines"]))
    n["text_corrections"] = insert(con, "text_corrections", strip(V["text_corrections"]))
    # bylines and their affiliations
    for m in V["byline_mentions"]:
        d = {k: v for k, v in m.items() if not k.startswith("_") and k != "anchor_key"}
        d.update(version_id=vid, anchor_pk=ap(m["anchor_key"]))
        fill_pk("byline_mentions", [d])
        insert(con, "byline_mentions", [d], "INSERT")
        m["_pk"] = d["mention_pk"]
    pos_pk = {m["byline_pos"]: m["_pk"] for m in V["byline_mentions"]}
    import inst46
    for a in V["affiliations"]:
        mpk = pos_pk.get(a["author_seq"])
        if not mpk:
            continue
        printed = a["printed"] or ""
        rest = inst46.strip_role(printed)
        pos_title = printed[:len(printed) - len(rest)].strip(" ،,") if rest != printed else None
        has_inst = bool(a["orgname"] or a["dept"] or re.search(
            r"جامع|كلي|قسم|معهد|مركز|وزار|univ|coll|facult|depart|institut|ministry|centre|center", printed, re.I))
        kind = "institution" if has_inst else ("place-only" if (a["city"] or a["country"]) else "position-only")
        insert(con, "affiliation_mentions", [dict(mention_pk=mpk, seq=a["seq"] + 1, printed=printed,
                                                  position_title=pos_title, org_text=a["orgname"], faculty_text=None,
                                                  dept_text=a["dept"], city=a["city"], country_printed=a["country"],
                                                  country_code=country_iso(a["country"]), kind=kind)], "INSERT")
    n["byline_mentions"] = len(V["byline_mentions"])
    # citation mentions (unresolved here; link47 resolves back references and builds the cited works)
    mrows = []
    for m in V["citation_mentions"]:
        mrows.append(dict(mention_id=m["mention_id"], version_id=vid, container_kind=m["container_kind"],
                          container_id=m["container_id"], reading_ord=m["reading_ord"],
                          seq_in_container=m["seq_in_container"], kind=m["kind"], marker=m["marker"],
                          printed=m["printed"], printed_fixed=m["printed_fixed"], parsed=jdump(m["parsed"]),
                          cited_volume=m["cited_volume"], cited_pages=m["cited_pages"], page=m["page"],
                          block_id=m["block_id"], anchor_pk=ap(m["anchor_key"]),
                          resolve_evidence=jdump(dict(hint=m["_hint"])) if m["_hint"] else None))
    n["citation_mentions"] = insert(con, "citation_mentions", mrows)
    mpk = {r["mention_id"]: r["mention_pk"] for r in con.execute(
        "SELECT mention_id, mention_pk FROM citation_mentions WHERE version_id = ?", (vid,))}
    # Quran: a note reference is the citation mention of kind quran in the same block; a quotation stands alone
    qrows = []
    qm = defaultdict(list)
    for m in V["citation_mentions"]:
        if m["kind"] == "quran":
            qm[m["block_id"]].append(m)
    for q in V["quran"]:
        mention = None
        if q["source_kind"] == "note-ref":
            mention = next((m for m in qm.get(q["block_id"], []) if q["printed_ref"] and
                            q["printed_ref"] in (m["printed"] or "")), None)
        d = {k: v for k, v in q.items() if not k.startswith("_") and k != "anchor_key"}
        d.update(version_id=vid, anchor_pk=ap(q["anchor_key"]),
                 mention_pk=mpk.get(mention["mention_id"]) if mention else None)
        qrows.append(d)
    n["quran_citations"] = insert(con, "quran_citations", qrows)
    # extra anchors (a block or a citation running on to the next page)
    insert(con, "anchor_links", [dict(anchor_pk=ap(x["anchor_key"]), owner_kind=x["owner_kind"],
                                      owner_key=f"{vid}:{x['owner_key']}", role=x["role"], seq=x["seq"])
                                 for x in V["extra_anchors"] if ap(x["anchor_key"])], "INSERT OR IGNORE")
    return n


def load_versions(con, run: str, mdir: Path, stems: list, force: bool, load_id: int, azp: dict) -> tuple:
    kind = run_kind(run)
    done, skipped, touched, counts = 0, 0, [], Counter()
    t0 = time.time()
    checks = Counter()
    for i, stem in enumerate(stems):
        files = [mdir / f"{stem}.{x}" for x in ("jats.xml", "alto.xml", "metachanges.json", "patches.json",
                                                "stamp.json")]
        sha = sha_files(files)
        old = con.execute("SELECT version_id, inputs_sha FROM versions WHERE stem = ? AND run = ?", (stem, run)).fetchone()
        if old and old["inputs_sha"] == sha and not force:
            skipped += 1
            continue
        if stem not in azp:
            print(f"  no Azure JSON for {stem}: skipped", flush=True)
            continue
        az = ink47.read_azure(azp[stem])
        ensure_document(con, stem, az, azp[stem], load_id)
        V = parse47.parse_version(mdir, stem, run, az)
        stamp = {}
        if (mdir / f"{stem}.stamp.json").exists():
            stamp = json.loads((mdir / f"{stem}.stamp.json").read_text(encoding="utf-8"))
        pages = sorted({b["page"] for b in V["blocks"]} | {r["page"] for r in V["page_regions"]})
        exp = len(az["pages"])
        if old:
            vid = old["version_id"]
            delete_version(con, vid)
        else:
            vid = spk("versions", f"V:{stem}@{run}")      # from the version key, never from load order
        con.execute("""INSERT INTO versions (version_id, version_key, stem, run, stamp_run, made, load_id, jats_sha, alto_sha,
                       pdf_sha, sidecars_sha, inputs_sha, pages_covered, pages_expected, complete, content_in_db,
                       is_current, masters_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,0,?)
                       ON CONFLICT(version_id) DO UPDATE SET stamp_run = excluded.stamp_run, made = excluded.made,
                       load_id = excluded.load_id, jats_sha = excluded.jats_sha, alto_sha = excluded.alto_sha,
                       pdf_sha = excluded.pdf_sha, sidecars_sha = excluded.sidecars_sha, inputs_sha = excluded.inputs_sha,
                       pages_covered = excluded.pages_covered, pages_expected = excluded.pages_expected,
                       complete = excluded.complete, masters_key = excluded.masters_key""",
                    (vid, f"V:{stem}@{run}", stem, run, stamp.get("run"), stamp.get("made"), load_id,
                     sha_file(files[0]), sha_file(files[1]), sha_file(mdir / f"{stem}.pdf"),
                     sha_files(files[2:4]), sha, pages_text(pages), exp, int(len(pages) >= exp),
                     f"{run}/masters/{stem}.jats.xml"))
        n = write_version(con, V, vid, f"V:{stem}@{run}")
        counts.update(n)
        # consistency of the line crosswalk with the masters' own 'P:N' labels on fixes and misprints
        for c in V["text_corrections"]:
            if c["_line_label"] and c["_alto_line"]:
                m = re.match(r"(\d+):(\d+)", c["_line_label"])
                lm = next((r for r in V["line_map"] if r["alto_line_id"] == c["_alto_line"]), None)
                if m and lm:
                    checks["label_agree" if (lm["page"], lm["azure_line_no"]) == (int(m[1]), int(m[2]))
                           else "label_disagree"] += 1
        checks["calls_46"] += V["n_calls_46"]
        checks["calls_v2"] += len(V["note_calls"])
        checks["text_mismatch_blocks"] += len(V.get("text_mismatch") or [])
        touched.append(stem)
        done += 1
        if done % 25 == 0:
            con.commit()
            print(f"  {i + 1}/{len(stems)} ({time.time() - t0:.0f} s)", flush=True)
    con.commit()
    return done, skipped, touched, counts, checks


# ------------------------------------------------------------------ which version is shown
def choose_current(con, stems: list):
    for stem in stems:
        vs = con.execute("SELECT v.*, r.kind FROM versions v JOIN runs r USING (run) WHERE v.stem = ?", (stem,)).fetchall()
        if not vs:
            continue
        person = [v for v in vs if v["chosen_by"] == "person"]
        if person:
            best, why = person[0], "person"
        else:
            def rank(v):
                return (-(v["complete"] or 0), PURPOSE.get(v["kind"], 9), "" if not v["made"] else
                        "".join(chr(255 - ord(c)) for c in v["made"]))
            srt = sorted(vs, key=rank)
            best = srt[0]
            why = "only version"
            if len(srt) > 1:
                o = srt[1]
                if (best["complete"] or 0) != (o["complete"] or 0):
                    why = "complete"
                elif PURPOSE.get(best["kind"], 9) != PURPOSE.get(o["kind"], 9):
                    why = "purpose:final>judged>base>exam>sample"
                else:
                    why = "newest"
        con.execute("UPDATE versions SET is_current = 0, current_reason = NULL, chosen_by = CASE WHEN chosen_by = "
                    "'person' THEN chosen_by END WHERE stem = ? AND version_id <> ?", (stem, best["version_id"]))
        con.execute("UPDATE versions SET is_current = 1, current_reason = ?, chosen_by = coalesce(chosen_by, "
                    "'agent:load47') WHERE version_id = ?", (why, best["version_id"]))
        lvl = {"final": "final", "judged": "judged"}.get(best["kind"], "structured")
        con.execute("UPDATE documents SET level = ? WHERE stem = ?", (lvl, stem))


# ------------------------------------------------------------------ run-level quality files
def load_flags(con, run: str, path: Path) -> int:
    vids = {r["stem"]: r["version_id"] for r in con.execute("SELECT stem, version_id FROM versions WHERE run = ?",
                                                            (run,))}
    con.execute("DELETE FROM flags WHERE version_id IN (SELECT version_id FROM versions WHERE run = ?)", (run,))
    if not path.exists():
        return 0
    d = json.loads(path.read_text(encoding="utf-8"))
    th = json.dumps(dict(thresholds=d.get("thresholds"), norms=d.get("norms")), sort_keys=True, ensure_ascii=False)
    import hashlib
    h = hashlib.sha1(th.encode()).hexdigest()[:8]
    rows, dets = [], {}
    anchors = {}
    for stem, a in (d.get("articles") or {}).items():
        vid = vids.get(stem)
        if not vid:
            continue
        lm = {}
        for r in con.execute("SELECT page, azure_line_no, block_id FROM line_map WHERE version_id = ? AND "
                             "azure_line_no IS NOT NULL", (vid,)):
            lm.setdefault((r["page"], r["azure_line_no"]), r["block_id"])
        al = {(r["page"], r["line_no"]): r for r in con.execute(
            "SELECT page, line_no, first_word, last_word FROM azure_lines WHERE stem = ?", (stem,))}
        for f in a.get("flags") or []:
            kind = f.get("kind")
            det = f"{kind}@{h}"
            dets[det] = dict(detector_id=det, kind=kind, code_hash=None, thresholds=th, introduced=d.get("made"))
            lines = [x for x in (f.get("lines") or []) if isinstance(x, str) and re.match(r"^\d+:\d+$", x)]
            blk = None
            ws = []
            pg = f.get("page")
            for x in lines:
                p, n = (int(y) for y in x.split(":"))
                blk = blk or lm.get((p, n))
                r = al.get((p, n))
                if r and p == (pg or p) and r["first_word"]:
                    ws += [r["first_word"], r["last_word"]]
            ak = None
            if ws and pg:
                ak = f"{stem}|p{pg}|w{min(ws)}-{max(ws)}"
                anchors[ak] = (stem, pg, min(ws), max(ws))
            extra = {k: v for k, v in f.items() if k not in ("id", "stem", "kind", "severity", "page", "lines", "box",
                                                             "reason")}
            rows.append(dict(version_id=vid, flag_id=f.get("id"), detector_id=det, kind=kind,
                             severity=f.get("severity"), page=pg, block_id=blk,
                             lines_raw=jdump(f.get("lines")), box_raw=jdump(f.get("box")), reason=f.get("reason"),
                             extra=jdump(extra) if extra else None, _ak=ak))
    insert(con, "flag_detectors", list(dets.values()))
    A = anchor_from_words(con, anchors, "line")
    for r in rows:
        r["anchor_pk"] = A.get(r.pop("_ak"))
    return insert(con, "flags", rows)


def anchor_from_words(con, spans: dict, method: str) -> dict:
    """anchor_key -> pk for word spans given as (stem, page, first, last), text and box read from the Azure lines."""
    out = {}
    for k, (stem, page, a, b) in spans.items():
        r = con.execute("SELECT anchor_pk FROM ink_anchors WHERE anchor_key = ?", (k,)).fetchone()
        if r:
            out[k] = r[0]
            continue
        ls = con.execute("SELECT x, y, w, h, text, wc_min FROM azure_lines WHERE stem = ? AND page = ? AND "
                         "first_word <= ? AND last_word >= ?", (stem, page, b, a)).fetchall()
        if ls:
            x0 = min(r["x"] for r in ls)
            y0 = min(r["y"] for r in ls)
            x1 = max(r["x"] + r["w"] for r in ls)
            y1 = max(r["y"] + r["h"] for r in ls)
            wc = [r["wc_min"] for r in ls if r["wc_min"] is not None]
            row = fill_pk("ink_anchors", [dict(anchor_key=k, stem=stem, page=page, first_word=a, last_word=b, x=x0, y=y0,
                                               w=x1 - x0, h=y1 - y0, text_azure=" / ".join(r["text"] for r in ls),
                                               wc_min=min(wc) if wc else None, method=method)])[0]
            insert(con, "ink_anchors", [row], "INSERT")
            out[k] = row["anchor_pk"]
    return out


def load_patches(con, run: str, mdir: Path, pdirs: list, load_id: int) -> tuple:
    vids = {r["stem"]: r["version_id"] for r in con.execute("SELECT stem, version_id FROM versions WHERE run = ?",
                                                            (run,))}
    vload = {r["version_id"]: r["load_id"] for r in con.execute("SELECT version_id, load_id FROM versions WHERE run = ?",
                                                                (run,))}
    rows = []
    for pdir in pdirs:
        for f in sorted(pdir.glob("*.json")) if pdir.exists() else []:
            try:
                lst = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(lst, dict):
                lst = lst.get("patches") or []
            for p in lst:
                if not isinstance(p, dict) or not p.get("id"):
                    continue
                stem = p.get("article") or f.stem
                prun = p.get("run") or run
                key_ = f"{prun}|{stem}|{p['id']}"
                src = p.get("source") or "judge"
                act = p.get("action") or ""
                dom = "content"
                if act in ("set_title", "set_meta", "set_pages"):
                    dom = "metadata"
                rows.append(dict(patch_key=key_, run=prun, stem=stem, patch_id=p["id"], domain=dom, op=act,
                                 page=p.get("page"), targets=jdump(p.get("targets")), payload=jdump(p.get("payload")),
                                 source=src, priority={"person": 1, "judge": 2, "gemini-retry": 3}.get(src, 4),
                                 actor_id=("model:" + p["model"]) if p.get("model") and src in ("judge", "gemini-retry")
                                 else ("model:gemini-4-argon" if src == "gemini-retry" else
                                       ("person:owner" if src == "person" else None)),
                                 finding_pk=None, confidence=p.get("confidence"), evidence=jdump(p.get("evidence")),
                                 reason=p.get("reason"), apply=int(bool(p.get("apply"))), created=p.get("created"),
                                 root_id="local-43", file_key=str(f.relative_to(OUT43)), sha=sha_file(f),
                                 payload_copy=jdump(p) if src == "person" else None, _model=p.get("model")))
    for r in rows:
        if r["_model"]:
            insert(con, "actors", [dict(actor_id="model:" + r["_model"], kind="model", name=r["_model"], note=None)],
                   "INSERT OR IGNORE")
    seen = {}
    for r in rows:
        seen[r["patch_key"]] = {k: v for k, v in r.items() if not k.startswith("_")}
    # patches never change after they are made: same key, same row. A patch copied into several runs' folders is
    # kept from the first file in name order, whichever run is loaded first
    keep = []
    for r in seen.values():
        old = con.execute("SELECT file_key FROM patches WHERE patch_key = ?", (r["patch_key"],)).fetchone()
        if not old or r["file_key"] < old[0] or r["file_key"] == old[0]:
            keep.append(r)
    insert(con, "patches", keep)
    # what this run's build did with them (the masters' <stem>.patches.json)
    con.execute("DELETE FROM patch_applications WHERE version_id IN (SELECT version_id FROM versions WHERE run = ?) OR "
                "(version_id IS NULL AND patch_key IN (SELECT patch_key FROM patches WHERE run = ?))", (run, run))
    apps = []
    for sc in sorted(mdir.glob("*.patches.json")):
        try:
            d = json.loads(sc.read_text(encoding="utf-8"))
        except Exception:
            continue
        stem = d.get("stem") or sc.name[:-len(".patches.json")]
        vid = vids.get(stem)
        if vid is None:
            continue                 # a sidecar of a document this run did not load (--stem): not this load's build
        st = {}
        for kind in ("applied", "skipped", "overridden"):
            for e in d.get(kind) or []:
                pid = e.get("id") if isinstance(e, dict) else e
                st[pid] = (kind, e.get("why") if isinstance(e, dict) else None)
        for e in d.get("log") or []:
            if isinstance(e, dict) and e.get("id"):
                st[e["id"]] = (e.get("status") or e.get("result") or "logged", e.get("why"))
        for pid, (s, why) in st.items():
            pk = next((k for k in seen if k.endswith(f"|{stem}|{pid}")), None)
            if pk:
                apps.append(dict(patch_key=pk, version_id=vid, load_id=vload.get(vid) or load_id, status=s,
                                 why=jdump(why)))
    for pk, r in seen.items():
        if r["stem"] in vids and not any(a["patch_key"] == pk for a in apps) and \
                (mdir / f"{r['stem']}.patches.json").exists():
            apps.append(dict(patch_key=pk, version_id=vids[r["stem"]], load_id=vload.get(vids[r["stem"]]) or load_id,
                             status="proposed" if not r["apply"] else "not-built", why=None))
    insert(con, "patch_applications", apps)
    # blocks rewritten by an applied patch carry it as their text source
    for a in apps:
        if a["status"] != "applied" or not a["version_id"]:
            continue
        p = seen[a["patch_key"]]
        tg = json.loads(p["targets"] or "{}") if p["targets"] else {}
        bl = [b.get("id") if isinstance(b, dict) else b for b in (tg.get("blocks") or [])] if isinstance(tg, dict) else []
        bl = [b for b in bl if isinstance(b, str)]
        for ln_ in (tg.get("lines") or []) if isinstance(tg, dict) else []:
            m = re.match(r"(\d+):(\d+)", str(ln_))
            if m:
                r = con.execute("SELECT block_id FROM line_map WHERE version_id = ? AND page = ? AND azure_line_no = ? "
                                "AND block_id IS NOT NULL", (a["version_id"], int(m[1]), int(m[2]))).fetchone()
                if r:
                    bl.append(r[0])
        for b in set(bl):
            con.execute("UPDATE blocks SET text_source = ? WHERE version_id = ? AND block_id = ?",
                        (f"patch:{p['source']}:{a['patch_key']}", a["version_id"], b))
    return len(seen), len(apps)


def base_run(run: str) -> str:
    return re.sub(r"_(judged|fixed|patched|final)\w*$", "", run)


def load_judge(con, run: str) -> tuple:
    """Judge answers out/judge/answers/<model dir>/<base run>/<stem>_pNNN.json -> judge_calls (every look, clean or
    not, with its cost) and judge_findings (one per problem named)."""
    br = base_run(run)
    vids = {r["stem"]: r["version_id"] for r in con.execute("SELECT stem, version_id FROM versions WHERE run = ?",
                                                            (br,))}
    con.execute("DELETE FROM judge_findings WHERE call_id IN (SELECT call_id FROM judge_calls WHERE run = ?)", (br,))
    con.execute("DELETE FROM judge_calls WHERE run = ?", (br,))
    con.execute("DELETE FROM model_calls WHERE run = ? AND job = 'judge'", (br,))
    pt = {}
    for r in con.execute("SELECT patch_key, stem, patch_id, apply, actor_id FROM patches WHERE source = 'judge'"):
        pt.setdefault((r["stem"], r["patch_id"]), []).append(r)
    calls, finds, mcalls, links = [], [], [], []
    for f in sorted((OUT43 / "judge" / "answers").glob(f"*/{br}/*_p[0-9][0-9][0-9].json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        mdir_ = f.parent.parent.name
        model = rec.get("model") or mdir_.split("_")[0]
        pv = mdir_.split("_", 1)[1] if "_" in mdir_ else "v1"
        stem, page = rec.get("stem"), rec.get("page")
        ans = rec.get("answer") or {}
        probs = ans.get("problems") or []
        cid = f"{br}|{stem}|p{page}|{model}|{pv}"
        verdict = "failed" if not ans else ("problems" if probs else "clean")
        calls.append(dict(call_id=cid, run=br, version_id=vids.get(stem), stem=stem, page=page, model=model,
                          prompt_version=pv, view=None, mode=rec.get("mode"), usd=rec.get("usd"),
                          tokens_in=rec.get("tin"), tokens_out=rec.get("tout"), finish=rec.get("finish"),
                          verdict=verdict, root_id="local-43", file_key=str(f.relative_to(OUT43)), sha=sha_file(f)))
        mcalls.append(dict(called=None, model=model, job="judge", run=br, stem=stem, page=page, chunk=None,
                           mode=rec.get("mode"), tokens_in=rec.get("tin"), tokens_out=rec.get("tout"),
                           tokens_think=rec.get("think"), usd=rec.get("usd"), finish=rec.get("finish"),
                           root_id="local-43", file_key=str(f.relative_to(OUT43)), sha=None))
        for k, pr in enumerate(probs, 1):
            pid = f"j-{stem[:4]}-p{page}-{k}"
            ps = [p for p in pt.get((stem, pid), []) if (p["actor_id"] or "") in ("", f"model:{model}")]
            p = ps[0] if ps else None
            route = ("auto" if p["apply"] else "proposed") if p else pr.get("route")
            finds.append(dict(call_id=cid, k=k, type=pr.get("type"), subtype=pr.get("subtype"),
                              confidence=pr.get("confidence"), question=None, answer=pr.get("instruction"),
                              evidence=pr.get("evidence"), code_check=None, action=pr.get("action"), route=route,
                              targets_raw=jdump(dict(blocks=pr.get("blocks") or [], lines=pr.get("lines") or [],
                                                     box=pr.get("box"))), _p=p, _lines=pr.get("lines") or [],
                              _stem=stem, _page=page))
    insert(con, "judge_calls", calls)
    insert(con, "model_calls", mcalls)
    spans = {}
    for x in finds:
        ws = []
        for lab in x["_lines"]:
            m = re.match(r"(\d+):(\d+)", str(lab))
            if m and int(m[1]) == x["_page"]:
                r = con.execute("SELECT first_word, last_word FROM azure_lines WHERE stem = ? AND page = ? AND "
                                "line_no = ?", (x["_stem"], int(m[1]), int(m[2]))).fetchone()
                if r and r[0]:
                    ws += [r[0], r[1]]
        if ws:
            x["_ak"] = f"{x['_stem']}|p{x['_page']}|w{min(ws)}-{max(ws)}"
            spans[x["_ak"]] = (x["_stem"], x["_page"], min(ws), max(ws))
    A = anchor_from_words(con, spans, "line")
    for x in finds:
        x["anchor_pk"] = A.get(x.get("_ak"))
    ins = [{k: v for k, v in x.items() if not k.startswith("_")} for x in finds]
    insert(con, "judge_findings", ins)
    for x in finds:
        if x["_p"]:
            r = con.execute("SELECT finding_pk FROM judge_findings WHERE call_id = ? AND k = ?",
                            (x["call_id"], x["k"])).fetchone()
            con.execute("UPDATE patches SET finding_pk = ? WHERE patch_key = ?", (r[0], x["_p"]["patch_key"]))
    return len(calls), len(finds)


def load_model_calls(con, run: str) -> int:
    """The reader's chunk calls (out/<run>/raw/<stem>_cXXX-YYY.json): cost per version."""
    con.execute("DELETE FROM model_calls WHERE run = ? AND job IN ('read', 'retry')", (run,))
    rows = []
    for f in sorted((OUT43 / run / "raw").glob("*_c[0-9][0-9][0-9]-[0-9][0-9][0-9].json")):
        if f.name.endswith(".failed.json"):
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        m = re.match(r"(.+)_c(\d{3})-(\d{3})\.json$", f.name)
        rows.append(dict(called=None, model=d.get("model") or "gemini-4-argon", job="read", run=run,
                         stem=d.get("stem") or m.group(1), page=d.get("first") or int(m.group(2)),
                         chunk=int(m.group(2)), mode=d.get("mode"), tokens_in=d.get("tin"), tokens_out=d.get("tout"),
                         tokens_think=d.get("think"), usd=d.get("usd"), finish=d.get("finish"), root_id="local-43",
                         file_key=str(f.relative_to(OUT43)), sha=None))
    insert(con, "model_calls", rows)
    con.execute("""UPDATE versions SET usd = (SELECT round(sum(usd), 6) FROM model_calls m WHERE m.run = versions.run
                   AND m.stem = versions.stem AND m.job = 'read'),
                   tokens_in = (SELECT sum(tokens_in) FROM model_calls m WHERE m.run = versions.run AND m.stem = versions.stem AND m.job = 'read'),
                   tokens_out = (SELECT sum(tokens_out) FROM model_calls m WHERE m.run = versions.run AND m.stem = versions.stem AND m.job = 'read'),
                   n_chunks = (SELECT count(*) FROM model_calls m WHERE m.run = versions.run AND m.stem = versions.stem AND m.job = 'read')
                   WHERE run = ?""", (run,))
    return len(rows)


def load_reviews(con) -> int:
    """Judge verdicts, the judge truth file (gold pages) and the owner's gold files; link checks come in link47."""
    rows = []
    jv = E43 / "judge_verdicts43.json"
    if jv.exists():
        d = json.loads(jv.read_text(encoding="utf-8"))
        for k, v in (d.get("verdicts") or {}).items():
            mdir_, sp, n = k.split("|")
            stem, page = sp.split(":")
            model = mdir_.split("_")[0]
            pv = mdir_.split("_", 1)[1] if "_" in mdir_ else "v1"
            c = con.execute("SELECT call_id FROM judge_calls WHERE stem = ? AND page = ? AND model = ? AND "
                            "prompt_version = ? ORDER BY run = 'v33_300' DESC LIMIT 1",
                            (stem, int(page), model, pv)).fetchone()
            subj = f"{c[0]}|{n}" if c else f"?|{stem}|p{page}|{model}|{pv}|{n}"
            rows.append(dict(subject_kind="finding", subject_key=subj, subject_fingerprint=None,
                             verdict={"real": "right", "false": "wrong", "debatable": "unsure"}.get(v.get("verdict"),
                                                                                                    v.get("verdict")),
                             note=v.get("note"), actor_id="agent:judge-verdicts43", checked="2026-10-20", is_gold=0,
                             source_file="judge_verdicts43.json"))
    jt = E43 / "judge_truth43.json"
    if jt.exists():
        d = json.loads(jt.read_text(encoding="utf-8"))
        for p in d.get("pages") or []:
            rows.append(dict(subject_kind="page", subject_key=f"{p['page']}@{p.get('run')}",
                             subject_fingerprint=None, verdict="known-problems" if p.get("problems") else "clean",
                             note=jdump(dict(problems=p.get("problems"), words=p.get("words"))),
                             actor_id="person:owner" if "owner" in (p.get("src") or "") else "agent:judge-verdicts43",
                             checked=None, is_gold=1, source_file="judge_truth43.json"))
    for f in sorted((E43 / "gold").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for c in d.get("checked") or []:
            rows.append(dict(subject_kind="article", subject_key=f"{d.get('stem')}@{d.get('run')}",
                             subject_fingerprint=None, verdict="right" if "right" in (c.get("source") or "") else
                             "unsure", note=c.get("source"), actor_id="person:owner", checked=c.get("date"),
                             is_gold=1, source_file=f"gold/{f.name}"))
    con.execute("DELETE FROM reviews WHERE source_file <> 'link_checks'")
    return insert(con, "reviews", rows)


# ------------------------------------------------------------------ derived per version: flags on blocks, trust, search
def refresh_quality(con, run: str):
    con.execute("""UPDATE blocks SET n_flags = (SELECT count(*) FROM flags f WHERE f.version_id = blocks.version_id
                   AND f.block_id = blocks.block_id) WHERE version_id IN (SELECT version_id FROM versions WHERE run = ?)""",
                (run,))
    con.execute("""UPDATE blocks SET trust = (SELECT t.trust FROM v_block_trust t WHERE t.version_id = blocks.version_id
                   AND t.block_id = blocks.block_id) WHERE version_id IN (SELECT version_id FROM versions WHERE run = ?)""",
                (run,))
    # each citation mention: corrections and flags whose ink overlaps its own words; trust from its block
    con.execute("""UPDATE citation_mentions SET
        n_fixes_on_lines = (SELECT count(*) FROM text_corrections c JOIN ink_anchors a ON a.anchor_pk = c.anchor_pk
            JOIN ink_anchors m ON m.anchor_pk = citation_mentions.anchor_pk
            WHERE c.version_id = citation_mentions.version_id AND c.layer = 'azure-misread' AND a.stem = m.stem
            AND a.page = m.page AND a.first_word <= m.last_word AND a.last_word >= m.first_word),
        n_misprints_on_lines = (SELECT count(*) FROM text_corrections c JOIN ink_anchors a ON a.anchor_pk = c.anchor_pk
            JOIN ink_anchors m ON m.anchor_pk = citation_mentions.anchor_pk
            WHERE c.version_id = citation_mentions.version_id AND c.layer = 'misprint' AND a.stem = m.stem
            AND a.page = m.page AND a.first_word <= m.last_word AND a.last_word >= m.first_word),
        max_flag = (SELECT f.severity FROM flags f JOIN ink_anchors a ON a.anchor_pk = f.anchor_pk
            JOIN ink_anchors m ON m.anchor_pk = citation_mentions.anchor_pk
            WHERE f.version_id = citation_mentions.version_id AND a.stem = m.stem AND a.page = m.page
            AND a.first_word <= m.last_word AND a.last_word >= m.first_word
            ORDER BY CASE f.severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END LIMIT 1)
        WHERE version_id IN (SELECT version_id FROM versions WHERE run = ?)""", (run,))
    con.execute("""UPDATE citation_mentions SET trust = round(max(0.05, coalesce((SELECT b.trust FROM blocks b WHERE
        b.version_id = citation_mentions.version_id AND b.block_id = citation_mentions.block_id), 1.0)
        * (CASE WHEN n_misprints_on_lines > 0 THEN 0.85 ELSE 1.0 END)
        * (CASE max_flag WHEN 'high' THEN 0.7 WHEN 'medium' THEN 0.85 ELSE 1.0 END)), 3)
        WHERE version_id IN (SELECT version_id FROM versions WHERE run = ?)""", (run,))


def refresh_search(con, stems: list):
    """search_units for the shown version of each document (blocks, figure texts, equations, verse lines, printed
    citations), indexed folded and clitic-stripped; per document, no corpus rebuild."""
    for stem in stems:
        for (vid,) in con.execute("SELECT version_id FROM versions WHERE stem = ?", (stem,)).fetchall():
            for (uid, f, s) in con.execute("SELECT uid, folded, stemmed FROM search_units WHERE version_id = ?",
                                           (vid,)).fetchall():
                con.execute("INSERT INTO search_fts(search_fts, rowid, folded, stemmed) VALUES ('delete', ?, ?, ?)",
                            (uid, f, s))
            con.execute("DELETE FROM search_units WHERE version_id = ?", (vid,))
        cur = con.execute("SELECT version_id FROM versions WHERE stem = ? AND is_current = 1", (stem,)).fetchone()
        if not cur:
            continue
        vid = cur[0]
        rows = []
        for b in con.execute("SELECT uid, block_id, lang, text, anchor_pk FROM blocks WHERE version_id = ?", (vid,)):
            if b["text"]:
                rows.append(dict(uid=b["uid"], version_id=vid, unit_kind="block", unit_id=b["block_id"], lang=b["lang"],
                                 text=b["text"], anchor_pk=b["anchor_pk"]))
        for f in con.execute("SELECT * FROM figures WHERE version_id = ?", (vid,)):
            for kind, col, lang in (("alt-text", "alt_ar", "ar"), ("alt-text", "alt_en", "en"),
                                    ("figure-text", "text_in_figure", None), ("equation", "tex", None)):
                if f[col]:
                    rows.append(dict(uid=spk("uid", vid, kind, f"{f['figure_id']}:{col}"), version_id=vid, unit_kind=kind,
                                     unit_id=f"{f['figure_id']}:{col}", lang=lang, text=f[col],
                                     anchor_pk=f["anchor_pk"]))
        for v in con.execute("SELECT verse_id, text, anchor_pk FROM verse_lines WHERE version_id = ?", (vid,)):
            rows.append(dict(uid=spk("uid", vid, "verse", v["verse_id"]), version_id=vid, unit_kind="verse",
                             unit_id=v["verse_id"], lang="ar",
                             text=v["text"], anchor_pk=v["anchor_pk"]))
        for m in con.execute("SELECT mention_id, printed, anchor_pk FROM citation_mentions WHERE version_id = ? AND "
                             "kind IN ('full', 'short')", (vid,)):
            if m["printed"]:
                rows.append(dict(uid=spk("uid", vid, "citation", m["mention_id"]), version_id=vid, unit_kind="citation",
                                 unit_id=m["mention_id"],
                                 lang=None, text=m["printed"], anchor_pk=m["anchor_pk"]))
        for r in rows:
            r["folded"] = fold(r["text"])
            r["stemmed"] = stemmed(r["text"])
        insert(con, "search_units", rows, "INSERT OR IGNORE")
        con.executemany("INSERT INTO search_fts(rowid, folded, stemmed) VALUES (?, ?, ?)",
                        [(r["uid"], r["folded"], r["stemmed"]) for r in rows])


def refresh_pages(con, stems: list):
    """Printed folio and running head of each page, from the shown version's page regions (Azure's words)."""
    for stem in stems:
        cur = con.execute("SELECT version_id FROM versions WHERE stem = ? AND is_current = 1", (stem,)).fetchone()
        if not cur:
            continue
        con.execute("UPDATE pages SET printed_folio = NULL, printed_folio_int = NULL, running_head = NULL WHERE stem = ?",
                    (stem,))
        for r in con.execute("SELECT page, role, text FROM page_regions WHERE version_id = ? AND role IN "
                             "('pageNumber', 'pageHeader') ORDER BY y", (cur[0],)):
            if r["role"] == "pageNumber":
                v = re.sub(r"[^0-9٠-٩]", "", r["text"] or "")
                from common47 import to_int
                con.execute("UPDATE pages SET printed_folio = coalesce(printed_folio, ?), printed_folio_int = "
                            "coalesce(printed_folio_int, ?) WHERE stem = ? AND page = ?",
                            ((r["text"] or "").strip(), to_int(v) if v else None, stem, r["page"]))
            else:
                con.execute("UPDATE pages SET running_head = coalesce(running_head, ?) WHERE stem = ? AND page = ?",
                            ((r["text"] or "").strip(), stem, r["page"]))


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--masters")
    ap.add_argument("--flags")
    ap.add_argument("--patches", action="append")
    ap.add_argument("--stem", action="append")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--kind", help="run kind (default from the name): sample | base | judged | final | exam")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--note")
    a = ap.parse_args(argv)
    run = a.run
    mdir = Path(a.masters) if a.masters else OUT43 / run / "masters"
    if not mdir.exists():
        sys.exit(f"no masters folder {mdir}")
    con = connect(Path(a.db))
    static(con)
    t0 = time.time()
    stems = sorted(p.name[:-len(".jats.xml")] for p in mdir.glob("*.jats.xml"))
    if a.stem:
        stems = [s for s in stems if s in set(a.stem)]
    stamps = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(mdir.glob("*.stamp.json"))]
    st = stamps[0] if stamps else {}
    kind = a.kind or run_kind(run)
    con.execute("""INSERT INTO runs (run, kind, parent_run, model, prompt_hash, rules_hash, started, finished, root_id,
                   root_rel, note) VALUES (?,?,?,?,?,?,?,?, 'local-43', ?, ?) ON CONFLICT(run) DO UPDATE SET
                   kind = excluded.kind, parent_run = excluded.parent_run, model = excluded.model,
                   prompt_hash = excluded.prompt_hash, rules_hash = excluded.rules_hash, started = excluded.started,
                   finished = excluded.finished, note = CASE WHEN runs.note LIKE 'parent of a loaded run%'
                   THEN excluded.note ELSE coalesce(excluded.note, runs.note) END""",
                (run, kind, parent_of(run) if kind != "exam" or run.endswith("_final") else None, st.get("model"),
                 st.get("prompt_hash"), st.get("rules_hash"), min((s.get("made") or "") for s in stamps) if stamps
                 else None, max((s.get("made") or "") for s in stamps) if stamps else None, run, a.note))
    if kind == "exam" and run.endswith("_final"):
        con.execute("UPDATE runs SET parent_run = ? WHERE run = ?", (re.sub(r"_final$", "", run), run))
    if con.execute("SELECT parent_run FROM runs WHERE run = ?", (run,)).fetchone()[0]:
        p = con.execute("SELECT parent_run FROM runs WHERE run = ?", (run,)).fetchone()[0]
        con.execute("INSERT OR IGNORE INTO runs (run, kind, root_id, root_rel, note) VALUES (?, ?, 'local-43', ?, "
                    "'parent of a loaded run, not loaded itself yet')", (p, run_kind(p), p))
    cur = con.execute("INSERT INTO load_events (started, tool, tool_hash, run, export_id, args) VALUES (?, 'load47', ?, ?, "
                      "?, ?)", (now(), sha_files([HERE / "load47.py", HERE / "parse47.py", HERE / "ink47.py",
                                                  HERE / "biblio47.py"]), run, EXPORT, " ".join(sys.argv[1:])))
    load_id = cur.lastrowid
    azp = ink47.azure_paths()
    done, skipped, touched, counts, checks = load_versions(con, run, mdir, stems, a.force, load_id, azp)
    all_run = [r[0] for r in con.execute("SELECT stem FROM versions WHERE run = ?", (run,))]
    choose_current(con, all_run)
    nf = load_flags(con, run, Path(a.flags) if a.flags else OUT43 / run / "flags.json")
    pdirs = [Path(p) for p in a.patches] if a.patches else [OUT43 / run / "patches"]
    np_, napp = load_patches(con, run, mdir, pdirs, load_id)
    nj = load_judge(con, run)
    nmc = load_model_calls(con, run)
    con.execute("UPDATE runs SET usd = (SELECT round(sum(usd), 4) FROM model_calls WHERE run = ? AND job = 'read'), "
                "tokens_in = (SELECT sum(tokens_in) FROM model_calls WHERE run = ? AND job = 'read'), tokens_out = "
                "(SELECT sum(tokens_out) FROM model_calls WHERE run = ? AND job = 'read'), pages = (SELECT "
                "sum(pages_expected) FROM versions WHERE run = ?) WHERE run = ?", (run, run, run, run, run))
    refresh_quality(con, run)
    con.commit()
    nrev = load_reviews(con)
    # the bibliographic and people layers for every document this run reads (cheap; keeps the shown version's view)
    mcon = marc()
    bstats = biblio47.refresh(con, mcon, all_run, load_id)
    refresh_search(con, all_run)
    refresh_pages(con, all_run)
    con.commit()
    rows = {r[0]: con.execute(f"SELECT count(*) FROM [{r[0]}]").fetchone()[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'search_fts%' AND name NOT LIKE "
        "'sqlite_%'")}
    con.execute("UPDATE load_events SET finished = ?, n_loaded = ?, n_unchanged = ?, rows_by_table = ? WHERE load_id = ?",
                (now(), done, skipped, json.dumps(rows), load_id))
    con.commit()
    orphans = con.execute("PRAGMA foreign_key_check").fetchall()
    print(f"run {run} ({kind}): {len(stems)} masters, {done} loaded, {skipped} unchanged; {nf} flags, {np_} patches "
          f"({napp} applications), judge {nj[0]} calls / {nj[1]} findings, {nmc} chunk calls, {nrev} reviews; "
          f"{dict(checks)}; biblio {bstats}; orphans {len(orphans)} ({time.time() - t0:.0f} s)")
    if orphans:
        print("  orphans by table:", Counter((o[0], o[2]) for o in orphans).most_common(12))


if __name__ == "__main__":
    main()
