"""All journal title forms in the catalogue (773 $s / $t|$e / $f, journal code, ISSN), with record counts."""
import json, collections
from q import marc
m = marc()
J = collections.defaultdict(lambda: dict(forms=collections.Counter(), issn=collections.Counter(), n=0, types=collections.Counter()))
for code, j, je, jr, issn, typ, n in m.execute(
        "select journal_code, journal, journal_en, journal_romanised, issn, type, count(*) from records "
        "where journal_code is not null and journal_code <> '' group by 1,2,3,4,5,6"):
    d = J[code]; d["n"] += n; d["types"][typ] += n
    for f in (j, je, jr):
        if f: d["forms"][f] += n
    if issn: d["issn"][issn] += n
out = {k: dict(n=v["n"], forms=v["forms"].most_common(), issn=v["issn"].most_common(), types=v["types"].most_common()) for k, v in J.items()}
json.dump(out, open("/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/catalogue_journals.json", "w"), ensure_ascii=False)
print(len(out), "journal codes;", sum(len(v["forms"]) for v in out.values()), "forms")
