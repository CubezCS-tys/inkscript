"""The catalogue's title (245 $a, $b) and authors (100 $a, 700 $a) for the set's documents, a truth to score the
JATS title and authors against (the catalogue is made by people from the article; spelling may differ).
    .venv/bin/python experiments/28_scale/catalogue_titles.py   -> out/catalogue_titles.json
"""
import json, os, re, subprocess, gzip
from pathlib import Path
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
want = set(os.listdir(OUT / "azure"))
p = subprocess.Popen([str(HERE.parents[1] / ".venv/bin/aws"), "s3", "cp",
                      "s3://mandumah-source-docs/metadata/metadata_final.xml.gz", "-"], stdout=subprocess.PIPE)
def subs(r, tag, code):
    out = []
    for m in re.finditer(r'<datafield tag="%s"[^>]*>(.*?)</datafield>' % tag, r, re.S):
        out += [x.strip() for x in re.findall(r'<subfield code="%s">(.*?)</subfield>' % code, m.group(1), re.S)]
    return out
found = {}
with gzip.open(p.stdout, "rt", encoding="utf-8") as f:
    rec = []
    for line in f:
        if line.startswith("<record"): rec = [line]; continue
        rec.append(line)
        if line.startswith("</record>"):
            r = "".join(rec); rec = []
            m = re.search(r'<subfield code="u">([^<]+)\.pdf</subfield>', r)
            if m and m.group(1) in want:
                found[m.group(1)] = dict(title=" ".join(subs(r, "245", "a") + subs(r, "245", "b")),
                                         authors=subs(r, "100", "a") + subs(r, "700", "a"),
                                         journal=(subs(r, "773", "s") or [""])[0], year=(subs(r, "260", "c") or [""])[0],
                                         country=(subs(r, "044", "b") or [""])[0], field=(subs(r, "773", "6") or [""])[0])
                if len(found) == len(want): break
p.kill()
json.dump(found, open(OUT / "catalogue_titles.json", "w"), ensure_ascii=False, indent=1)
print(len(found), "of", len(want))
