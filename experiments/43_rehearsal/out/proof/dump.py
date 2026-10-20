"""Dump one page of a mirror Layout view: blocks in reading order with kind, box and text (fixes shown as [azure->ours])."""
import re, sys, html as H
from pathlib import Path
from bs4 import BeautifulSoup
VIEWS = Path(__file__).resolve().parents[1] / 'v33_300b_final/views/mirror'
def page(stem, n, full=True):
    soup = BeautifulSoup((VIEWS/f'{stem}.html').read_text(), 'html.parser')
    sec = soup.find(id=f'p{n}')
    out = []
    for b in sec.select('.lpage > .pc'):
        ob = b.find('span', class_='ob'); ob = ob.get_text() if ob else '-'
        st = b.get('style','')
        m = re.search(r'left:([\d.]+)%;top:([\d.]+)%;width:([\d.]+)%;height:([\d.]+)%', st)
        box = '(%.0f,%.0f %.0fx%.0f)' % tuple(map(float, m.groups())) if m else ''
        for f in b.select('span.fix'):
            f.insert_before('[' + f.get('data-azure','') + '->'); f.insert_after(']')
        for s in b.select('span.sic'):
            s.insert_after('{sic->' + s.get('data-corr','') + '}')
        for o in b.select('span.ob'): o.decompose()
        extra = ''
        img = b.find('img')
        if img: extra = ' IMG:' + (img.get('alt') or '')
        ft = b.find(class_='figtx')
        if ft: extra += ' FIGTEXT:' + ft.get('data-text','')[:200]; ft.decompose()
        cls = ' '.join(c for c in b.get('class',[]) if c not in ('pc',))
        t = re.sub(r'\s+', ' ', b.get_text(' ')).strip()
        out.append(f"#{ob} {b.get('data-t')} [{cls}] {box}{extra}\n    {t if full else t[:200]}")
    return '\n'.join(out)
if __name__ == '__main__':
    print(page(sys.argv[1], int(sys.argv[2])))
