"""Experiment 54 step 3: per EduSearch journal (codes in out/articles.tsv): the share of research articles among all its
records 2010-2025, its fields_of_study, its subject terms (research articles 2010-2025) and the authority ids of its
authors (research articles 2000-2025). marc.db read-only, streamed per journal through the journal index.
-> out/journals.json"""
import collections, csv, json, sqlite3
from pathlib import Path
HERE = Path(__file__).resolve().parent
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
R = "بحوث ومقالات"
codes = sorted({r["journal_code"] for r in csv.DictReader(open(HERE / "out/articles.tsv"), delimiter="\t")})
c = sqlite3.connect(MARC, uri=True); q = c.cursor()
out = {}
for code in codes:
    types = collections.Counter(); fos = collections.Counter(); subj = collections.Counter(); auth = set()
    nauth = 0; edu = 0
    for rec, typ, y, f, db in c.execute(
            "select rec, type, year_int, fields_of_study, databases from records where journal_code = ?", (code,)):
        if y is None or not (2000 <= y <= 2025):
            continue
        if 2010 <= y: types[typ or "-"] += 1
        if typ != R or "EduSearch" not in (db or ""):
            continue
        if 2010 <= y:
            for t in (f or "").split(" | "):
                if t.strip(): fos[t.strip()] += 1
            for (t,) in q.execute("select term from subjects where rec = ?", (rec,)):
                if t: subj[t.strip()] += 1
        for (a,) in q.execute("select authority_id from authors where rec = ? and authority_id is not null and authority_id != ''", (rec,)):
            auth.add(a); nauth += 1
    out[code] = dict(types=dict(types), fos=fos.most_common(8), subjects=dict(subj.most_common(300)),
                     authority_ids=sorted(auth), bylines_with_id=nauth)
(HERE / "out/journals.json").write_text(json.dumps(out, ensure_ascii=False))
print(len(out), "journals")
