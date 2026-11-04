"""Frequent name tokens in the catalogue's author headings (given names, particles): not evidence of the same person."""
import collections, json
from q import marc
m = marc(); C = collections.Counter(); n = 0
for (nf,) in m.execute("select name_folded from authors"):
    for t in set((nf or "").replace("،", " ").replace(",", " ").split()): C[t] += 1
    n += 1
json.dump(dict(n=n, top=C.most_common(400)), open("/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/name_token_freq.json", "w"), ensure_ascii=False)
print(n, C.most_common(60))
