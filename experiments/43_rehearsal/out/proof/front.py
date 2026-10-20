import sys, re
import xml.etree.ElementTree as etree
from pathlib import Path
M = Path(__file__).resolve().parents[1]/'v33_300b_final/masters'
def front(stem):
    t = etree.parse(str(M/f'{stem}.jats.xml'))
    am = t.find('.//article-meta')
    out=[]
    for el in am.iter():
        if el.tag in ('article-title','trans-title','contrib','aff','pub-date','fpage','lpage','kwd-group','abstract','trans-abstract','volume','issue'):
            out.append(f'{el.tag} {dict(el.attrib)}: ' + re.sub(r'\s+',' ',' '.join(el.itertext()))[:300])
    jm = t.find('.//journal-meta')
    if jm is not None: out.insert(0, 'JOURNAL: '+re.sub(r'\s+',' ',' '.join(jm.itertext()))[:200])
    return '\n'.join(out)
if __name__=='__main__': print(front(sys.argv[1]))
