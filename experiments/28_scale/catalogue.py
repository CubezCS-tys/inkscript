"""Stream the corpus's MARC catalogue once (s3://mandumah-source-docs/metadata/metadata_final.xml.gz, 1.2 GB) and keep
id, year, journal, language and record kind for every record -> out/catalogue.tsv  (the frame for a decade-stratified draw).
    .venv/bin/python experiments/28_scale/catalogue.py
Same reader as experiments/19_azure_map/meta.py, without stopping early.
"""
import re, subprocess, gzip
from pathlib import Path
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
p = subprocess.Popen([str(HERE.parents[1] / ".venv/bin/aws"), "s3", "cp",
                      "s3://mandumah-source-docs/metadata/metadata_final.xml.gz", "-"], stdout=subprocess.PIPE)
def sub(r, tag, code):
    m = re.search(r'<datafield tag="%s"[^>]*>(.*?)</datafield>' % tag, r, re.S)
    if not m: return ""
    m2 = re.search(r'<subfield code="%s">(.*?)</subfield>' % code, m.group(1), re.S)
    return re.sub(r"[\t\n]", " ", m2.group(1).strip()) if m2 else ""
n = 0
with gzip.open(p.stdout, "rt", encoding="utf-8") as f, open(OUT / "catalogue.tsv.part", "w") as o:
    rec = []
    for line in f:
        if line.startswith("<record"): rec = [line]; continue
        rec.append(line)
        if line.startswith("</record>"):
            r = "".join(rec); rec = []
            m = re.search(r'<subfield code="u">([^<]+)\.pdf</subfield>', r)
            if not m: continue
            o.write("\t".join([m.group(1), sub(r, "260", "c"), sub(r, "773", "s"), sub(r, "041", "a"), sub(r, "336", "b")]) + "\n")
            n += 1
            if n % 100000 == 0: print(n, flush=True)
(OUT / "catalogue.tsv.part").rename(OUT / "catalogue.tsv")
print("records", n)
