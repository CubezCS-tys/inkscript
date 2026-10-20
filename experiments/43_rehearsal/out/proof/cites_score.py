"""Score the 80 drawn citations: every present field is 'right' unless listed; listed fields carry loose/wrong/invented/missing."""
import json, collections
D = json.load(open('cites_draw.json'))
G = {'authors':'authors','editors':'authors','translators':'authors','article-title':'title','chapter-title':'title',
     'source':'source','year':'year','string-date':None,'volume':'volume','issue':'issue','fpage':'pages','lpage':None,'page-range':None,
     'publisher-name':'publisher','publisher-loc':'place','ext-link':'link','pub-id/doi':'link','series':'other','edition':'other'}
# deviations: i -> {group: (verdict, why)}
DEV = {
 2: {'other': ('missing','second locus "ق ٢ جـ ٧ ص ٧٧" not parsed')},
 5: {'authors': ('loose','title د. inside given name; وآخرون dropped'), 'place': ('loose','printer typo عمانن kept'), 'other': ('missing','edition ط7')},
 10: {'citation': ('invented','a book mentioned in passing (not cited) parsed as a citation')},
 11: {'other': ('missing','translator')},
 12: {'title': ('missing','article title "A critique of existing practice..." not parsed')},
 20: {'publisher': ('missing','مركز الخليج للابحاث not parsed')},
 24: {'publisher': ('loose','two bodies merged into one publisher')},
 26: {'publisher': ('loose','venue university as publisher')},
 30: {'year': ('loose','"دجنبر 81" - month + 2-digit year, not a year')},
 31: {'place': ('missing','London not parsed')},
 35: {'title': ('missing','article title not parsed'), 'source': ('loose','volume 52 merged into source "DAI-A 52"')},
 36: {'pages': ('loose','"48. 48" duplication kept')},
 38: {'other': ('loose','"عدد ٣١" read as a day of the date; issue not separated')},
 39: {'place': ('loose','"طبعة أوروبا" (European edition) put as place')},
 40: {'pages': ('loose','16.84 is a title number, put as page')},
 42: {'year': ('loose','Hijri "١٤٢٦ هـ" in <year>, not machine-readable')},
 51: {'link': ('missing','URL not parsed')},
 53: {'authors': ('loose','"Jr." inside surname')},
 54: {'other': ('missing','editor (تحقيق) and edition not parsed')},
 60: {'authors': ('missing','الجاحظ not parsed as author')},
 71: {'authors': ('loose','accusative form أبا الفرج kept as the name')},
 73: {'title': ('loose','unbalanced parenthesis "أمر رقم (09/95"')},
 74: {'source': ('missing','title كتاب المسالك والممالك'), 'year': ('missing','١٨٨٩'), 'place': ('missing','ليدن'), 'other': ('missing','editor دي غوية')},
}
tally = collections.defaultdict(collections.Counter); per = []
cit_ok = 0
for x in D['sample']:
    i = x['i']; dev = DEV.get(i, {})
    groups = set(G.get(f.split('/')[0] if f!='pub-id/doi' else f, 'other') for f, _ in x['fields']) - {None}
    groups |= set(g for g in dev if g != 'citation')
    v = {}
    for g in groups:
        v[g] = dev[g][0] if g in dev else 'right'
        tally[g][v[g]] += 1
    if 'citation' in dev: tally['citation']['invented'] += 1
    allright = all(a == 'right' for a in v.values()) and 'citation' not in dev
    cit_ok += allright
    per.append(dict(i=i, stem=x['stem'], where=x['where'], verdicts=v, notes={k: w for k, (_, w) in dev.items()}, all_right=allright))
tot = collections.Counter(); [tot.update(c) for g, c in tally.items() if g != 'citation']
json.dump(dict(seed=D['seed'], population=D['population'], per_field={g: dict(c) for g, c in tally.items()}, fields_total=dict(tot),
               citations_all_right=cit_ok, items=per), open('cites_score.json', 'w'), ensure_ascii=False, indent=1)
print('citations fully right', cit_ok, '/ 80'); print(dict(tot))
for g, c in sorted(tally.items()): print(g, dict(c))
