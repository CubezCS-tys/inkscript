"""Experiment 58: the page lists (units) the runs read.  No outputs other than out/units_*.json.

  truth34   exp 41's 34 truth pages (20 owner gold, 14 born-digital): 300 dpi images (exp 41 out/pages) and the PDFs
  lay300    every page of the 300 unseen articles (exp 43 v33_300b_fix3, the proof pack's run) that has Gemini's
            line roles in rules/: 300 dpi images (exp 43 out/pages)
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def truth34():
    s = jl(E / "41_azure_structure/out/scores.json")
    arts = {a["stem"]: a for a in jl(E / "41_azure_structure/out/sample.json")["articles"]}
    img, pdf = [], []
    for r in s["truth_pages"]:
        pid = f"{r['stem']}_p{r['page']:03d}"
        a = arts[r["stem"]]
        img.append(dict(id=pid, image=str(E / "41_azure_structure/out/pages" / f"{pid}.jpg"), kind=r["kind"]))
        # the article's page r['page'] is PDF page r['page'] (windows keep the PDF's numbering in exp 41)
        pdf.append(dict(id=pid, pdf=a["pdf"], page=r["page"], kind=r["kind"]))
    return img, pdf


def lay300():
    arts = {a["stem"]: a for a in jl(E / "43_rehearsal/sample43b.json")["articles"]}
    units, seen = [], set()
    for f in sorted((E / "43_rehearsal/out/v33_300b_fix3/rules").glob("*.json")):
        d = jl(f)
        for p in d["answer"]["pages"]:
            pid = f"{d['stem']}_p{p['page']:03d}"
            im = E / "43_rehearsal/out/pages" / f"{pid}.jpg"
            if pid in seen or not im.exists():
                continue
            seen.add(pid)
            units.append(dict(id=pid, image=str(im), stem=d["stem"], page=p["page"]))
    return units


if __name__ == "__main__":
    i, p = truth34()
    (OUT / "units_truth34.json").write_text(json.dumps(i, indent=0))
    (OUT / "units_truth34_pdf.json").write_text(json.dumps(p, indent=0))
    u = lay300()
    (OUT / "units_lay300.json").write_text(json.dumps(u, indent=0))
    print(len(i), len(p), len(u))
