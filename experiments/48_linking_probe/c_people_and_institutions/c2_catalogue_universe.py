"""C2d. A large-scale saturation curve from the catalogue itself: distinct thesis universities (502 $c, folded) as
dissertation records are added in random order (seed 4824), and the corporate-authority hierarchy (110 headings
«country. body. sub-body»). Streams one indexed column; read-only."""
import json, random, re
from collections import Counter
from common48c import mcon, mfold, progress, save
m = mcon()
th = []
for (t,) in m.execute("SELECT thesis FROM records WHERE thesis IS NOT NULL AND thesis <> ''"):
    try:
        c = json.loads(t).get("c")
    except Exception:
        c = None
    if c:
        th.append(re.sub(r"\s+", " ", mfold(c)).strip(" .،-"))
rnd = random.Random(4824); rnd.shuffle(th)
seen, curve = set(), {}
marks = {100, 300, 600, 1000, 3000, 10000, 30000, 100000}
for i, c in enumerate(th, 1):
    seen.add(c)
    if i in marks: curve[i] = len(seen)
curve[len(th)] = len(seen)
cnt = Counter(th)
corp = Counter()
for (n,) in m.execute("SELECT name FROM authors WHERE is_org = 1 AND name LIKE '%. %'"):
    parts = [p.strip() for p in n.split(". ") if p.strip()]
    if len(parts) >= 2: corp[mfold(". ".join(parts[:2]))] += 1
S = dict(theses_with_university=len(th), distinct_university_strings=len(seen), saturation_curve=curve,
         top_universities=cnt.most_common(12), strings_seen_once=sum(1 for v in cnt.values() if v == 1),
         corporate_headings_with_hierarchy=sum(corp.values()), distinct_country_body_pairs=len(corp),
         top_bodies=corp.most_common(10))
save("c2_catalogue_universe.json", S)
progress(f"- c2_catalogue_universe.py: {len(th)} theses, {len(seen)} distinct universities; {len(corp)} corporate bodies")
print(json.dumps(S, ensure_ascii=False, indent=1))
