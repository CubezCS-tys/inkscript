"""Experiment 56, step 1: evidence packets for the librarian (read-only on the release and the catalogue extract).

One packet per printed affiliation (every mention of the shown versions) with everything a person would look at:
- the printed statement and its parts (org, faculty, department, city, country as the reader gave them);
- the article (stem, journal, year), the author (byline as printed, person id);
- the same author's other affiliation statements in the same article (the other script, a second affiliation) and
  in other articles (by person id);
- what the machine linked it to (org / faculty / department rows of `institutions`, with their names and country);
- where the statement sits on the scan (Azure lines near the byline that carry its words, for the ink crop);
- catalogue hits: MARC 502 $c (the university that granted a thesis, with its country 502 $g) and 110 corporate
  headings «البلد. الهيئة. الوحدة» whose body matches the printed organisation.

Output: out/packets56.jsonl (one JSON per affiliation), out/institutions56.jsonl (the 701 machine rows with their
names, links and articles), out/view56.txt (a compact listing to read).

    python3 experiments/56_librarian_institutions/build56.py [--db RELEASE]
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE.parents[0] / "46_platform_db"))
from common46 import fold, key  # noqa: E402

RELEASES = Path.home() / "data/desk/releases"


def newest_release() -> Path:
    return sorted(RELEASES.glob("R*.db"))[-1]


def aff_key(stem, pos, scr, seq) -> str:
    """A stable key for one printed affiliation: article, byline position, script, its order under the byline."""
    return f"aff:{stem}|b{pos}|{scr}|a{seq}"


def toks(s: str) -> set:
    return {w for w in key(s).split() if len(w) > 1}


ORG_HEAD = re.compile(r"(جامع|univ|وزار|ministr|مركز|cent|معهد|institut|اكاديمي|academ|هيئ|مجلس|council|"
                      r"مدرس|school|أكاديمي|ecole|école|lyc)", re.I)


def org_tokens(s: str) -> set:
    """The distinctive words of an organisation name (no generic head words)."""
    stop = {"جامعه", "الجامعه", "university", "of", "the", "de", "la", "le", "des", "du", "d", "universite", "و",
            "كليه", "college", "faculty", "في", "ب", "and"}
    out = set()
    for w in key(s).split():
        w2 = re.sub(r"^(وال|بال|لل|ال)", "", w) if len(w) > 4 else w
        if w not in stop and w2 not in stop and len(w2) > 1:
            out.add(w2)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else newest_release()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    OUT.mkdir(exist_ok=True)

    rows = [dict(r) for r in con.execute("""
        SELECT am.aff_pk, am.seq, am.printed, am.org_text, am.faculty_text, am.faculty_printed, am.dept_text, am.city,
               am.country_printed, am.country_code, am.kind, am.assembled, am.position_title,
               b.mention_pk, b.byline_pos, b.script, b.printed AS byline, b.name_text, b.email, b.block_id,
               ia.anchor_key AS byline_anchor, ia.page AS byline_page, ia.y AS byline_y,
               v.stem, v.version_id, v.run, d.pub_id, p.journal_id, p.year_shown
        FROM affiliation_mentions am JOIN byline_mentions b USING (mention_pk)
        JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
        JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
        LEFT JOIN ink_anchors ia ON ia.anchor_pk = b.anchor_pk
        ORDER BY v.stem, b.byline_pos, b.script, am.seq""")]
    person = {r[0]: r[1] for r in con.execute("""SELECT am.mention_pk, a.person_id FROM authorship_mentions am
                                                JOIN authorships a USING (authorship_pk)""")}
    pname = {r[0]: r[1] or r[2] for r in con.execute(
        "SELECT person_id, preferred_name_ar, preferred_name_lat FROM persons")}
    jname = {}
    for r in con.execute("SELECT journal_id, title FROM journal_titles ORDER BY is_chosen DESC, n DESC"):
        jname.setdefault(r[0], r[1])
    iname = defaultdict(list)
    for r in con.execute("SELECT inst_id, name, script, n_seen, type FROM institution_names ORDER BY n_seen DESC"):
        iname[r[0]].append(dict(name=r[1], script=r[2], n=r[3], type=r[4]))
    inst = {r["inst_id"]: dict(r) for r in con.execute("SELECT * FROM institutions")}
    natkey = {r[0]: r[1] for r in con.execute("SELECT public_id, natural_key FROM id_registry WHERE kind = 'institution'")}
    links = defaultdict(list)
    for r in con.execute("SELECT aff_pk, inst_id, level, method FROM affiliation_links"):
        links[r[0]].append(dict(inst_id=r[1], level=r[2], method=r[3]))

    # the catalogue extract (marc_authority56.py)
    mc = sqlite3.connect(OUT / "marc_inst56.db")
    thesis = defaultdict(Counter)             # folded university -> country counts
    thesis_name = {}
    for u, c, f, n in mc.execute("SELECT univ, country, faculty, n FROM thesis_unis WHERE univ IS NOT NULL"):
        k = key(u)
        thesis[k][c or "?"] += n
        thesis_name.setdefault(k, u)
    corp = [(h, aid, n) for h, aid, n in mc.execute("SELECT heading, authority_id, n FROM corp")]
    corp_parts = [(h, aid, n, [key(p) for p in re.split(r"\s*\.\s+", h)]) for h, aid, n in corp]

    def catalogue_hits(name: str) -> dict:
        k = key(name)
        out = dict(thesis=[], corp=[])
        if not k:
            return out
        kk = re.sub(r"\bال", "", k)
        for tk, cs in thesis.items():
            if tk == k or re.sub(r"\bال", "", tk) == kk:
                out["thesis"].append(dict(univ=thesis_name[tk], countries=dict(cs.most_common(3))))
        for h, aid, n, parts in corp_parts:
            if any(p == k for p in parts[1:]) or (len(parts) == 1 and parts[0] == k):
                out["corp"].append(dict(heading=h, authority_id=aid, n=n))
        out["corp"] = sorted(out["corp"], key=lambda x: -x["n"])[:5]
        return out

    # where each affiliation sits on the scan: Azure lines on the byline's page sharing its words
    lines_by_page = defaultdict(list)
    stems = {r["stem"] for r in rows}
    for r in con.execute("SELECT stem, page, line_no, y, text FROM azure_lines WHERE page <= 3"):
        if r[0] in stems:
            lines_by_page[(r[0], r[1])].append((r[2], r[3], r[4]))
    lmap = {}
    for r in con.execute("""SELECT lm.version_id, lm.page, lm.azure_line_no, lm.alto_line_id FROM line_map lm
                            JOIN versions v ON v.version_id = lm.version_id AND v.is_current = 1
                            WHERE lm.page <= 3 AND lm.azure_line_no IS NOT NULL"""):
        lmap[(r[0], r[1], r[2])] = r[3]

    def locate(r) -> dict | None:
        want = toks(r["printed"])
        if not want:
            return None
        pages = [r["byline_page"]] if r["byline_page"] else [1, 2]
        best = None
        for pg in pages:
            ls = lines_by_page.get((r["stem"], pg), [])
            hit = [(no, y, t, len(toks(t) & want)) for no, y, t in ls]
            hit = [h for h in hit if h[3] >= max(1, min(2, len(toks(h[2]))))]
            if not hit:
                continue
            # keep the run of hit lines closest to the byline
            hit.sort(key=lambda h: abs((h[1] or 0) - (r["byline_y"] or 0)) if r["byline_y"] else h[0])
            got, cover = [], set()
            for h in hit:
                if len(got) >= 4:
                    break
                new = toks(h[2]) & want - cover
                if new:
                    got.append(h)
                    cover |= toks(h[2]) & want
            share = len(cover) / len(want)
            if share >= 0.5 and (best is None or share > best["share"]):
                ids = [lmap.get((r["version_id"], pg, h[0])) for h in sorted(got)]
                best = dict(page=pg, azure_lines=[h[0] for h in sorted(got)],
                            alto_lines=[i for i in ids if i and re.fullmatch(r"p\d+b\d+l\d+", i)],   # the crop route's line ids
                            share=round(share, 2))
        return best

    by_person = defaultdict(list)
    for r in rows:
        pid = person.get(r["mention_pk"])
        r["person_id"] = pid
        if pid:
            by_person[pid].append(r)
    by_article_person = defaultdict(list)
    for r in rows:
        by_article_person[(r["stem"], r["person_id"] or f"pos{r['byline_pos']}")].append(r)

    def inst_view(iid):
        i = inst.get(iid) or {}
        return dict(inst_id=iid, kind=i.get("kind"), country=i.get("country_code"), parent_id=i.get("parent_id"),
                    key=natkey.get(iid), names=[n["name"] for n in iname.get(iid, [])][:6])

    packets = []
    for r in rows:
        k = aff_key(r["stem"], r["byline_pos"], r["script"], r["seq"])
        same = [dict(key=aff_key(x["stem"], x["byline_pos"], x["script"], x["seq"]), printed=x["printed"],
                     script=x["script"]) for x in by_article_person[(r["stem"], r["person_id"] or f"pos{r['byline_pos']}")]
                if x["aff_pk"] != r["aff_pk"]]
        other = [dict(stem=x["stem"], printed=x["printed"]) for x in by_person.get(r["person_id"], [])
                 if x["stem"] != r["stem"]][:6]
        ml = {}
        for l in links.get(r["aff_pk"], []):
            ml[l["level"]] = dict(inst_view(l["inst_id"]), method=l["method"])
        cand_names = [s for s in [*(r["org_text"] or "").split(" | ")] if s]
        packets.append(dict(
            key=k, aff_pk=r["aff_pk"], stem=r["stem"], journal_id=r["journal_id"], journal=jname.get(r["journal_id"]),
            year=r["year_shown"], run=r["run"], author=dict(printed=r["byline"], name=r["name_text"], script=r["script"],
                                                            person_id=r["person_id"], person=pname.get(r["person_id"]),
                                                            byline_anchor=r["byline_anchor"], email=r["email"]),
            printed=r["printed"], parts=dict(org=r["org_text"], faculty=r["faculty_printed"] or r["faculty_text"],
                                             dept=r["dept_text"], city=r["city"], country=r["country_printed"],
                                             country_code=r["country_code"], position=r["position_title"]),
            kind=r["kind"], assembled=r["assembled"], same_article=same, other_articles=other, machine=ml,
            ink=locate(r), catalogue={n: catalogue_hits(n) for n in cand_names}))
    with open(OUT / "packets56.jsonl", "w", encoding="utf-8") as f:
        for p in packets:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # the machine's institution rows
    arts = defaultdict(set)
    affs_of = defaultdict(list)
    for p in packets:
        for lvl, m in p["machine"].items():
            arts[m["inst_id"]].add(p["stem"])
            affs_of[m["inst_id"]].append(p["key"])
    with open(OUT / "institutions56.jsonl", "w", encoding="utf-8") as f:
        for iid, i in sorted(inst.items()):
            f.write(json.dumps(dict(inst_view(iid), source=i["source"], all_names=iname.get(iid, []),
                                    articles=sorted(arts[iid]), affiliations=affs_of[iid]), ensure_ascii=False) + "\n")

    # a compact listing to read
    with open(OUT / "view56.txt", "w", encoding="utf-8") as f:
        for n, p in enumerate(packets):
            m = p["machine"]
            o = m.get("org")
            fa = m.get("faculty")
            f.write(f"{n:03d} {p['key']} [{p['journal_id']} {p['year']}] {p['author']['name']}\n")
            f.write(f"    P: {p['printed']}\n")
            f.write(f"    parts: org={p['parts']['org']!s} | fac={p['parts']['faculty']!s} | dept={p['parts']['dept']!s}"
                    f" | city={p['parts']['city']!s} | ctry={p['parts']['country']!s}\n")
            f.write(f"    M: org={o['names'][0] if o and o['names'] else None} ({o['inst_id'] if o else ''},{o['country'] if o else ''})"
                    f" fac={fa['names'][0] if fa and fa['names'] else None} ({fa['key'] if fa else ''})\n")
            if p["same_article"]:
                f.write("    same: " + " || ".join(x["printed"] for x in p["same_article"]) + "\n")
            if p["other_articles"]:
                f.write("    other: " + " || ".join(f"{x['stem']}: {x['printed']}" for x in p["other_articles"][:3]) + "\n")
            cat = [f"{t['univ']}={t['countries']}" for c in p["catalogue"].values() for t in c["thesis"]]
            if cat:
                f.write("    cat: " + "; ".join(cat) + "\n")
    print(dict(packets=len(packets), located=sum(1 for p in packets if p["ink"]), db=str(db)))


if __name__ == "__main__":
    sys.exit(main())
