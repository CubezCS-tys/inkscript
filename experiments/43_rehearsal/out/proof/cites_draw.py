"""Draw 80 random parsed citations (element-citation) from the exam masters, seed fixed; print printed string + fields."""
import json, random, re, xml.etree.ElementTree as ET
from pathlib import Path
M = Path(__file__).resolve().parents[1]/'v33_300b_final/masters'
SEED = 20261022
def txt(e): return re.sub(r'\s+', ' ', ''.join(e.itertext())).strip()
items = []
for f in sorted(M.glob('*.jats.xml')):
    t = ET.parse(f); stem = f.name[:-9]
    parent = {c: p for p in t.iter() for c in p}
    for ec in t.iter('element-citation'):
        p = parent[ec]
        if p.tag == 'ref':
            mc = p.find('mixed-citation'); printed = txt(mc) if mc is not None else ''; where = 'ref ' + p.get('id','')
        else:  # parsed-citations p inside fn
            fn = parent[p]; ps = [x for x in fn.findall('p') if x.get('content-type') != 'parsed-citations']
            printed = ' '.join(txt(x) for x in ps); where = 'fn ' + fn.get('id','')
            n = len(p.findall('element-citation'))
            if n > 1: where += f' ({list(p).index(ec)+1} of {n})'
        fields = []
        for c in ec:
            if c.tag == 'person-group':
                fields.append((c.get('person-group-type','')+'s', ' ; '.join(txt(n) for n in c)))
            else:
                fields.append((c.tag + (('/' + c.get('pub-id-type')) if c.get('pub-id-type') else ''), txt(c)))
        items.append(dict(stem=stem, where=where, type=ec.get('publication-type'), printed=printed, fields=fields))
rng = random.Random(SEED)
pick = rng.sample(range(len(items)), 80)
out = [dict(i=k+1, **items[j]) for k, j in enumerate(pick)]
json.dump(dict(seed=SEED, population=len(items), sample=out), open('cites_draw.json','w'), ensure_ascii=False, indent=1)
print(len(items))
