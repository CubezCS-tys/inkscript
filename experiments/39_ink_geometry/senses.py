"""The layout's other senses, where the rivers of paper are blind: label every Azure line of a page from
measurements and text patterns alone (no model, and the page's own hand labels are not used):
  - the ink: core letter height, stroke thickness, indent, centring, the gap above, a short rule above;
  - Azure's words: (n) footnote numbers that match a marker in the body, a leading dash or bullet, numbering;
  - the page: the top line, set apart, is page furniture.
-> out/senses/<pid>.jpg, out/senses/<pid>.json"""
import json, re, sys
from pathlib import Path
from statistics import median
import cv2, numpy as np
HERE = Path(__file__).parent; OUT = HERE / "out/senses"; OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE.parent / "38_parser"))
from common import azure_draft, page_image

DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
COL = {"body": (150, 150, 150), "paragraph start": (60, 150, 60), "heading": (30, 30, 220), "footnote": (200, 110, 20),
       "bullet": (170, 40, 170), "bullet, continued": (200, 120, 200), "verse": (20, 150, 200), "furniture": (90, 90, 90)}


def measure(ink, box):
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    c = ink[max(0, y0):y1, max(0, x0):x1]
    if c.size == 0 or c.sum() == 0: return dict(core=0, stroke=0, gap_inside=0)
    ys = np.nonzero(c)[0]; core = float(np.percentile(ys, 80) - np.percentile(ys, 20))   # spread of the ink: scales with letter size
    cs, _ = cv2.findContours(c.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    per = sum(cv2.arcLength(k, True) for k in cs)
    stroke = 2 * c.sum() / max(1, per)                                         # area / half the edge = mean thickness
    cols = c.any(0); runs, n = [], 0                                           # widest empty stretch inside the line
    for v in cols[int(.15 * len(cols)):int(.85 * len(cols))]:
        n = 0 if v else n + 1; runs.append(n)
    return dict(core=core, stroke=round(float(stroke), 2), gap_inside=max(runs or [0]))


def rule_above(ink, box, prev_bottom, W):
    """A thin horizontal line of ink in the gap above this line, at least 10% of the page wide."""
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    g = ink[int(prev_bottom):max(int(prev_bottom) + 1, y0), :]
    if g.shape[0] < 2: return False
    run = cv2.morphologyEx(g.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, int(.10 * W)), np.uint8))
    return bool(run.any())


