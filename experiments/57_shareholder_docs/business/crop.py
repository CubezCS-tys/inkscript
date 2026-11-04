"""Crop the raw screenshots in img/ to what each caption talks about; write img/web/*.jpg (2000 px wide)."""
from pathlib import Path
from PIL import Image
D = Path(__file__).resolve().parent / "img"
OUT = D / "web"; OUT.mkdir(exist_ok=True)
# name: (top, bottom) in CSS pixels of the 1440-wide page (screenshots are 2x)
CROPS = {"index": (0, 1372), "journal": (0, 1240), "article_beside": (0, 1000), "explore": (0, 960),
         "person": (0, 1010), "work": (0, 1210), "project": (0, 1335), "librarian": (0, 1210), "guide": (0, 800)}
for name, (t, b) in CROPS.items():
    im = Image.open(D / f"{name}.png").convert("RGB")
    im = im.crop((0, t * 2, im.width, min(b * 2, im.height)))
    im = im.resize((2000, round(im.height * 2000 / im.width)), Image.LANCZOS)
    im.save(OUT / f"{name}.jpg", quality=88, optimize=True)
    print(name, im.size)
