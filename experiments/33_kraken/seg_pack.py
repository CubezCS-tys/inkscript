"""Pack the line-finder training pages small enough for this machine's slow upload (0.1-0.9 MB/s measured):
WebP quality 40 (about 64 KB a page instead of 180 KB as JPEG), XML pointing at the .webp.

    out/env/bin/python seg_pack.py      -> out/seg_up.tar  (seg/train, seg/dev)
"""
import re, tarfile
from pathlib import Path
from PIL import Image

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out")
up = OUT / "seg_up"
for sp in ("train", "dev"):
    (up / "seg" / sp).mkdir(parents=True, exist_ok=True)
    for x in sorted((OUT / "seg" / sp).glob("*.xml")):
        Image.open(x.with_suffix(".jpg")).save(up / "seg" / sp / f"{x.stem}.webp", "WEBP", quality=40)
        t = re.sub(r'imageFilename="([^"]+)\.jpg"', r'imageFilename="\1.webp"', x.read_text())
        (up / "seg" / sp / x.name).write_text(t)
with tarfile.open(OUT / "seg_up.tar", "w") as tf:
    tf.add(up / "seg", arcname="seg")
print((OUT / "seg_up.tar").stat().st_size // 2**20, "MB")
