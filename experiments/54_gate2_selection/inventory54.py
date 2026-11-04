"""Experiment 54 step 1: every EduSearch research article (type 'بحوث ومقالات', 2000-2025) in the catalogue, with its
route: scan (main bucket), word (a Word original on the server and/or a legacy PDF, no scan), or nowhere.
marc.db read-only, streamed. -> out/articles.tsv (one line per record)."""
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"

main = set(open(EXP / "44_bucket_map/out/ids_main.txt").read().split())
legacy = set(open(EXP / "44_bucket_map/out/ids_legacy.txt").read().split())
word = {}
for line in open(EXP / "53_word_route/out/word_files_all.txt"):
    folder, name = line.split()
    stem, ext = name.rsplit(".", 1)
    word.setdefault(stem, set()).add(f"{folder}/{ext}")

c = sqlite3.connect(MARC, uri=True)
q = c.cursor()
out = open(HERE / "out/articles.tsv", "w")
out.write("rec\tjournal_code\tjournal\tcountry\tyear\tpage_first\tpage_last\tstems\troute\tword\tlegacy\n")
n = 0
for rec, jc, j, ctry, y, pf, pl in c.execute(
        "select rec, journal_code, journal, country, year_int, page_first, page_last from records "
        "where type = 'بحوث ومقالات' and databases like '%EduSearch%' and year_int between 2000 and 2025"):
    stems = [s for (s,) in q.execute("select stem from pdf_ids where rec = ? order by seq", (rec,))]
    sc = any(s in main for s in stems)
    wd = sorted({w for s in stems for w in word.get(s, ())})
    lg = any(s in legacy for s in stems)
    route = "scan" if sc else ("word" if wd else ("legacy" if lg else "nowhere"))
    out.write("\t".join(map(str, [rec, jc, (j or "").replace("\t", " "), ctry, y, pf, pl, ",".join(stems), route,
                                   ",".join(wd), int(lg)])) + "\n")
    n += 1
print(n, "records")
