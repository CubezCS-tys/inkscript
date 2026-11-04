"""Experiment 61: "nothing lost" — does everything printed and everything Gemini returned end up in a proper field?

$0, no model calls, read-only on every input. For each current article of the release DB (780):

  1. LINE ACCOUNTING   every Azure word of every read page -> ALTO String (ink47.match_words, by box) -> TextBlock
                       -> JATS element (id / xlink:href) -> field (fields61.jats_class). Byline-like containers
                       (custom-meta front-matter-block, contrib, a byline paragraph in the text) are split by
                       matching their words against the JATS front's specific values (fields61.front_values).
                       Buckets: a = a specific field, b = generic text only, c = explicitly not article text,
                       d = nowhere. A line takes the bucket most of its words have. b and d are leaks.
  2. ANSWER ACCOUNTING every value of Gemini's answer (metadata, enrich, block attributes, parsed works, fixes,
                       sic, math, missed, ornaments) -> stored in its JATS field / stored elsewhere / flattened into
                       generic text / dropped, with the code's reason where known (answers61.py).
  3. BILINGUAL PAIRS   title, names, affiliations, positions, abstracts, keywords printed in Arabic and Latin
                       script: both stored as fields? linked?
  4. PLATFORM          the same words through the release DB (line_map -> blocks / page_regions; byline and
                       affiliation rows for the containers), and JATS fields that never reach a platform row.

Each leak is classed: mapping (Gemini returned it, our code dropped or flattened it: free to fix from the saved
answers), not_asked (no prompt version asks for it: must go into the prompt before gate 2), gemini_missed (asked,
printed, not returned).

    audit61.py run [--stems ...] [--workers 3]     per-article JSON -> out/articles/<stem>.json
    audit61.py aggregate                           out/audit.json (corpus totals, leak table, fix list)
    audit61.py one STEM                            print one article's summary (debugging)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "experiments" / "47_platform_v2"))
sys.path.append(str(REPO / "experiments" / "43_rehearsal"))
import fields61 as F  # noqa: E402
import ink47  # noqa: E402

E43OUT = REPO / "experiments" / "43_rehearsal" / "out"
RELEASE = Path(os.environ.get("AUDIT_RELEASE", Path.home() / "data/desk/releases/R20261023T005909.db"))
# experiment 65: the same audit on another platform DB / masters (AUDIT_RELEASE = a candidate DB) into another folder
# (AUDIT_OUT), so this experiment's own outputs stay as they are; or audit61.py --release DB --out DIR run|aggregate
OUT = Path(os.environ.get("AUDIT_OUT", HERE / "out"))
ART = OUT / "articles"
# the run whose saved answers each current run was built from (the letter-fix runs reuse their parents' answers)
RAW_OF = {"j0130_final": "j0130_final", "v33_300_final_lettersfix": "v33_300_final",
          "v33_300b_fix3_lettersfix": "v33_300b_fix3", "v2_55": "v2_55"}
LID = re.compile(r"^(\d+):(\d+)([a-z]?)$")
BUCKET_ORDER = {"d": 0, "b": 1, "c": 2, "a": 3}


def release():
    return sqlite3.connect(f"file:{RELEASE}?mode=ro&immutable=1", uri=True)


def current_versions(con) -> list[dict]:
    rows = con.execute("SELECT v.stem, v.run, v.version_id, v.masters_key, v.pages_covered, v.pages_expected, "
                       "v.complete, d.pub_id FROM versions v JOIN documents d ON d.stem = v.stem "
                       "WHERE v.is_current = 1 ORDER BY v.stem").fetchall()
    return [dict(stem=r[0], run=r[1], version_id=r[2], masters_key=r[3], pages_covered=r[4], pages_expected=r[5],
                 complete=r[6], pub_id=r[7]) for r in rows]


def pages_of(spec: str) -> list[int]:
    out = []
    for part in (spec or "").split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return out


# ------------------------------------------------------------------------------------------------ answers
def raw_of(run: str) -> str:
    """The run whose saved answers built this one (a rebuild folder <run>_fix61 reads its source run's)."""
    base = re.sub(r"_fix61(_d30)?$", "", run)   # exp 68: _fix61_d30 likewise
    return RAW_OF.get(base, base)


def load_answers(run: str, stem: str) -> list[dict]:
    d = E43OUT / raw_of(run) / "raw"
    out = []
    for f in sorted(d.glob(f"{stem}_c*.json")):
        if f.name.endswith(".failed.json"):
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        if j.get("stem") != stem:
            continue
        out.append(j)
    out.sort(key=lambda j: j.get("first") or 0)
    return out


def rules_logs(run: str, stem: str) -> list[dict]:
    d = E43OUT / raw_of(run) / "rules"
    out = []
    for f in sorted(d.glob(f"{stem}_c*.json")):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")).get("rules43") or {})
        except (OSError, json.JSONDecodeError):
            pass
    return out


def _lines_in(x) -> list[str]:
    """Every line id inside a block's lines / hemistichs / rows."""
    out = []
    if isinstance(x, str):
        if LID.match(x):
            out.append(x)
    elif isinstance(x, list):
        for y in x:
            out += _lines_in(y)
    elif isinstance(x, dict):
        for k in ("lines", "hemistichs", "rows"):
            if k in x:
                out += _lines_in(x[k])
    return out


def gemini_roles(answers: list[dict]) -> tuple[dict, set]:
    """Azure line 'P:N' -> the block type Gemini gave it (first one), and the set of lines it called noise."""
    role, noise = {}, set()
    for j in answers:
        a = j.get("answer") or {}
        for pg in a.get("pages") or []:
            for b in pg.get("blocks") or []:
                if not isinstance(b, dict):
                    continue
                t = str(b.get("type") or "?")
                if t == "title" and b.get("translated"):
                    t = "title (translated)"
                for lid in _lines_in(b):
                    m = LID.match(lid)
                    role.setdefault(f"{m.group(1)}:{m.group(2)}", t)
        for n in a.get("noise") or []:
            m = LID.match(str(n))
            if m:
                noise.add(f"{m.group(1)}:{m.group(2)}")
    return role, noise


def answer_values(answers: list[dict]) -> list[tuple[str, list[str]]]:
    """(key path, folded tokens) of every string in the answers' metadata and enrich parts."""
    out = []

    def walk(x, path):
        if isinstance(x, str):
            t = F.toks(x)
            if t and not LID.match(x):
                out.append((path, t))
        elif isinstance(x, list):
            for i, y in enumerate(x):
                walk(y, f"{path}[{i}]")
        elif isinstance(x, dict):
            for k, y in x.items():
                walk(y, f"{path}.{k}")
    for j in answers:
        a = j.get("answer") or {}
        if a.get("metadata"):
            walk(a["metadata"], "metadata")
        if a.get("enrich"):
            walk(a["enrich"], "enrich")
    return out


def sub_seq(small: list[str], big: list[str]) -> bool:
    n = len(small)
    if not n or n > len(big):
        return False
    first = small[0]
    for i in range(len(big) - n + 1):
        if big[i] == first and big[i:i + n] == small:
            return True
    return False


def covered_by(tokens: list[str], values) -> tuple[str | None, float]:
    """The answer value that holds these tokens (contiguously, or >= 80% of them for 3+ tokens)."""
    if not tokens:
        return None, 0.0
    best, share = None, 0.0
    for key, v in values:
        if sub_seq(tokens, v):
            return key, 1.0
        if len(tokens) >= 3:
            vs = set(v)
            s = sum(1 for t in tokens if t in vs) / len(tokens)
            if s > share:
                best, share = key, s
    return (best, share) if share >= 0.8 else (None, share)


# ------------------------------------------------------------------------------------------------ matching
def match_values(strings: list[dict], values: list[tuple[str, str]]) -> list[str | None]:
    """For the ALTO Strings of one container block (in order): the field of the value that covers each, or None.
    A value covers the Strings whose folded tokens it matches contiguously (longest values first)."""
    stoks = [F.toks(s["content"]) for s in strings]
    flat, owner = [], []
    for i, t in enumerate(stoks):
        for x in t:
            flat.append(x)
            owner.append(i)
    field_of = [None] * len(strings)
    taken = [False] * len(flat)
    vals = sorted({(f, tuple(F.toks(v))) for f, v in values if F.toks(v)}, key=lambda x: -len(x[1]))
    for f, vt in vals:
        n = len(vt)
        i = 0
        while i <= len(flat) - n:
            if F.same_tok(flat[i], vt[0]) and all(F.same_tok(flat[i + k], vt[k]) for k in range(n)) \
                    and not any(taken[i:i + n]):
                for k in range(i, i + n):
                    taken[k] = True
                    if field_of[owner[k]] is None:
                        field_of[owner[k]] = f
                i += n
            else:
                i += 1
    # a value Azure broke differently (a hyphen, a glued word): 3+ tokens, >= 85% of them present in this block,
    # in a window no longer than the value + 2
    for f, vt in vals:
        n = len(vt)
        if n < 3:
            continue
        need = set(vt)
        for i in range(0, max(1, len(flat) - n + 1)):
            win = range(i, min(len(flat), i + n + 2))
            hit = [k for k in win if flat[k] in need and not taken[k]]
            if len(set(flat[k] for k in hit)) >= 0.85 * len(need):
                for k in hit:
                    taken[k] = True
                    if field_of[owner[k]] is None:
                        field_of[owner[k]] = f
                break
    return field_of


def labels_in_block(fields: list, strings: list[dict], line_of: list) -> list:
    """In a block where some words matched a value, a line made only of label words («Accepted», «تاريخ القبول:»,
    «Email:») is the label of that value, not text that fell through."""
    if not any(fields):
        return fields
    out = list(fields)
    by_line = defaultdict(list)
    for i, ln in enumerate(line_of):
        by_line[ln].append(i)
    for ln, idx in by_line.items():
        if any(fields[i] for i in idx):
            continue
        ts = [F.toks(strings[i]["content"]) for i in idx]
        if all(all(x in F.LABELS for x in t) for t in ts if t) and any(ts):
            for i in idx:
                out[i] = "label"
    return out


def inside_value(strings: list[dict], values: list[tuple[str, str]]) -> str | None:
    """The field of a front value that holds this whole line (a title printed again on page 2, the journal's name
    printed on page 1): the line's words, in order, inside one value."""
    lt = [x for s in strings for x in F.toks(s["content"])]
    if not lt:
        return None
    for f, v in values:
        vt = F.toks(v)
        if len(lt) == 1 and (len(lt[0]) < (3 if f == "title" else 4) or (vt != lt and f not in (
                "title", "subtitle", "trans_title", "journal_info"))):
            continue
        if sub_seq(lt, vt):
            return f
    return None


def absorb_labels(line_fields: list, line_strings: list[dict]) -> list:
    """Label words («البريد الإلكتروني:»، «Email:»، «تاريخ الاستلام:»، «و»، «د.») next to a matched value take its
    field when nothing else in the line is unmatched."""
    fields = list(line_fields)
    known = [f for f in fields if f]
    if not known:
        return fields
    rest = [i for i, f in enumerate(fields) if f is None and F.is_word(line_strings[i]["content"])]
    if rest and all(all(t in F.LABELS or len(t) <= 2 for t in F.toks(line_strings[i]["content"])) for i in rest):
        main = Counter(known).most_common(1)[0][0]
        for i in rest:
            fields[i] = main
    return fields


# ------------------------------------------------------------------------------------------------ platform values
def platform_rows(con, V: dict) -> dict:
    vid, pub = V["version_id"], V["pub_id"]
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    cols = {r[1] for r in con.execute("PRAGMA table_info(byline_mentions)")}
    pos = "position" if "position" in cols else "NULL"      # experiment 65's column (absent from older DBs)
    bm = q("SELECT mention_pk, printed, email, role_phrase, ids, is_corresponding, twin_of_pk, script, contrib_type, "
           f"block_id, byline_pos, {pos}, {'contacts' if 'contacts' in cols else 'NULL'} FROM byline_mentions "
           "WHERE version_id = ?", vid)
    aff = q("SELECT a.mention_pk, a.seq, a.printed, a.position_title, a.org_text, a.faculty_text, a.dept_text, a.city, "
            "a.country_printed, a.faculty_printed, a.kind FROM affiliation_mentions a JOIN byline_mentions b "
            "USING (mention_pk) WHERE b.version_id = ?", vid)
    ma = q("SELECT field, value, form, lang, block_id FROM metadata_assertions WHERE version_id = ?", vid)
    dates = q("SELECT date_type, printed, derivation FROM publication_dates WHERE pub_id = ?", pub)
    kw = q("SELECT printed, source FROM publication_keywords WHERE version_id = ?", vid)
    ab = q("SELECT lang, text, form, block_id FROM abstracts WHERE version_id = ?", vid)
    notes = q("SELECT note_id, kind, written_by, text FROM notes WHERE version_id = ?", vid)
    blocks = {r[0]: dict(role=r[1], lang=r[2]) for r in
              q("SELECT block_id, role, lang FROM blocks WHERE version_id = ?", vid)}
    lmap = {r[0]: (r[1], r[2]) for r in q("SELECT alto_line_id, block_id, region_id FROM line_map WHERE version_id = ?",
                                          vid)}
    regions = {r[0]: r[1] for r in q("SELECT region_id, role FROM page_regions WHERE version_id = ?", vid)}
    counts = {}
    for t, sql in (("figures", "SELECT kind, COUNT(*), SUM(fig_type IS NOT NULL), SUM(alt_ar IS NOT NULL), "
                               "SUM(alt_en IS NOT NULL), SUM(text_in_figure IS NOT NULL), SUM(tex IS NOT NULL) "
                               "FROM figures WHERE version_id = ? GROUP BY kind"),):
        counts[t] = {r[0]: list(r[1:]) for r in q(sql, vid)}
    for t, sql in (("table_cells", "SELECT COUNT(*) FROM table_cells WHERE version_id = ?"),
                   ("verse_lines", "SELECT COUNT(*) FROM verse_lines WHERE version_id = ?"),
                   ("figure_notes", "SELECT COUNT(*) FROM figure_notes WHERE version_id = ?"),
                   ("page_marks", "SELECT COUNT(*) FROM page_marks WHERE version_id = ?"),
                   ("sections", "SELECT COUNT(*) FROM sections WHERE version_id = ? AND heading IS NOT NULL"),
                   ("citations_ref_list", "SELECT COUNT(DISTINCT container_id) FROM citation_mentions WHERE "
                                          "version_id = ? AND container_kind = 'ref-list'"),
                   ("citations_full", "SELECT COUNT(*) FROM citation_mentions WHERE version_id = ? AND kind = 'full'"),
                   ("fixes", "SELECT COUNT(*) FROM text_corrections WHERE version_id = ? AND layer = 'azure-misread'"),
                   ("misprints", "SELECT COUNT(*) FROM text_corrections WHERE version_id = ? AND layer = 'misprint'")):
        counts[t] = q(sql, vid)[0][0]
    counts["doc_type"] = q("SELECT doc_type FROM publications WHERE pub_id = ?", pub)[0][0] if pub else None
    return dict(bm=bm, aff=aff, ma=ma, dates=dates, kw=kw, ab=ab, notes=notes, blocks=blocks, lmap=lmap,
                regions=regions, counts=counts)


def platform_values(P: dict) -> list[tuple[str, str]]:
    out = []
    for r in P["bm"]:
        out.append(("author_name", r[1]))
        if r[2]:
            out.append(("email", r[2]))
        if r[3]:
            out.append(("position" if (r[8] or "author") == "author" else "role", r[3]))
        if r[4]:
            for v in json.loads(r[4]).values():
                out.append(("author_id", v))
        if len(r) > 11 and r[11]:                            # experiment 65: byline_mentions.position, .contacts
            out.append(("position", r[11]))
        if len(r) > 12 and r[12]:
            ct = json.loads(r[12])
            out += [("email", v) for v in ct.get("emails") or []] + [("phone_address", v) for v in
                                                                      ct.get("phones") or []] + \
                   [("doi_url", v) for v in ct.get("urls") or []]
    for r in P["aff"]:
        out.append(("affiliation", r[2]))
        if r[3]:
            out.append(("position", r[3]))
    for f, v, form, lang, bid in P["ma"]:
        if not v or form not in ("printed", "reader", "corrected"):
            continue
        fld = {"title": "title", "title_translated": "trans_title", "subtitle": "subtitle",
               "journal_title": "journal_info", "issue": "journal_info", "volume": "journal_info"}.get(f)
        if fld is None and "." in f:
            fld = {"conference": "conference", "thesis": "thesis", "reviewed_book": "reviewed_work",
                   "original": "original"}.get(f.split(".")[0])
        if fld:
            out.append((fld, v))
    for dt, pr, der in P["dates"]:
        if pr:
            out.append(("history_date" if dt in ("received", "accepted", "revised", "reviewed", "online") else
                        "pub_date", pr))
    for pr, src in P["kw"]:
        if pr and src == "masters":
            out.append(("keywords", pr))
    for lang, t, form, bid in P["ab"]:
        if form == "printed" and t:
            out.append(("abstract", t))
    for nid, kind, by, t in P["notes"]:
        if kind == "author-note" and t:
            out.append(("author_note", t))
    return [(f, v) for f, v in out if F.toks(v)]


PLATFORM_SPECIFIC = {"title": "title", "title-translated": "trans_title", "abstract": "abstract",
                     "keywords": "keywords", "heading": "heading", "paragraph": "paragraph", "list-item": "list_item",
                     "footnote": "footnote", "endnote": "endnote", "ref": "reference", "caption": "caption",
                     "table-cell": "table_cell", "verse-group": "verse", "quote": "quote"}
PLATFORM_CONTAINER = {"front-matter", "back-matter", "byline", "affiliation"}
# where each JATS field lives in the platform (for the flow's last column)
PLATFORM_HOME = {
    "title": "metadata_assertions.title", "trans_title": "metadata_assertions.title_translated",
    "subtitle": "metadata_assertions.subtitle", "abstract": "abstracts", "abstract_label": "blocks (heading)",
    "keywords": "publication_keywords", "author_name": "byline_mentions", "email": "byline_mentions.email",
    "position": "affiliation_mentions.position_title", "role": "byline_mentions.role_phrase",
    "author_id": "byline_mentions.ids", "affiliation": "affiliation_mentions", "author_note": "notes (author-note)",
    "history_date": "publication_dates", "pub_date": "publication_dates", "conference": "metadata_assertions.conference",
    "thesis": "metadata_assertions.thesis", "reviewed_work": "metadata_assertions.reviewed_book",
    "original": "metadata_assertions.original", "journal_info": "metadata_assertions (journal)",
    "heading": "sections", "paragraph": "blocks", "list_item": "blocks", "quote": "blocks", "verse": "verse_lines",
    "boxed_text": "blocks", "acknowledgements": "blocks", "appendix": "blocks", "footnote": "notes",
    "endnote": "notes", "reference": "citation_mentions", "caption": "figures.caption", "table_cell": "table_cells",
    "table_note": "figure_notes", "figure_note": "figure_notes", "equation": "figures (equation)",
    "figure_text": "figures.text_in_figure", "paragraph_added": "blocks"}


# ------------------------------------------------------------------------------------------------ word matching
def match_all(AP: dict, LP: dict) -> dict:
    """ALTO String id -> Azure word ordinals: ink47's box match, then two fallbacks for the words it misses (the
    masters re-lay a mixed Arabic / Latin line in reading order, so some boxes move): (1) the same folded word in an
    ALTO line that already holds this Azure line's other words; (2) the closest String of the ALTO TextLine whose
    box holds the word's centre. A word none of the three finds is not in the ALTO."""
    wmap = ink47.match_words(AP, LP)
    got = {n for v in wmap.values() for n in v}
    missing = [w for w in AP["words"] if w["n"] not in got]
    if not missing:
        return wmap
    s_line, line_strings, line_box = {}, defaultdict(list), {}
    for b in LP["blocks"]:
        for L in b["lines"]:
            line_box[L["id"]] = L["box"]
            for s in L["strings"]:
                s_line[s["id"]] = L["id"]
                line_strings[L["id"]].append(s)
    az_alto = defaultdict(set)                     # Azure line -> ALTO lines holding its matched words
    for sid, ns in wmap.items():
        for n in ns:
            ln = AP["word_line"].get(n)
            if ln:
                az_alto[ln].add(s_line.get(sid))
    used = Counter(sid for sid, ns in wmap.items() if ns)
    for w in missing:
        ln = AP["word_line"].get(w["n"])
        ft = F.fold(w["text"] or "").strip()
        hit = None
        for al in az_alto.get(ln, ()):
            for s in line_strings.get(al, []):
                if F.fold(s["content"] or "").strip() == ft and (s["id"] not in wmap or w["n"] not in wmap[s["id"]]):
                    if used[s["id"]] < 1 or ft == "":
                        hit = s
                        break
            if hit:
                break
        if hit is None:
            cx, cy = w["x"] + w["w"] / 2, w["y"] + w["h"] / 2
            for lid, bx in line_box.items():
                if bx and bx[0] - 10 <= cx <= bx[0] + bx[2] + 10 and bx[1] - 10 <= cy <= bx[1] + bx[3] + 10:
                    cands = [s for s in line_strings[lid] if s["box"]]
                    if cands:
                        hit = min(cands, key=lambda s: abs(s["box"][0] + s["box"][2] / 2 - cx))
                        break
        if hit is not None:
            wmap.setdefault(hit["id"], []).append(w["n"])
            used[hit["id"]] += 1
    return wmap


# ------------------------------------------------------------------------------------------------ one article
def audit_article(con, V: dict) -> dict:
    stem, run = V["stem"], V["run"]
    mk = E43OUT / V["masters_key"]
    root = etree.parse(str(mk)).getroot()
    alto = ink47.read_alto(Path(str(mk).replace(".jats.xml", ".alto.xml")))
    az = ink47.read_azure(AZ[stem])
    answers = load_answers(run, stem)
    prompts = sorted({j.get("prompt") or "?" for j in answers})
    prompt = answers[0].get("prompt") if answers else "?"
    groles, gnoise = gemini_roles(answers)
    gmath = {f"{m.group(1)}:{m.group(2)}" for j in answers for x in (j.get("answer") or {}).get("math") or []
             if isinstance(x, dict) for m in [LID.match(str(x.get("line") or ""))] if m}
    wrong_page = 0
    avals = answer_values(answers)
    P = platform_rows(con, V)
    pvals = platform_values(P)
    jvals = F.front_values(root)
    jvals2 = [(f, v) for f, v in jvals if len(F.toks(v)) >= 2]
    els = {}
    for e in root.iter():
        if isinstance(e.tag, str) and e.get("id") and e.get("id") not in els:
            els[e.get("id")] = e
    # text printed inside figures (fig/p[@content-type=text-in-figure]), per page
    fig_text = defaultdict(set)
    for fg in root.iter("fig"):
        m = re.match(r"p(\d+)f", fg.get("id") or "")
        for p in fg.iter("p"):
            if p.get("content-type") == "text-in-figure":
                fig_text[int(m.group(1)) if m else 0].update(F.toks(F.text_of(p)))
    read_pages = set(pages_of(V["pages_covered"])) or set(az["pages"])
    # a window (v2_55: an excerpt of a long document) numbers its pages 1..n; Azure and the answer use the scan's
    off = 0
    for cm in root.iter("custom-meta"):
        if (cm.findtext("meta-name") or "").strip() == "window":
            m = re.search(r"pages\s+(\d+)-(\d+)\s+of", F.text_of(cm.find("meta-value")))
            if m:
                off = int(m.group(1)) - 1

    words = {}                      # (page, azure word no) -> record
    alto_at = defaultdict(list)     # page -> (x, y, folded text, record) of every ALTO String
    line_of_string = {}
    for p in sorted(read_pages):
        if p + off not in az["pages"]:
            continue
        AP = az["pages"][p + off]
        LP = alto.get(p)
        wmap = match_all(AP, LP) if LP else {}
        for tb in (LP or {}).get("blocks", []):
            role = ink47.role_of(tb["tags"])
            href = (tb.get("href") or "").rsplit("#", 1)[-1] or None
            el = els.get(href) if href else None
            if el is not None:
                bucket, field = F.jats_class(el)
            elif role in F.REGION:
                bucket, field = F.REGION[role]
            elif tb["id"] in els and role not in F.REGION:
                bucket, field = F.jats_class(els[tb["id"]])
            else:
                bucket, field = "b", f"unresolved:{role}"
            where = field
            if bucket == "container":       # values may run over a line break: match the whole block, then by line
                allstr = [s for L in tb["lines"] for s in L["strings"]]
                jf_all = labels_in_block(match_values(allstr, jvals), allstr,
                                         [L["id"] for L in tb["lines"] for _ in L["strings"]])
            so = 0
            for L in tb["lines"]:
                strings = L["strings"]
                jf = [None] * len(strings)
                if bucket == "container":
                    jf = absorb_labels(jf_all[so:so + len(strings)], strings)
                so += len(strings)
                if bucket == "b" and not field.startswith("unresolved"):
                    whole = inside_value(strings, jvals)
                    if whole:
                        gf = [whole] * len(strings)
                    else:                       # «سنة النشر: 2018»: a label and a one-word value, wholly held
                        g1 = absorb_labels(match_values(strings, jvals), strings)
                        if all(g1[i] or not F.is_word(x["content"]) for i, x in enumerate(strings)):
                            gf = g1
                        else:
                            gf = absorb_labels(match_values(strings, jvals2), strings)
                else:
                    gf = [None] * len(strings)
                for k, s in enumerate(strings):
                    b, f = bucket, field
                    if gf[k]:
                        b, f = "a", gf[k]                 # the same text is held by a front field
                    if bucket == "container":
                        b, f = ("a", jf[k]) if jf[k] else ("b", None)
                    elif bucket == "pic":
                        st = F.toks(s["content"])
                        b, f = (("a", "figure_text") if st and all(t in fig_text.get(p, ()) for t in st)
                                else ("c", "picture_text_not_stored"))
                    for n in wmap.get(s["id"], []):
                        words.setdefault((p, n), dict(b=b, f=f, where=where, tb=tb["id"], line=L["id"],
                                                      s=s["id"], content=s["content"], role=role))
                    line_of_string[s["id"]] = L["id"]
                    if s["box"]:
                        alto_at[p].append((s["box"][0], s["box"][1], F.fold(s["content"] or "").strip(),
                                           dict(b=b, f=f, where=where, tb=tb["id"], line=L["id"], s=s["id"],
                                                content=s["content"], role=role)))
    # platform field per ALTO line / String
    plat_line = {}
    for alid, (bid, rid) in P["lmap"].items():
        if bid and bid in P["blocks"]:
            r = P["blocks"][bid]["role"]
            plat_line[alid] = ("container", r) if r in PLATFORM_CONTAINER else ("a", PLATFORM_SPECIFIC.get(r, r))
        elif rid:
            plat_line[alid] = ("c", P["regions"].get(rid, "region"))
        else:
            plat_line[alid] = ("d", None)

    # ---- per Azure line
    lines_out, leaks = [], []
    flows = defaultdict(lambda: dict(words=0, lines=0, refs=[]))
    tot = Counter()
    wtot = Counter()
    by_field = Counter()
    for p in sorted(read_pages):
        AP = az["pages"].get(p + off)
        if not AP:
            continue
        # platform matching for container lines, one block at a time (values may run over a line break)
        for Lz in AP["lines"]:
            lid = f"{p + off}:{Lz['line_no']}"          # the answer's id (the scan's page)
            ws = []
            for n in range(Lz["first"] or 0, (Lz["last"] or -1) + 1):
                if AP["word_line"].get(n) != Lz["line_no"]:
                    continue
                w = AP["words"][n - 1]
                rec = words.get((p, n))
                if rec is None:
                    rec = elsewhere_in_alto(alto_at, p, w)
                    if rec is not None:
                        wrong_page += 1
                    elif lid in gmath:
                        rec = dict(b="a", f="equation", where="inline_formula", tb=None, line=None, s=None,
                                   content=w["text"], role=None)
                if rec is None:
                    rec = dict(b="d", f="not_in_alto", where="not_in_alto", tb=None, line=None, s=None,
                               content=w["text"], role=None)
                ws.append((n, w, rec))
            real = [(n, w, r) for n, w, r in ws if F.is_word(w["text"] or "")]
            if not real:                       # a line of marks only («*», «-»): not counted
                continue
            # noise: called noise by the model (c) or dropped by it / by the code (d)
            fixed = []
            for n, w, r in real:
                if r["b"] == "noise":
                    if lid in gnoise:
                        r = dict(r, b="c", f="noise")
                    elif lid in groles:
                        r = dict(r, b="d", f="moved_to_noise_by_code")
                    else:
                        r = dict(r, b="d", f="not_placed_by_gemini")
                elif r["b"] == "d" and r["f"] == "not_in_alto":
                    r = dict(r, f="not_in_alto_placed" if lid in groles else "not_in_alto_unplaced")
                fixed.append((n, w, r))
            real = fixed
            bc = Counter(r["b"] for _, _, r in real)
            bucket = max(bc, key=lambda b: (bc[b], -BUCKET_ORDER[b]))
            fc = Counter(r["f"] for _, _, r in real if r["b"] == bucket)
            field = fc.most_common(1)[0][0] if fc else None
            g = groles.get(lid, "noise" if lid in gnoise else "not placed")
            alto_lines = sorted({r["line"] for _, _, r in real if r["line"]})
            pl = Counter()
            for _, _, r in real:
                pb, pf = plat_line.get(r["line"], ("d", None)) if r["line"] else ("d", None)
                pl[(pb, pf)] += 1
            (pb, pf) = pl.most_common(1)[0][0]
            box = [round(Lz["x"]), round(Lz["y"]), round(Lz["w"]), round(Lz["h"])]
            tot[bucket] += 1
            for _, _, r in real:
                wtot[r["b"]] += 1
                if r["b"] == "a":
                    by_field[r["f"]] += 1
            leak_words = [(n, w, r) for n, w, r in real if r["b"] in ("b", "d")]
            if leak_words and all(is_mark(w["text"]) for _, w, _ in leak_words):
                leak_words = []                 # only superscript numbers / stars / lone letters fell through
            if leak_words and all(all(x in F.LABELS for x in F.toks(w["text"])) for _, w, _ in leak_words):
                leak_words = []                 # only label words («Received», «تاريخ القبول:») fell through
            rec = dict(id=f"{p}:{Lz['line_no']}", az_id=lid, page=p, n=Lz["line_no"], text=Lz["text"], box=box, bucket=bucket, field=field,
                       gemini=g, alto=alto_lines, words=len(real), plat=[pb, pf])
            lines_out.append(rec)
            if leak_words:
                leaks.append(leak_entry(rec, leak_words, real, avals, prompt, groles, P, pvals, AP))
            jf = field if bucket == "a" else ({"b": "generic text", "c": "not article text",
                                               "d": "nowhere"}[bucket])
            key = (g, jf, bucket)
            fl = flows[key]
            fl["words"] += len(real)
            fl["lines"] += 1
            if len(fl["refs"]) < 300:
                fl["refs"].append(lid)

    # ---- platform words for container lines (a second pass, with the platform's values)
    plat_leaks = platform_container_check(alto, words, P, pvals, read_pages)
    from answers61 import answer_accounting, bilingual, platform_accounting
    ans = answer_accounting(answers, root, words, lines_out, rules_logs(run, stem), prompt)
    bil = bilingual(answers, root, P, lines_out, leaks)
    plat = platform_accounting(root, P)
    page_size = {p: [round(alto[p]["w"]), round(alto[p]["h"])] for p in alto if p in read_pages}
    return dict(stem=stem, run=run, journal=stem[:4], prompt=prompt, window_offset=off, alto_wrong_page=wrong_page, prompts=prompts, version_id=V["version_id"],
                pages=sorted(read_pages), pages_expected=V["pages_expected"], complete=V["complete"],
                page_size=page_size,
                totals=dict(lines=dict(tot), words=dict(wtot), lines_all=sum(tot.values()),
                            words_all=sum(wtot.values())),
                specific_words=dict(by_field),
                leaks=leaks, platform_leaks=plat_leaks,
                flows=[dict(gemini=k[0], jats=k[1], bucket=k[2], plat=PLATFORM_HOME.get(k[1], k[1]) if k[2] == "a"
                            else ("page_regions" if k[2] == "c" else ("blocks (generic)" if k[2] == "b" else
                                                                         "nowhere")), **v)
                       for k, v in sorted(flows.items(), key=lambda kv: -kv[1]["words"])],
                lines=lines_out, answer=ans, bilingual=bil, platform=plat)


def elsewhere_in_alto(alto_at, p: int, w: dict) -> dict | None:
    """An Azure word the ALTO holds with its own box, but on the next or previous page (a block continued across
    pages drawn on the wrong page): its text and field are there; the ink link points at the wrong page."""
    ft = F.fold(w["text"] or "").strip()
    for q in (p - 1, p + 1):
        for x, y, t, rec in alto_at.get(q, ()):
            if abs(x - w["x"]) < 4 and abs(y - w["y"]) < 4 and t == ft:
                return dict(rec, wrong_page=q)
    return None


def is_mark(text: str) -> bool:
    """A superscript number, a star or a lone letter beside a name («Faisal1 *», «2», «أ»): a mark, not a field."""
    t = F.toks(text)
    return all((x.isdigit() and len(x) <= 2) or len(x) == 1 or len(set(x)) == 1 for x in t)


def leak_entry(rec, leak_words, real, avals, prompt, groles, P, pvals, AP) -> dict:
    lw_text = " ".join(w["text"] for _, w, _ in leak_words)
    where = Counter(r["where"] for _, _, r in leak_words).most_common(1)[0][0]
    bucket = Counter(r["b"] for _, _, r in leak_words).most_common(1)[0][0]
    jf = Counter(r["f"] for _, _, r in leak_words if r["f"]).most_common(1)
    field_guess = F.detect(lw_text, where, rec["page"])
    if where in ("abstract", "keywords") and bucket == "b":
        field_guess = where
    if where == "other" and field_guess == "unclassified":
        field_guess = "other"
    toks = [t for _, w, _ in leak_words for t in F.toks(w["text"])]
    key, share = covered_by(toks, avals)
    if key and field_guess in ("author_name", "unclassified", "date", "other", "journal_info"):
        kf = key_field(key)
        if kf:
            field_guess = kf
    g = rec["gemini"]
    if key:
        kind, why = "mapping", f"Gemini returned it in {key}"
    elif bucket == "b" and g in ("abstract", "keywords", "byline") and field_guess in (
            "abstract", "keywords", "signature", "author_name", "affiliation", "position", "email", "history_date",
            "date", "role", "honorific"):
        kind, why = "mapping", f"Gemini typed the block «{g}»; the code stored it as generic text"
    elif bucket == "d" and rec["gemini"] not in ("not placed", "noise"):
        kind, why = "mapping", f"Gemini placed the line in a «{g}» block; the code dropped it"
    elif field_guess in ("position", "phone_address", "doi_url", "funding_ack", "date", "unclassified", "other") \
            or prompt not in F.ASKED.get(field_guess, set()):
        kind, why = "not_asked", f"prompt {prompt} has no field for «{field_guess}»"
    else:
        kind, why = "gemini_missed", f"prompt {prompt} asks for «{field_guess}»; not in the answer"
    # does the platform hold it anyway (as a field)?
    pkey, _ = covered_by(toks, [(f, F.toks(v)) for f, v in pvals])
    return dict(id=rec["id"], page=rec["page"], n=rec["n"], text=rec["text"], leak_text=lw_text, box=rec["box"],
                alto=rec["alto"], bucket=bucket, where=where, field=field_guess, kind=kind, why=why,
                answer_key=key, gemini=g, words=len(leak_words), line_words=len(real),
                platform_field=pkey, script=F.script(lw_text))


KEY_FIELD = [(r"\.role$", "position"), (r"affiliation$|aff_parts|\.affs\[", "affiliation"), (r"\.email$", "email"),
             (r"\.name$", "author_name"), (r"keywords", "keywords"), (r"history", "history_date"),
             (r"trans_titles", "trans_title"), (r"metadata\.title$", "title"), (r"subtitle", "subtitle"),
             (r"conference", "conference"), (r"thesis", "thesis"), (r"reviewed", "reviewed_work"),
             (r"original", "original"), (r"journal|volume|issue|year|pages", "journal_info")]


def key_field(key: str) -> str | None:
    for rx, f in KEY_FIELD:
        if re.search(rx, key):
            return f
    return None


def platform_container_check(alto, words, P, pvals, read_pages) -> dict:
    """Words the JATS holds as a field and the platform does not (or the reverse), for container blocks."""
    out = Counter()
    by_line = defaultdict(list)
    for (p, n), r in words.items():
        if r["line"]:
            by_line[(p, r["tb"])].append(r)
    for (p, tb), rs in by_line.items():
        roles = {P["blocks"].get((P["lmap"].get(r["line"]) or (None, None))[0], {}).get("role") for r in rs}
        if not roles & PLATFORM_CONTAINER:
            continue
        strings = [dict(content=r["content"]) for r in rs]
        pf = match_values(strings, pvals)
        for r, f in zip(rs, pf):
            if not F.is_word(r["content"]):
                continue
            j = r["f"] if r["b"] == "a" else None
            if j and not f:
                out[f"jats_field_not_in_platform:{j}"] += 1
            elif f and not j:
                out[f"platform_field_not_in_jats:{f}"] += 1
            elif j and f:
                out["both"] += 1
            else:
                out["neither"] += 1
    return dict(out)


AZ = {}


def _work(args):
    stems, wid = args
    con = release()
    vs = {v["stem"]: v for v in current_versions(con)}
    done = 0
    for s in stems:
        try:
            r = audit_article(con, vs[s])
        except Exception as e:  # noqa: BLE001 — one bad article must not stop the run; it is reported
            import traceback
            r = dict(stem=s, error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-2000:])
        (ART / f"{s}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
        done += 1
    return done


def cmd_run(a):
    global AZ
    ART.mkdir(parents=True, exist_ok=True)
    con = release()
    vs = current_versions(con)
    stems = a.stems or [v["stem"] for v in vs]
    if not a.force:
        stems = [s for s in stems if not (ART / f"{s}.json").exists()]
    AZ.update(ink47.azure_paths())
    word = [s for s in stems if s not in AZ]     # exp 70: the Word route has no scan and no Azure lines to account
    if word:
        stems = [s for s in stems if s in AZ]
        (OUT / "skipped_word_route.json").write_text(json.dumps(sorted(word)), encoding="utf-8")
        print(f"{len(word)} articles without an Azure reading (Word route) skipped -> {OUT / 'skipped_word_route.json'}")
    t = time.time()
    if a.workers <= 1:
        _work((stems, 0))
    else:
        from multiprocessing import get_context
        parts = [stems[i::a.workers] for i in range(a.workers)]
        with get_context("fork").Pool(a.workers) as pool:
            pool.map(_work, [(p, i) for i, p in enumerate(parts)])
    print(f"{len(stems)} articles in {time.time() - t:.0f}s -> {ART}")


def cmd_one(a):
    AZ.update(ink47.azure_paths())
    con = release()
    vs = {v["stem"]: v for v in current_versions(con)}
    r = audit_article(con, vs[a.stem])
    print(json.dumps(dict(totals=r["totals"], prompt=r["prompt"]), ensure_ascii=False))
    for lk in r["leaks"]:
        print(lk["id"], lk["bucket"], lk["field"], lk["kind"], "|", lk["leak_text"][:80], "|", lk["why"][:90])
    print(json.dumps(r["answer"]["summary"], ensure_ascii=False)[:2000])
    for d in r["answer"]["values"]:
        if d["status"] not in ("stored",):
            print("  ans", d["key"], d["status"], d.get("where"), "|", str(d.get("value"))[:60], "|", d.get("reason"))
    print(json.dumps(r["bilingual"], ensure_ascii=False))
    print(json.dumps(r["platform"], ensure_ascii=False)[:1500])
    print(json.dumps(r["platform_leaks"], ensure_ascii=False))
    for f in r["flows"][:30]:
        print(f["gemini"], "->", f["jats"], "->", f["plat"], f["bucket"], f["words"], f["lines"])


def configure(release=None, out=None):
    """Point this run (and aggregate61, imported later, through the environment) at another DB / output folder."""
    global RELEASE, OUT, ART
    if release:
        os.environ["AUDIT_RELEASE"] = str(Path(release).resolve())
        RELEASE = Path(release).resolve()
    if out:
        os.environ["AUDIT_OUT"] = str(Path(out).resolve())
        OUT = Path(out).resolve()
        ART = OUT / "articles"


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("run")
    r.add_argument("--stems", nargs="*")
    r.add_argument("--workers", type=int, default=1)
    r.add_argument("--force", action="store_true")
    o = sp.add_parser("one")
    o.add_argument("stem")
    sp.add_parser("aggregate")
    ap.add_argument("--release", help="experiment 65: another platform DB (default AUDIT_RELEASE / the release)")
    ap.add_argument("--out", help="experiment 65: another output folder (default AUDIT_OUT / out/)")
    a = ap.parse_args()
    if a.release or a.out:
        configure(a.release, a.out)
    if a.cmd == "aggregate":
        import aggregate61
        aggregate61.main()
    else:
        {"run": cmd_run, "one": cmd_one}[a.cmd](a)


if __name__ == "__main__":
    main()