def label(pid):
    gray = page_image(pid); H, W = gray.shape
    _, ink = cv2.threshold(gray, 0, 1, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    d = azure_draft(pid); by = {l["id"]: l for l in d["lines"]}
    L = [dict(id=i, text=by[i]["text"], box=by[i]["box"]) for i in d["order"]]
    for l in L: l.update(measure(ink, l["box"]))
    # the column: where full lines start and end
    right = median(l["box"][2] for l in L); left = median(l["box"][0] for l in L); colw = right - left
    core = median(l["core"] for l in L if l["core"]); stroke = median(l["stroke"] for l in L if l["stroke"])
    cy = lambda l: (l["box"][1] + l["box"][3]) / 2
    pitch = median(cy(b) - cy(a) for a, b in zip(L, L[1:]) if cy(b) - cy(a) > 10); gap = pitch
    body_text = " ".join(l["text"] for l in L).translate(DIG)
    for k, l in enumerate(L):
        x0, y0, x1, y1 = l["box"]; t = l["text"].translate(DIG).strip()
        l["gap_above"] = round((cy(l) - cy(L[k - 1])) / pitch, 2) if k else None   # line pitch above, in normal pitches
        l["size"] = round(l["core"] / core, 2); l["bold"] = round(l["stroke"] / stroke, 2)
        l["indent_right"] = round((right - x1) / colw, 3); l["short"] = (x1 - x0) / colw < 0.75
        l["centred"] = l["short"] and abs((x0 - left) - (right - x1)) < 0.08 * colw and (x0 - left) > 0.1 * colw
        l["rule_above"] = bool(k) and rule_above(ink, l["box"], L[k - 1]["box"][3], W)
        m = re.match(r"^\(?\s*(\d{1,3})\s*\)", t)
        l["note_no"] = m and m.group(1)
        l["note_matches_body"] = bool(m) and len(re.findall(r"\(\s*%s\s*\)" % m.group(1), body_text)) >= 2
        l["dash"] = bool(re.match(r"^[-–—ـ•▪●*]\s", t))
        l["numbered"] = bool(re.match(r"^(\d{1,2}|[أ-ي])\s*[-–ـ.)]\s*\S", t)) and not m
        l["verse"] = l["gap_inside"] > 0.035 * colw
    # decisions, each with its reason
    foot = False
    for k, l in enumerate(L):
        why = []; t = l["text"].translate(DIG).strip()
        top = [m for m in L if m["box"][3] < L[0]["box"][3] + 0.5 * pitch]          # the first row of the page
        nxt = [m for m in L if m not in top]
        if l in top and nxt and all(m["short"] for m in top) and (cy(nxt[0]) - cy(l) > 1.5 * pitch or re.fullmatch(r"[-–ـ\s\d]+", t)):
            lab, why = "furniture", ["top row, only a number" if re.fullmatch(r"[-–ـ\s\d]+", t) else "top row, short, set apart"]
        elif foot or (l["rule_above"] and k > len(L) // 3) or (l["note_matches_body"] and l["size"] < 0.95) or \
                (l["note_matches_body"] and k > len(L) // 2 and (l["gap_above"] or 0) > 1.2):
            if not foot: why.append("rule above" if l["rule_above"] else f"starts ({l['note_no']}), which is marked in the body")
            foot = True; lab = "footnote"; why.append(f"letters {l['size']}x")
        elif (l["gap_above"] or 0) > 1.4 and l["short"] and (l["size"] > 1.08 or l["bold"] > 1.12 or l["numbered"] or l["centred"]):
            lab = "heading"; why = [f"gap above {l['gap_above']}x", "short line"] + (["numbered"] if l["numbered"] else []) + \
                ([f"thicker strokes {l['bold']}x"] if l["bold"] > 1.12 else []) + ([f"bigger letters {l['size']}x"] if l["size"] > 1.08 else []) + (["centred"] if l["centred"] else [])
        elif l["dash"]:
            lab, why = "bullet", ["starts with a dash"]
        elif l["verse"]:
            lab, why = "verse", ["a wide gap in the middle of the line (two half-verses)"]
        elif k and (L[k - 1]["box"][2 - 2] - left > 0.15 * colw and L[k - 1]["short"] and not L[k - 1].get("label") == "heading") or l["indent_right"] > 0.02:
            lab, why = "paragraph start", ["previous line ends short" if L[k - 1]["short"] else f"indented {l['indent_right']:.0%}"]
        elif k and L[k - 1]["label"] in ("bullet", "bullet, continued"):
            lab, why = "bullet, continued", ["follows a bullet line, not indented"]
        else:
            lab = "body"
        l["label"], l["why"] = lab, why
    return gray, L


def draw(pid, gray, L):
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR); over = img.copy()
    for l in L:
        x0, y0, x1, y1 = (int(round(v)) for v in l["box"]); c = COL[l["label"]]
        cv2.rectangle(over, (x0 - 6, y0), (x1 + 6, y1), c, -1)
    img = cv2.addWeighted(over, 0.28, img, 0.72, 0)
    for l in L:
        x0, y0, x1, y1 = (int(round(v)) for v in l["box"]); c = COL[l["label"]]
        cv2.rectangle(img, (x0 - 6, y0), (x1 + 6, y1), c, 3)
        cv2.putText(img, l["label"], (x1 + 14, int((y0 + y1) / 2) + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, c, 2)
    pad = np.full((img.shape[0], 260, 3), 255, np.uint8)
    cv2.imwrite(str(OUT / f"{pid}.jpg"), np.hstack([img, pad]) if False else cv2.copyMakeBorder(img, 0, 0, 0, 260, cv2.BORDER_CONSTANT, value=(255, 255, 255)), [cv2.IMWRITE_JPEG_QUALITY, 85])
    json.dump(L, open(OUT / f"{pid}.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
  for pid in sys.argv[1:] or ["0266-006-002-001_p042", "0005-055-003-004_p008"]:
    gray, L = label(pid); draw(pid, gray, L)
    for l in L: print(l["id"], f"{l['label']:15}", l["size"], l["bold"], l["gap_above"], l["indent_right"], l["gap_inside"], l["why"], l["text"][:40])
