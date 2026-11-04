"""Experiment 74 (from look70.py; usage look74.py J): the ten random pages (seed 7446, judge_pages74.py) for the look beside the scan: each page's text
from the master (blocks whose id is on that page, in order) + the scan cut in thirds for reading. No calls."""
import json, re, sys
from pathlib import Path
from lxml import etree
import cv2
J = sys.argv[1]
H = Path(__file__).resolve().parent / "out" / J
PAGES = H.parents[2] / "43_rehearsal" / "out" / "pages"
run = f"j{J}"
look = json.loads((H / "look10.json").read_text())["pages"]
for s, p in look:
    root = etree.parse(str(H / run / "masters" / f"{s}.jats.xml")).getroot()
    out = []
    for e in root.iter():
        i = e.get("id") if isinstance(e.tag, str) else None
        if i and re.match(rf"^p{p}(b|t)\d", i) and not any((a.get("id") or "").startswith(f"p{p}") for a in e.iterancestors()):
            out.append(f"[{e.tag} {i}] " + " ".join("".join(e.itertext()).split()))
    (H / "look10").mkdir(exist_ok=True)
    (H / "look10" / f"{s}_p{p:03d}.txt").write_text("\n".join(out), encoding="utf-8")
    img = cv2.imread(str(PAGES / f"{s}_p{p:03d}.jpg"))
    h = img.shape[0]
    for k in range(3):
        c = img[max(0, k * h // 3 - 60): min(h, (k + 1) * h // 3 + 60)]
        c = cv2.resize(c, (1500, int(c.shape[0] * 1500 / c.shape[1])))
        cv2.imwrite(str(H / "look10" / f"{s}_p{p:03d}_{k}.jpg"), c, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(s, p, len(out), "blocks")
