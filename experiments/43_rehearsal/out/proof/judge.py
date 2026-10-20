"""Append one page judgement: python3 judge.py STEM PAGE VERDICT 'kinds,comma,sep' 'reason'"""
import json, sys, time
stem, p, v, kinds, why = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
assert v in ('right', 'minor', 'serious')
ks = [k for k in kinds.split(',') if k]
OK = {'missing_text','text_not_on_scan','wrong_kind','wrong_order','notes_links','table_picture','verse','metadata','word_errors','format_loss','other'}
assert all(k.split(':')[0] in OK for k in ks), ks
with open('pages.jsonl', 'a') as f:
    f.write(json.dumps(dict(stem=stem, page=p, verdict=v, kinds=ks, why=why, image=f'side/side_{stem[:4]}_p{p:03d}.jpg', t=time.strftime('%H:%M')), ensure_ascii=False) + '\n')
print('ok', stem, p, v)
