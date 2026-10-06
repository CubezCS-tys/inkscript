"""Fixture checks, today's src vs the patch, both built in this process (build25.py): words intact and lines in order
(the --verify line of each build log), letter coverage (09_pen_path/coverage.py), and whether the copied text of any
page differs between the two builds (pdfium, as compare_boxes).  -> out/checks25.json"""
import re, json, subprocess, sys, difflib
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments/09_pen_path")); import compare_boxes as CB
ORDER = ["0582", "1036", "0618", "0772"]


def verify(log):
    return re.findall(r"all documents: (\d+/\d+) words intact.*?lines in order (\d+/\d+)", open(log).read())


def cov(pdf):
    o = subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "experiments/09_pen_path/coverage.py"), str(pdf)], capture_output=True, text=True).stdout
    m = re.search(r"own box: (\d+) of (\d+)", o); return f"{m.group(1)}/{m.group(2)}"


out = {}; VT, VA = verify(HERE / "out/build_today.log"), verify(HERE / "out/build_lumpfoot.log")
for i, d in enumerate(ORDER):
    pt = next((HERE / "out/build_today" / d).glob("*_vector.pdf")); pa = next((HERE / "out/build_lumpfoot" / d).glob("*_vector.pdf"))
    A, B = CB.read(str(pt)), CB.read(str(pa)); diff = [(k + 1, ta, tb) for k, ((ta, _), (tb, _)) in enumerate(zip(A, B)) if ta != tb]
    ex = []
    for pg, ta, tb in diff[:3]:
        sm = difflib.SequenceMatcher(None, ta, tb)
        ex += [f"p{pg}: «{ta[i1:i2]}» → «{tb[j1:j2]}»" for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"][:3]
    out[d] = dict(today=dict(intact=VT[i][0], lines=VT[i][1], coverage=cov(pt)), after=dict(intact=VA[i][0], lines=VA[i][1], coverage=cov(pa)),
                  text_changed="same" if not diff else f"{len(diff)} pages differ: " + "; ".join(ex))
json.dump(out, open(HERE / "out/checks25.json", "w"), ensure_ascii=False, indent=1); print(json.dumps(out, ensure_ascii=False, indent=1))
