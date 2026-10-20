import sys,re
sys.path.insert(0,'.')
from bs4 import BeautifulSoup
from dump import VIEWS
stem,p=sys.argv[1],int(sys.argv[2]); blocks=[int(b) for b in sys.argv[3].split(',')]
soup=BeautifulSoup((VIEWS/f'{stem}.html').read_text(),'html.parser')
n=0
for b in soup.find(id=f'p{p}').select('.lpage > .pc'):
    ob=b.find('span',class_='ob')
    if ob and ob.get_text().isdigit() and int(ob.get_text()) in blocks:
        for o in b.select('span.ob,button'): o.decompose()
        n+=len(b.get_text(' ').split())
print(n)
