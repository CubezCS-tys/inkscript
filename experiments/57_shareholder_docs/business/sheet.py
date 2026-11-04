"""Contact sheet of out/pages/*.png -> out/sheet.png (for a quick look at the layout)."""
from pathlib import Path
from PIL import Image
import sys
P = sorted((Path(__file__).resolve().parent / "out" / "pages").glob("page-*.png"))[:int(sys.argv[1])]
w, h = 300, 424; cols = 6; rows = (len(P) + cols - 1) // cols
S = Image.new("RGB", (cols * (w + 10), rows * (h + 10)), "#888")
for i, p in enumerate(P):
    S.paste(Image.open(p).convert("RGB").resize((w, h)), ((i % cols) * (w + 10), (i // cols) * (h + 10)))
S.save(P[0].parent.parent / "sheet.png")
