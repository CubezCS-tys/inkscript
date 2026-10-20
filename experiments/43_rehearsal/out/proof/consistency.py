"""Run-to-run variance: two v3.3-low runs of the same articles (out/stepEF/g0_v33 vs out/g0_v33_low_rep), word-level block-kind agreement."""
import difflib, json, re, sys
from bs4 import BeautifulSoup
from pathlib import Path
O = Path(__file__).resolve().parents[1]
A, B = O/'stepEF/g0_v33/views/mirror', O/'g0_v33_low_rep/views/mirror'
def words(f):
    s = BeautifulSoup(f.read_text(), 'html.parser'); out = {}
    for sec in s.select('[data-p]'):
        p = int(sec['data-p']); seq = []; nb = 0
        for b in sec.select('.lpage > .pc'):
            for o in b.select('span.ob,button'): o.decompose()
            k = b.get('data-t') or 'noise'; ws = b.get_text(' ').split(); nb += 1
            seq += [(w, k) for w in ws]
        out[p] = (seq, nb)
    return out
res = {}; T = dict(words=0, same=0, kind=0, only=0, blocks_a=0, blocks_b=0)
for f in sorted(B.glob('*.html')):
    if not (A/f.name).exists(): continue
    a, b = words(A/f.name), words(f); r = dict(words=0, same=0, kind=0, only=0, pages_diff_blocks=0, pages=0)
    for p in a:
        sa, na = a[p]; sb, nb = b.get(p, ([], 0))
        r['pages'] += 1; r['pages_diff_blocks'] += (na != nb); T['blocks_a'] += na; T['blocks_b'] += nb
        m = difflib.SequenceMatcher(None, [w for w, _ in sa], [w for w, _ in sb], autojunk=False)
        for i, j, n in m.get_matching_blocks():
            for t in range(n):
                r['same' if sa[i+t][1] == sb[j+t][1] else 'kind'] += 1
        matched = sum(n for _, _, n in m.get_matching_blocks())
        r['only'] += (len(sa) - matched) + (len(sb) - matched); r['words'] += max(len(sa), len(sb))
    res[f.stem] = r
    for k in ('words', 'same', 'kind', 'only'): T[k] += r[k]
json.dump(dict(articles=res, total=T), open(O/'proof/consistency.json', 'w'), indent=1)
print(json.dumps(res, indent=1)); print(T)
