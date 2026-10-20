import sys
from PIL import Image
from pathlib import Path
stem,p,y0,y1=sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),float(sys.argv[4])
x0,x1=(float(sys.argv[5]),float(sys.argv[6])) if len(sys.argv)>6 else (0,1)
im=Image.open(Path(__file__).parent.parent/'pages'/f'{stem}_p{p:03d}.jpg'); w,h=im.size
c=im.crop((int(w*x0),int(h*y0),int(w*x1),int(h*y1)))
if c.width>1800: c=c.resize((1800,int(c.height*1800/c.width)))
o=f'crops/{stem[:4]}_p{p}_{y0}_{x0}.png'; c.save(o); print(o)
