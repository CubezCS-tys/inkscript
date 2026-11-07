"""Experiment 80: the manifest of what was pulled, and its summary. No network; safe to rerun at any time (it
appends only ids not yet in the manifest, so a stopped pull loses nothing).

    nice -n 19 .venv/bin/python experiments/80_old_print_pull/manifest80.py        -> data/manifest80.jsonl, data/summary80.json

Per document: id, journal, year, decade, printed pages (catalogue), azure_pages, pdf_pages, bytes, whether every
page has Azure lines with polygons, Arabic share of Azure's letters, whether the PDF carries a text layer.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
FETCH = DATA / "fetch"
ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LATIN = re.compile(r"[A-Za-z]")


def one(d: dict) -> dict:
    s = d["id"]
    pdf, js = FETCH / s / f"{s}.pdf", FETCH / s / f"{s}.json"
    r = dict(id=s, jcode=d["jcode"], journal=d["journal"], year=d["year"], decade=d["decade"], type=d["type"],
             printed_pages=d["printed_pages"], pdf=pdf.exists(), json=js.exists(),
             pdf_bytes=pdf.stat().st_size if pdf.exists() else 0, json_bytes=js.stat().st_size if js.exists() else 0)
    if js.exists():
        try:
            a = json.loads(js.read_text(encoding="utf-8"))
            a = a.get("analyzeResult", a)
            pages = a.get("pages") or []
            lines = [len(p.get("lines") or []) for p in pages]
            poly = [sum(1 for l in p.get("lines") or [] if len(l.get("polygon") or []) >= 8) for p in pages]
            text = a.get("content") or ""
            ar, la = len(ARABIC.findall(text)), len(LATIN.findall(text))
            r.update(azure_pages=len(pages), azure_lines=sum(lines), lines_with_polygon=sum(poly),
                     pages_without_lines=sum(1 for n in lines if n == 0),
                     all_lines_polygon=bool(pages) and sum(lines) > 0 and sum(poly) == sum(lines),
                     arabic_share=round(ar / (ar + la), 3) if ar + la else None, model=a.get("modelId"),
                     api=a.get("apiVersion"))
        except Exception as e:                                  # noqa: BLE001
            r["json_error"] = f"{type(e).__name__}: {e}"[:200]
    if pdf.exists():
        try:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(str(pdf))
            n = len(doc)
            chars = 0
            for i in range(min(n, 3)):
                tp = doc[i].get_textpage()
                chars += tp.count_chars()
            r.update(pdf_pages=n, pdf_text_chars_first3=chars)
            doc.close()
        except Exception as e:                                  # noqa: BLE001
            r["pdf_error"] = f"{type(e).__name__}: {e}"[:200]
    return r


def summary(rows: list[dict]) -> dict:
    ok = [r for r in rows if r["pdf"] and r["json"]]
    dec, jr = defaultdict(Counter), defaultdict(Counter)
    for r in ok:
        for C, k in ((dec, r["decade"]), (jr, (r["jcode"], r["journal"]))):
            C[k]["docs"] += 1
            C[k]["pages"] += r.get("azure_pages", 0)
            C[k]["bytes"] += r["pdf_bytes"] + r["json_bytes"]
    odd = dict(
        missing_pdf=[r["id"] for r in rows if not r["pdf"]],
        missing_json=[r["id"] for r in rows if not r["json"]],
        json_error=[r["id"] for r in rows if r.get("json_error")],
        pdf_error=[r["id"] for r in rows if r.get("pdf_error")],
        page_count_mismatch=[r["id"] for r in ok if r.get("azure_pages") is not None and r.get("pdf_pages") is not None
                             and r["azure_pages"] != r["pdf_pages"]],
        pdf_without_text_layer=[r["id"] for r in ok if r.get("pdf_text_chars_first3") == 0],
        no_azure_lines=[r["id"] for r in ok if r.get("azure_lines") == 0],
        some_pages_without_lines=[r["id"] for r in ok if r.get("pages_without_lines")],
        not_all_lines_polygon=[r["id"] for r in ok if r.get("azure_lines") and not r.get("all_lines_polygon")],
        mostly_latin=[r["id"] for r in ok if r.get("arabic_share") is not None and r["arabic_share"] < 0.5],
    )
    return dict(
        documents=len(ok), attempted=len(rows), azure_pages=sum(r.get("azure_pages", 0) for r in ok),
        azure_lines=sum(r.get("azure_lines", 0) for r in ok),
        gb=round(sum(r["pdf_bytes"] + r["json_bytes"] for r in ok) / 1e9, 3),
        journals=len(jr), all_lines_polygon_docs=sum(1 for r in ok if r.get("all_lines_polygon")),
        models=Counter(f'{r.get("model")} {r.get("api")}' for r in ok),
        by_decade={str(k): dict(v) for k, v in sorted(dec.items())},
        by_journal=[dict(jcode=k[0], journal=k[1], **v) for k, v in sorted(jr.items(), key=lambda x: (-x[1]["pages"], x[0]))],
        odd={k: dict(n=len(v), ids=v[:30]) for k, v in odd.items()},
    )


def main():
    plan = [json.loads(l) for l in (DATA / "plan80.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    log = (DATA / "fetch80.log").read_text() if (DATA / "fetch80.log").exists() else ""
    done = {l.split(":")[0] for l in log.splitlines() if re.match(r"^\d{4}-\d{3}-\d{3}-\d{3}: ", l)}
    mf = DATA / "manifest80.jsonl"
    rows = [json.loads(l) for l in mf.read_text(encoding="utf-8").splitlines() if l.strip()] if mf.exists() else []
    seen = {r["id"] for r in rows}
    with mf.open("a", encoding="utf-8") as fh:
        for d in plan:
            if d["id"] in done and d["id"] not in seen:
                r = one(d)
                fh.write(json.dumps(r, ensure_ascii=False) + "\n"); fh.flush()
                rows.append(r)
    S = summary(rows)
    (DATA / "summary80.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in S.items() if k not in ("by_journal", "odd")}, ensure_ascii=False))
    print({k: v["n"] for k, v in S["odd"].items()})


if __name__ == "__main__":
    main()
