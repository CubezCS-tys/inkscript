"""Experiment 76, step 0: what Argon / Azure / scan material is on disk (read only; no calls).

For every article that Argon (Gemini 4 Argon over Azure's lines, experiment 43's pipeline) answered, count the
pages it covered, Azure's non-empty lines on those pages, the lines Argon labelled, the lines Argon "fixed", and
whether the Azure JSON and the scan PDF are on this machine. One JSON line per article -> out/inventory76.jsonl.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

E = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"

SETS = [  # (name, sample file, raw dir) -- each is one run of experiment 43's pipeline
    ("v2_55", E / "41_azure_structure/out/sample.json", E / "43_rehearsal/out/v2_55/raw"),
    ("v33_300", E / "43_rehearsal/sample43.json", E / "43_rehearsal/out/v33_300/raw"),
    ("v33_300b", E / "43_rehearsal/sample43b.json", E / "43_rehearsal/out/v33_300b/raw"),
    ("j0130", E / "52_journal_gate1/out/sample52.json", E / "52_journal_gate1/out/j0130/raw"),
    ("j0165", E / "70_gate2_pilot/out/sample70.json", E / "70_gate2_pilot/out/j0165/raw"),
] + [(f"j{j}", E / f"74_gate2_full/out/{j}/sample.json", E / f"74_gate2_full/out/{j}/j{j}/raw")
     for j in ("0011", "0013", "0097", "0246", "0523", "0840", "1001", "1182")]


def fix(p: str) -> Path:
    return Path(str(p).replace("/home/yassine/", "/home/appuser/"))


def azure_pages(f: Path):
    r = json.loads(f.read_text(encoding="utf-8"))
    return r.get("analyzeResult", r)["pages"]


def nonempty(pg) -> list[str]:
    return [t for t in ((ln.get("content") or "").strip() for ln in pg.get("lines", [])) if t]


def main():
    seen = set()
    rows = []
    for name, sf, raw in SETS:
        if not sf.exists():
            print("no sample", sf); continue
        arts = json.loads(sf.read_text(encoding="utf-8"))["articles"]
        for a in arts:
            stem = a["stem"]
            files = sorted(raw.glob(f"{stem}_c*.json")) if raw.exists() else []
            az, pdf = fix(a["azure"]), fix(a["pdf"])
            row = dict(set=name, stem=stem, journal=a.get("journal"), jcode=stem[:4], year=a.get("year"),
                       azure=str(az), pdf=str(pdf), azure_ok=az.exists(), pdf_ok=pdf.exists(),
                       answered=bool(files), dup=stem in seen)
            pages, labelled, fixed, noise, nfix = set(), set(), set(), set(), 0
            for f in files:
                d = json.loads(f.read_text(encoding="utf-8"))
                ans = d.get("answer") or {}
                if not isinstance(ans, dict):
                    continue
                pages.update(range(d["first"], d["last"] + 1))
                for pg in ans.get("pages") or []:
                    for b in pg.get("blocks") or []:
                        for lid in b.get("lines") or []:
                            if isinstance(lid, str):
                                labelled.add(lid.split("#")[0])
                for x in ans.get("fixes") or []:
                    nfix += 1; fixed.add(str(x.get("line")))
                for x in ans.get("noise") or []:
                    noise.add(str(x.get("line") if isinstance(x, dict) else x))
            nlines = 0
            if files and az.exists():
                pgs = azure_pages(az)
                nlines = sum(len(nonempty(pgs[p - 1])) for p in pages if p - 1 < len(pgs))
            row.update(pages=len(pages), lines=nlines, labelled=len(labelled), fixed_lines=len(fixed), fixes=nfix,
                       noise=len(noise))
            rows.append(row)
            seen.add(stem)
        print(name, len(arts), "articles", flush=True)
    OUT.mkdir(exist_ok=True)
    with open(OUT / "inventory76.jsonl", "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
