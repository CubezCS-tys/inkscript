#!/usr/bin/env python3
"""Experiment 97: choose and lock the exam articles and pages, and write the neutral packets the keyers work from.

A packet holds only what is independent of our parsing: the page images and Azure's raw lines (number, text, box).
The page strata (table / reference / footnote page) are picked with our own block roles, which is a known bias
(pages where we FOUND a table); the random body page of every article is the unbiased sample for what we missed.
Run once:  nice -n 19 python3 sample97.py     (refuses to overwrite the lock)
"""
import json, os, random, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__))
DB = "/home/appuser/data/desk/releases/R20261104T151029.db"
PAGES = "/home/appuser/inkscript/experiments/43_rehearsal/out/pages/"
LOCK = f"{HERE}/LOCKED_EVAL.json"
JOURNALS = ["0013", "0097", "0130", "0165", "0246", "0840", "1001"]
PER_JOURNAL, WIDE, SEED = 6, 18, 97
if os.path.exists(LOCK):
    raise SystemExit("LOCKED_EVAL.json exists: the exam set is frozen")
c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
rows = c.execute("""select j.code, v.stem, v.version_id, v.run, p.doc_type, v.pages_expected
    from versions v join runs r on r.run = v.run join documents d on d.stem = v.stem
    join publications p on p.pub_id = d.pub_id join journals j on j.journal_id = p.journal_id
    where v.is_current = 1 and v.content_in_db = 1 and v.complete = 1 and r.model = 'gemini-4-argon'
    order by v.stem""").fetchall()
rows = [r for r in rows if os.path.exists(f"{PAGES}{r[1]}_p001.jpg")]
rnd = random.Random(SEED)
chosen = []
for code in JOURNALS:
    pool = [r for r in rows if r[0] == code]
    chosen += rnd.sample(pool, PER_JOURNAL)
wide = [r for r in rows if r[0] not in JOURNALS]
seen, pick = set(), []
for r in rnd.sample(wide, len(wide)):          # one article per journal in the wide part
    if r[0] not in seen:
        seen.add(r[0]); pick.append(r)
    if len(pick) == WIDE:
        break
chosen += pick
arts = []
for code, stem, vid, run, doc_type, npages in chosen:
    roles = {}
    for page, role in c.execute("select page, role from blocks where version_id = ?", (vid,)):
        roles.setdefault(page, set()).add(role)
    allp = [r[0] for r in c.execute("select page from pages where stem = ? order by page", (stem,))]
    def first(pred, avoid):
        cand = [p for p in allp if p not in avoid and pred(roles.get(p, set()))]
        return rnd.choice(cand) if cand else None
    sel = {"front": allp[0]}
    used = {allp[0]}
    for name, pred in [("table", lambda s: "table-cell" in s), ("refs", lambda s: "ref" in s),
                       ("notes", lambda s: "footnote" in s or "endnote" in s),
                       ("body", lambda s: True)]:
        p = first(pred, used)
        if p is not None:
            sel[name] = p; used.add(p)
    arts.append(dict(stem=stem, journal=code, version_id=vid, run=run, doc_type=doc_type, n_pages=len(allp), pages=sel))
    pk = f"{HERE}/out/packets/{stem}"
    os.makedirs(pk, exist_ok=True)
    pages = []
    for p in allp:
        w, h, key = c.execute("select width_px, height_px, page_image_key from pages where stem = ? and page = ?", (stem, p)).fetchone()
        lines = [dict(line=n, text=t, x=x, y=y, w=ww, h=hh) for n, t, x, y, ww, hh in c.execute(
            "select line_no, text, x, y, w, h from azure_lines where stem = ? and page = ? order by line_no", (stem, p))]
        pages.append(dict(page=p, image=PAGES + key, width_px=w, height_px=h, azure_lines=lines))
    json.dump(dict(stem=stem, journal=code, exam_pages=sel, pages=pages), open(f"{pk}/packet.json", "w"), ensure_ascii=False, indent=0)
json.dump(dict(schema="eval97-1", release="R20261104T151029", seed=SEED, per_journal=PER_JOURNAL, wide=WIDE, articles=arts),
          open(LOCK, "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(len(arts), "articles;", Counter(k for a in arts for k in a["pages"]), "; pages total", sum(a["n_pages"] for a in arts))
