import time, sys
sys.path.insert(0,'/home/appuser/inkscript/experiments/45_marc_db')
from build45 import fold
from q import marc
m=marc()
m.execute("CREATE VIRTUAL TABLE temp.v USING fts5vocab(main, fts, 'row')")
ws=[fold(x) for x in "تأثير مناهج تدريبية بحجوم المتغيرات الفسيولوجية الناشئين".split()]
t=time.time()
for w in ws: print(w, m.execute("select doc from temp.v where term=?",(w,)).fetchone(), round(time.time()-t,3))
t=time.time()
print(m.execute("select rowid from fts where fts match ? limit 50",('title: (بحجوم AND الفسيولوجيه)',)).fetchall(), time.time()-t)
t=time.time()
print(m.execute("select rowid from fts where fts match ? order by rank limit 20",('title: (تاثير OR مناهج OR تدريبيه OR بحجوم OR المتغيرات OR الفسيولوجيه OR الناشئين)',)).fetchall()[:5], time.time()-t)
