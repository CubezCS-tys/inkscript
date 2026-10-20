import json, math, collections
def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k/n; d = 1 + z*z/n; c = p + z*z/(2*n); h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return (max(0, (c-h)/d), min(1, (c+h)/d))
P = [json.loads(l) for l in open('pages.jsonl')]
n = len(P); v = collections.Counter(x['verdict'] for x in P)
kinds = collections.Counter()
for x in P:
    for k in set(k.split(':')[0] for k in x['kinds']): kinds[k] += 1
out = dict(pages=n, verdicts={k: dict(n=c, ci=wilson(c, n)) for k, c in v.items()},
           kinds={k: dict(n=c, ci=wilson(c, n)) for k, c in kinds.most_common()})
W = [json.loads(l) for l in open('words.jsonl')]
nw = sum(x['words'] for x in W); out['words'] = dict(pages=len(W), words=nw, wrong=sum(x['wrong'] for x in W), wrong_ci=wilson(0, nw),
     ortho=sum(x['ortho'] for x in W), ortho_ci=wilson(sum(x['ortho'] for x in W), nw))
C = json.load(open('cites_score.json')); ft = C['fields_total']; N = sum(ft.values())
out['cites'] = dict(n=80, fully_right=C['citations_all_right'], fully_ci=wilson(C['citations_all_right'], 80), fields=N, field_right=ft.get('right',0),
     field_ci=wilson(ft.get('right',0), N), loose=ft.get('loose',0), missing=ft.get('missing',0), wrong=ft.get('wrong',0), invented=1, per_field=C['per_field'])
I = json.load(open('ibid_score.json'))['tally']; out['ibid'] = dict(I, n=20, right_ci=wilson(I['right'], 20))
M = json.load(open('meta_score.json')); out['meta'] = dict(n=30, fully_right=M['fully_right'], fully_ci=wilson(M['fully_right'], 30), per_field=M['per_field'],
     d33=M['d33_changes'], d33_articles=M['d33_articles'])
json.dump(out, open('stats.json', 'w'), indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:3000])
