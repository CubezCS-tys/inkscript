"""C1b-2. Hard names: how many catalogue authority ids could be the person behind a printed name, for common patterns;
and catalogue-wide homonymy (heading keys held by 2+ authority ids), from the heading-key index (read-only)."""
import json
from collections import Counter
from common48c import exact_holders, given_surname, hcon, is_arab, latin_loose_holders, loose_holders, mcon, name_key, save, progress
h, m = hcon(), mcon()
names = ["محمد أحمد", "أحمد علي", "محمد علي", "محمد عمران", "محمد شاهين", "عبد الله عسكر", "محمد التهامي",
         "محمد كامل حسين", "عبد العزيز الشناوي", "Ahmed, M.", "M. Ahmed", "Mohamed Ahmed", "Ali, A.", "Khalid Talal Alotaibi",
         "S. Ibrahim", "Hassan, M."]
rows = []
for n in names:
    g, s = given_surname(n)
    ex = exact_holders(h, [name_key(n)]).get(name_key(n), set())
    lo = loose_holders(m, g, s) if is_arab(n) else latin_loose_holders(h, g, s)
    rows.append(dict(printed=n, exact_holders=len(ex), loose_holders=len(lo)))
dist = Counter()
for (c,) in h.execute("SELECT count(*) FROM k GROUP BY key"):
    dist["1" if c == 1 else "2" if c == 2 else "3-5" if c <= 5 else "6-20" if c <= 20 else ">20"] += 1
top = [dict(key=k, ids=c) for k, c in h.execute("SELECT key, count(*) c FROM k GROUP BY key ORDER BY c DESC LIMIT 15")]
S = dict(examples=rows, heading_keys_by_number_of_authority_ids=dict(dist), most_shared_keys=top,
         note="heading key = folded «given surname» without spaces (experiment 47's heading_key), over Arabic and Latin headings")
save("c1_hard_examples.json", S)
progress("- c1_hard_examples.py done")
print(json.dumps(S, ensure_ascii=False, indent=1))
