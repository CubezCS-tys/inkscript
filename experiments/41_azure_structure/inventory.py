"""Experiment 41: every whole document on this machine that has both its PDF and Azure's JSON, with what truth it
carries (owner's gold pages done, born-digital truth pages, experiment 39 Pro-referee pages, Flash-labelled pages,
catalogue JATS master), its page count, decade, journal and page kinds. Writes out/inventory.json (no calls).

    /home/yassine/inkscript/.venv/bin/python inventory.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def decade(y):
    try:
        y = int(str(y)[:4])
    except Exception:
        return None
    return "pre-1960" if y < 1960 else f"{y // 10 * 10}s"


def main():
    docs = {}

    def add(stem, az, pdf, src):
        az, pdf = Path(az), Path(pdf)
        if az.exists() and pdf.exists() and stem not in docs:
            docs[stem] = dict(stem=stem, azure=str(az), pdf=str(pdf), source=src)

    for stem, p in jl(E / "34_yardstick/out/pool.json").items():
        add(stem, p["azure"], p["scan"], "34 pool")
    for d in sorted((E / "40_gemini4_vlm/out/src").iterdir()):
        add(d.name, d / f"{d.name}.json", d / f"{d.name}.pdf", "40 src")
    for f in sorted((E / "40_gemini4_vlm/out/docs").glob("*.json")):
        add(f.stem, f, f.with_suffix(".pdf"), "40 docs")
    for base, src in ((E / "39_ink_geometry/out/more/azure", "39 more"), (E / "33_kraken/out/docs", "33 docs"),
                      (E / "19_azure_map/out/docs", "19 docs"), (E / "28_scale/out/azure", "28 scale")):
        if base.exists():
            for d in sorted(base.iterdir()):
                add(d.name, d / f"{d.name}.json", d / f"{d.name}.pdf", src)

    meta = {}
    for f in (E / "33_kraken/out/meta.json", E / "19_azure_map/out/meta.json"):
        for k, v in jl(f).items():
            meta.setdefault(k, {}).update({a: b for a, b in v.items() if b})
    for k, v in jl(E / "34_yardstick/out/pool.json").items():
        meta.setdefault(k, {}).update({a: b for a, b in v.items() if b and a in ("year", "journal", "field")})
    merged = E / "29_catalogue/out/merged"

    gold = defaultdict(list)
    gold_todo = defaultdict(list)
    for f in (E / "34_yardstick/out/gold").glob("*.json"):
        g = jl(f)
        (gold if g.get("status") == "done" else gold_todo)[g["stem"]].append(g["page"])
        if g.get("year"):
            meta.setdefault(g["stem"], {}).setdefault("year", g["year"])
        if g.get("journal"):
            meta.setdefault(g["stem"], {}).setdefault("journal", g["journal"])
    bd = defaultdict(list)
    for f in (E / "36_vlm_bakeoff/out/ref/bdtruth").glob("*.json"):
        m = re.match(r"bd_(.+)_p(\d+)$", f.stem)
        bd[m.group(1)].append(int(m.group(2)))
    ref = defaultdict(list)
    for f in (E / "39_ink_geometry/out/score_test").glob("*.json"):
        s, p = f.stem.rsplit("_p", 1)
        ref[s].append(int(p))
    flash = defaultdict(list)
    for d in (E / "39_ink_geometry/out/train/labels", E / "39_ink_geometry/out/round2/labels"):
        for f in d.glob("*.json"):
            s, p = f.stem.rsplit("_p", 1)
            flash[s].append(int(p))
    kinds = defaultdict(lambda: dict(math=0, grid=0))
    for f in (E / "39_ink_geometry/out/train/pool_kinds.json", E / "39_ink_geometry/out/more/kinds.json"):
        for r in jl(f):
            kinds[r["stem"]]["math"] += r.get("math", 0) or 0
            kinds[r["stem"]]["grid"] += r.get("grid", 0) or 0
    s40 = {p["stem"]: p for p in jl(E / "40_gemini4_vlm/out/sample.json")["pages"]}
    s40docs = {d["stem"] for d in jl(E / "40_gemini4_vlm/out/sample.json")["docs"]}

    rows = []
    for stem, d in sorted(docs.items()):
        a = jl(d["azure"])
        a = a.get("analyzeResult", a)
        pages = a.get("pages", [])
        n = len(pages)
        txt = a.get("content", "")
        ar = len(re.findall(r"[؀-ۿ]", txt))
        la = len(re.findall(r"[A-Za-zÀ-ɏ]", txt))
        fr = len(re.findall(r"\b(le|la|les|des|du|est|une|dans)\b", txt))
        en = len(re.findall(r"\b(the|and|of|is|in|to)\b", txt))
        roles = defaultdict(int)
        for p in a.get("paragraphs", []) or []:
            roles[p.get("role") or "text"] += 1
        lines = sum(len(p.get("lines", [])) for p in pages)
        m = meta.get(stem, {})
        jats = merged / f"{stem}.jats.xml"
        year = m.get("year")
        if not year and jats.exists():
            y = re.search(r"<year>(\d{4})</year>", jats.read_text(encoding="utf-8"))
            year = y.group(1) if y else None
        journal = m.get("journal")
        if not journal and jats.exists():
            j = re.search(r"<journal-title[^>]*>([^<]+)<", jats.read_text(encoding="utf-8"))
            journal = j.group(1) if j else None
        rows.append(dict(d, pages=n, lines=lines, year=year, decade=decade(year), journal=journal,
                         journal_code=stem[:4], jats=str(jats) if jats.exists() else None,
                         gold_done=sorted(gold.get(stem, [])), gold_todo=len(gold_todo.get(stem, [])),
                         bd_pages=sorted(bd.get(stem, [])), referee_pages=sorted(ref.get(stem, [])),
                         flash_pages=len(flash.get(stem, [])), math_pages=kinds[stem]["math"],
                         grid_pages=kinds[stem]["grid"], latin_share=round(la / max(1, ar + la), 3),
                         french=fr > en and la > 300, english=en >= fr and la > 300,
                         footnote_paras=roles.get("footnote", 0), roles=dict(roles),
                         exp40_page=s40[stem]["page_id"] if stem in s40 else None,
                         exp40_kind=s40[stem]["kind"] if stem in s40 else ("doc" if stem in s40docs else None)))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inventory.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(rows), "documents with PDF + Azure")
    print("with gold done:", sum(1 for r in rows if r["gold_done"]), " bd:", sum(1 for r in rows if r["bd_pages"]),
          " referee:", sum(1 for r in rows if r["referee_pages"]), " jats:", sum(1 for r in rows if r["jats"]),
          " exp40:", sum(1 for r in rows if r["exp40_kind"]))
    print("<=20 pages:", sum(1 for r in rows if r["pages"] <= 20))


if __name__ == "__main__":
    main()
