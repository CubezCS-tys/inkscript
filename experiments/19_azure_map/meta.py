"""Stream the corpus's MARC metadata (s3://mandumah-source-docs/metadata/metadata_final.xml.gz, 1.2 GB) once and keep
the records of the sampled ids: journal, year, country, subject, language.  -> out/meta.json
    .venv/bin/python meta.py
"""
import json, re, subprocess, gzip
from pathlib import Path
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
want = set(l.strip() for l in open(OUT / "ids.txt") if l.strip())
p = subprocess.Popen([str(HERE.parents[1] / ".venv/bin/aws"), "s3", "cp", "s3://mandumah-source-docs/metadata/metadata_final.xml.gz", "-"], stdout=subprocess.PIPE)
found = {}; rec = []
def sub(r, tag, code):
    m = re.search(r'<datafield tag="%s"[^>]*>(.*?)</datafield>' % tag, r, re.S)
    if not m: return None
    m2 = re.search(r'<subfield code="%s">(.*?)</subfield>' % code, m.group(1), re.S)
    return m2.group(1).strip() if m2 else None
with gzip.open(p.stdout, "rt", encoding="utf-8") as f:
    for line in f:
        if line.startswith("<record"): rec = [line]; continue
        rec.append(line)
        if line.startswith("</record>"):
            r = "".join(rec); m = re.search(r'<subfield code="u">([^<]+)\.pdf</subfield>', r)
            if m and m.group(1) in want:
                found[m.group(1)] = dict(journal=sub(r, "773", "s"), journal_en=sub(r, "773", "t"), year=sub(r, "260", "c"),
                                         country=sub(r, "044", "b"), lang=sub(r, "041", "a"), field=sub(r, "773", "6"),
                                         kind=sub(r, "336", "b"), title=sub(r, "245", "a"))
                if len(found) == len(want): break
            rec = []
p.kill()
json.dump(found, open(OUT / "meta.json", "w"), ensure_ascii=False, indent=1)
print(len(found), "of", len(want), "ids found in the metadata")
