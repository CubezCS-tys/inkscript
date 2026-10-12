"""Draw PAGE XML lines on their page: boundary in blue, baseline in red (and optional predicted lines in green).

    out/env/bin/python seg_look.py PAGE.xml [PRED.json] OUT.png [--crop x0,y0,x1,y1]
PRED.json: {"lines": [{"baseline": [[x,y],...], "boundary": [[x,y],...]}]} in the same pixel frame.
"""
import json, re, sys
from pathlib import Path
from PIL import Image, ImageDraw


def read_xml(p):
    t = Path(p).read_text(); img = re.search(r'imageFilename="([^"]+)"', t).group(1)
    lines = []
    for m in re.finditer(r'<TextLine[^>]*><Coords points="([^"]+)"/><Baseline points="([^"]+)"/>', t):
        pts = lambda s: [tuple(map(int, q.split(","))) for q in s.split()]
        lines.append(dict(boundary=pts(m.group(1)), baseline=pts(m.group(2))))
    return Path(p).parent / img, lines


def draw(xml, pred, out, crop=None):
    img, lines = read_xml(xml)
    im = Image.open(img).convert("RGB"); d = ImageDraw.Draw(im)
    for l in lines:
        d.polygon(l["boundary"], outline=(40, 90, 230)); d.line(l["baseline"], fill=(230, 30, 30), width=3)
    if pred:
        for l in json.load(open(pred))["lines"]:
            d.line([tuple(p) for p in l["baseline"]], fill=(20, 170, 60), width=3)
    if crop:
        im = im.crop(crop)
    im.save(out)


if __name__ == "__main__":
    argv = sys.argv[1:]; crop = None
    if "--crop" in argv:
        k = argv.index("--crop"); crop = tuple(map(int, argv[k + 1].split(","))); argv = argv[:k] + argv[k + 2:]
    a = argv
    draw(a[0], a[1] if len(a) == 3 else None, a[-1], crop)
