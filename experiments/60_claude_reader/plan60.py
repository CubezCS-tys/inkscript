"""Experiment 60: the test-1 plan (no calls): the 60 proof-page + 30 metadata articles chained up to their last sampled page, plus the chunks holding the sampled citations in draw order until 900 pages -> out/plan_t1.json, out/plan_t1_cites.json."""
import json,re,glob,os
from collections import defaultdict
B='/home/appuser/inkscript/experiments/43_rehearsal/'
arts={a['stem']:a for a in json.load(open(B+'sample43b.json'))['articles']}
raw=B+'out/v33_300b_fix3/raw/'
ch=defaultdict(list); stat={}
for f in sorted(glob.glob(raw+'*.json')):
    if f.endswith('.failed.json'): continue
    r=json.load(open(f)); ch[r['stem']].append((r['first'],r['last'])); stat[(r['stem'],r['first'])]=(r.get('tin'),r.get('tout'),r['pages'])
for k in ch: ch[k].sort()
need=defaultdict(int)  # stem -> last page needed
d=json.load(open(B+'out/proof/draw.json'))['draw']
for x in d: need[x['stem']]=max(need[x['stem']],max(x['pages']))
for x in json.load(open(B+'out/proof/meta_draw.json')): need[x['stem']]=max(need[x['stem']],1)
for x in json.load(open(B+'out/proof/cites_draw.json'))['sample']:
    m=re.search(r'fn-p(\d+)',x['where'])
    p=int(m.group(1)) if m else 999
    need[x['stem']]=max(need[x['stem']],p)
tot=0; totall=0; nch=0
for s,p in need.items():
    cs=ch[s]; 
    use=[c for c in cs if c[0]<=p]  # prefix chunks up to the one containing p
    tot+=sum(c[1]-c[0]+1 for c in use); nch+=len(use)
    totall+=sum(c[1]-c[0]+1 for c in cs)
print(len(need),'articles; prefix pages',tot,'chunks',nch,'; whole pages',totall)
tin=sum(v[0] for v in stat.values()); tout=sum(v[1] for v in stat.values()); pg=sum(v[2] for v in stat.values())
print('argon per page tin',tin/pg,'tout',tout/pg)
def prefix(s,p):
    return [c for c in ch[s] if c[0]<=p]
def pages(cs): return sum(c[1]-c[0]+1 for c in cs)
P={}
for x in d: P[x['stem']]=max(P.get(x['stem'],0),max(x['pages']))
M={x['stem']:1 for x in json.load(open(B+'out/proof/meta_draw.json'))}
Cn={}
for x in json.load(open(B+'out/proof/cites_draw.json'))['sample']:
    m=re.search(r'fn-p(\d+)',x['where']); p=int(m.group(1)) if m else 999
    Cn[x['stem']]=max(Cn.get(x['stem'],0),p)
pp=sum(pages(prefix(s,p)) for s,p in P.items()); print('pages pack',len(P),pp)
mm=sum(pages(prefix(s,1)) for s in M); print('meta',len(M),mm, 'overlap with P',len(set(M)&set(P)))
u={}
for dd in (P,M): 
    for s,p in dd.items(): u[s]=max(u.get(s,0),p)
print('P+M', len(u), sum(pages(prefix(s,p)) for s,p in u.items()))
cc=sum(pages(prefix(s,p)) for s,p in Cn.items()); print('cites',len(Cn),cc,'overlap',len(set(Cn)&set(u)))
# cites whose chunk already covered by u
cov=0;extra=[]
cites=json.load(open(B+'out/proof/cites_draw.json'))['sample']
for x in cites:
    m=re.search(r'fn-p(\d+)',x['where']); p=int(m.group(1)) if m else 999
    s=x['stem']
    have=prefix(s,u.get(s,0)) if s in u else []
    if any(c[0]<=p<=c[1] for c in have): cov+=1
    else: extra.append((s,p,pages(prefix(s,p))-pages(have)))
print('cites covered by P+M',cov, 'extra', len(extra))
extra.sort(key=lambda e:e[2]); import itertools
acc=0
for i,e in enumerate(extra): acc+=e[2]; 
print(sorted(e[2] for e in extra))
R=B+'out/v33_300b_fix3/rules/'
def refpage(s,k):
    n=0
    for c in ch[s]:
        r=json.load(open(R+f'{s}_c{c[0]:03d}-{c[1]:03d}.json'))
        for p in r['answer']['pages']:
            for b in p['blocks']:
                if isinstance(b,dict) and b.get('type')=='reference':
                    n+=1
                    if n==k: return p['page']
    return None
need_ch=defaultdict(set)
for x in cites:
    s=x['stem']; m=re.search(r'fn-p(\d+)',x['where'])
    p=int(m.group(1)) if m else refpage(s,int(re.search(r'r(\d+)',x['where']).group(1)))
    if p is None: print('noref',s,x['where']); continue
    c=[c for c in ch[s] if c[0]<=p<=c[1]][0]
    if s in u and any(cc==c for cc in prefix(s,u[s])): continue
    need_ch[s].add(c)
print('cite-only chunks',sum(len(v) for v in need_ch.values()),'pages',sum(pages(v) for v in need_ch.values()),'articles',len(need_ch))
json.dump(dict(full={s:p for s,p in u.items()}, cite_chunks={s:sorted(v) for s,v in need_ch.items()}),open('plan.json','w'),indent=1)
# cite chunks in draw order until the whole plan reaches 900 pages; an article already in the full set is extended
base=sum(pages(prefix(s,p)) for s,p in u.items())
sel=defaultdict(set); up=dict(u); tot=base; covered=[]; dropped=[]
for x in cites:
    s=x['stem']; m=re.search(r'fn-p(\d+)',x['where'])
    p=int(m.group(1)) if m else refpage(s,int(re.search(r'r(\d+)',x['where']).group(1)))
    c=[c for c in ch[s] if c[0]<=p<=c[1]][0]
    if (s in up and c in prefix(s,up[s])) or c in sel[s]: covered.append(x['i']); continue
    k=(pages(prefix(s,c[0]))-pages(prefix(s,up[s]))) if s in up else c[1]-c[0]+1
    if tot+k>900: dropped.append(x['i']); continue
    tot+=k; covered.append(x['i'])
    if s in up: up[s]=c[0]
    else: sel[s].add(c)
print('total pages',tot,'cites kept',len(covered),'dropped',dropped)
plan={s:{'upto':p} for s,p in up.items()}
for s,v in sel.items():
    if v: plan[s]={'chunks':sorted(v)}
json.dump(plan,open('/home/appuser/inkscript/experiments/60_claude_reader/out/plan_t1.json','w'),indent=1)
json.dump(dict(kept=covered,dropped=dropped),open('/home/appuser/inkscript/experiments/60_claude_reader/out/plan_t1_cites.json','w'))
print(len(plan),'articles in plan', sum(1 for v in plan.values() if 'upto' in v),'chained')
