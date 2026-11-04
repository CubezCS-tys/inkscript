"""Experiment 59: the pages that may go to Reducto (owner's budget: about 50, never more than 60).

    /home/appuser/inkscript/.venv/bin/python units59.py      -> out/units59.json, out/approved_pages.json

Three sets, all pages of articles already hand-checked, sent as the same 300 dpi page images Indra read (exp 58):
  text   22 of exp 41's 34 truth pages: 12 born-digital (publisher's text layer = truth) + 10 owner gold pages
         (exp 34), chosen to keep the hard old prints (0656, 0005, 0041, 0629, 0407, 0355 ...) and the easy ones
  meta   page 1 of 12 of the proof pack's 30 metadata articles (seed 20261024): 10 the masters got fully right
         and 2 they did not (0367 title, 1633 affiliation) -- the same 25:5 share as the 30 (10:2)
  cites  15 pages holding 20 of the proof pack's 80 sampled citations (seed 20261022): the 4 pages holding 2-3
         each, then single ones for Arabic footnotes / Arabic reference lists / Latin, with editions, translators,
         Hijri dates and places
Layout is scored on the meta + cites pages (27 pages of the 300-article run v33_300b_fix3; 5 of them two-column).
"""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"

TEXT = ["0005-055-003-004_p008", "0197-002-001-003_p003", "0355-000-002-006_p017", "0407-009-001-028_p003",
        "0422-004-006-018_p002", "0447-000-006-007_p002", "0513-006-003-007_p003", "0629-021-011-009_p005",
        "0656-016-001-011_p003", "0041-002-005-008_p012",
        "0767-010-002-007_p001", "0493-000-029-001_p002", "0418-000-136-002_p002", "0418-000-136-002_p004",
        "0920-011-020-009_p002", "1148-041-116-018_p004", "1148-041-116-018_p007", "7956-000-000-016_p001",
        "2571-006-011-016_p001", "2571-006-011-016_p009", "0198-012-003-001_p015", "2502-000-041-029_p021"]
META = ["0071-020-144-001", "0167-000-111-054", "0266-001-001,002-002", "0367-000-006-017", "0486-000-007-005",
        "0596-037-437-020", "0728-022-003-013", "1036-000-182-010", "1289-000-001-006", "1459-000-009-022",
        "1633-000-006-019", "1717-006-001-005"]
CITES = [29, 46, 47, 26, 51, 28, 63, 54, 56, 7, 11, 2, 42, 5, 58, 69, 66, 74, 3, 23]


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def cite_page(x):
    w = x["where"].split()
    if w[0] == "fn":
        return int(re.match(r"fn-p(\d+)-", w[1]).group(1))
    t = (E / f"43_rehearsal/out/v33_300b_fix3/masters/{x['stem']}.jats.xml").read_text(encoding="utf-8")
    m = re.search(r'<ref id="%s">\s*<mixed-citation id="p(\d+)b' % w[1], t)
    return int(m.group(1))


def main():
    units = []
    s41 = {f"{r['stem']}_p{r['page']:03d}": r for r in jl(E / "41_azure_structure/out/scores.json")["truth_pages"]}
    for pid in TEXT:
        units.append(dict(id=pid, sets=["text"], kind=s41[pid]["kind"],
                          image=str(E / "41_azure_structure/out/pages" / f"{pid}.jpg")))
    by = {}
    for stem in META:
        pid = f"{stem}_p001"
        by[pid] = dict(id=pid, sets=["meta", "layout"], stem=stem, page=1, cites=[],
                       image=str(E / "43_rehearsal/out/pages" / f"{pid}.jpg"))
    cd = {x["i"]: x for x in jl(E / "43_rehearsal/out/proof/cites_draw.json")["sample"]}
    for i in CITES:
        x = cd[i]
        p = cite_page(x)
        pid = f"{x['stem']}_p{p:03d}"
        u = by.setdefault(pid, dict(id=pid, sets=["layout"], stem=x["stem"], page=p, cites=[],
                                    image=str(E / "43_rehearsal/out/pages" / f"{pid}.jpg")))
        if "cites" not in u["sets"]:
            u["sets"].append("cites")
        u["cites"].append(i)
    units += list(by.values())
    for u in units:
        assert Path(u["image"]).exists(), u
    assert len(units) <= 55, len(units)
    (OUT / "units59.json").write_text(json.dumps(units, ensure_ascii=False, indent=1))
    (OUT / "approved_pages.json").write_text(json.dumps([u["id"] for u in units], indent=0))
    print(len(units), "pages:", sum("text" in u["sets"] for u in units), "text,",
          sum("meta" in u["sets"] for u in units), "meta,", sum("cites" in u["sets"] for u in units), "cites pages,",
          sum(len(u.get("cites", [])) for u in units), "citations")


if __name__ == "__main__":
    main()
