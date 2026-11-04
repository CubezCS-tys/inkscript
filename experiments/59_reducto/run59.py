"""Experiment 59: Reducto Parse on the approved pages, one JSON per page and variant (resumable).

    nice -n 10 /home/appuser/inkscript/.venv/bin/python run59.py r1 [--sets text] [--ids a,b] [--workers 3]

Variants (docs.reducto.ai, 2026-10-30):
  r1          r-1 full-page model (preview, its best and newest), word + cell citations, HTML tables, no chunking
  r1_verbatim r1 + an agentic text prompt asking for the print as printed (Arabic letters, hamza, vowel marks,
              digits kept) -- "prompted blocks", the documented way to steer r-1
  legacy_ag   legacy Parse, OCR only, agentic text + table scopes (its pre-r-1 top setting)
  legacy      legacy Parse, OCR only, no agentic step
Each page is uploaded once (file id kept in out/uploads.json for the 24 h the upload lives) and reused by every
variant.  Responses (minus nothing) go to out/reducto/<variant>/<page id>.json.
"""
from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common59 as C

OUT = C.OUT
VERBATIM = ("Transcribe the text exactly as printed, letter for letter. Arabic: keep every letter as printed "
            "(do not change ي/ى, ة/ه, hamza forms أ إ آ ء ئ ؤ, do not add or remove vowel marks / shadda / tanween; "
            "do not write Persian ی or ک for Arabic ي or ك); keep Arabic-Indic digits ٠١٢٣٤٥٦٧٨٩ as printed; do not "
            "correct spelling, do not normalise, do not translate, do not summarise.")
VARIANTS = {
    "r1": {"settings": {"model": "r-1", "return_citations": True},
           "formatting": {"table_output_format": "html"},
           "retrieval": {"chunking": {"chunk_mode": "disabled"}}},
    "r1_verbatim": {"settings": {"model": "r-1", "return_citations": True},
                    "enhance": {"agentic": [{"scope": "text", "prompt": VERBATIM}]},
                    "formatting": {"table_output_format": "html"},
                    "retrieval": {"chunking": {"chunk_mode": "disabled"}}},
    "legacy_ag": {"settings": {"model": "legacy", "extraction_mode": "ocr", "ocr_system": "standard"},
                  "enhance": {"agentic": [{"scope": "text"}, {"scope": "table"}], "intelligent_ordering": True},
                  "formatting": {"table_output_format": "html"},
                  "retrieval": {"chunking": {"chunk_mode": "disabled"}}},
    "legacy": {"settings": {"model": "legacy", "extraction_mode": "ocr", "ocr_system": "standard"},
               "formatting": {"table_output_format": "html"},
               "retrieval": {"chunking": {"chunk_mode": "disabled"}}},
}
_lock = threading.Lock()
UP = OUT / "uploads.json"


def file_id(u):
    with _lock:
        ups = json.loads(UP.read_text()) if UP.exists() else {}
        if u["id"] in ups:
            return ups[u["id"]]
    fid = C.upload(Path(u["image"]), u["id"])
    with _lock:
        ups = json.loads(UP.read_text()) if UP.exists() else {}
        ups[u["id"]] = fid
        UP.write_text(json.dumps(ups, indent=0))
    return fid


def one(u, variant):
    f = OUT / "reducto" / variant / f"{u['id']}.json"
    if f.exists():
        return "skip"
    fid = file_id(u)
    st, j = C.parse(fid, VARIANTS[variant], tag=f"parse_{variant}", page_id=u["id"])
    if st != 200:
        return f"error {st}"
    j["chunks_full"] = C.fetch_result(j)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j, ensure_ascii=False))
    return f"ok {j.get('duration', 0):.1f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant", choices=list(VARIANTS))
    ap.add_argument("--sets", default="")
    ap.add_argument("--ids", default="")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    units = json.loads((OUT / "units59.json").read_text())
    if a.sets:
        units = [u for u in units if set(a.sets.split(",")) & set(u["sets"])]
    if a.ids:
        units = [u for u in units if u["id"] in a.ids.split(",")]
    with ThreadPoolExecutor(a.workers) as ex:
        for u, r in zip(units, ex.map(lambda u: one(u, a.variant), units)):
            print(u["id"], r, flush=True)
    print(f"list-price $ so far: {C.credits_used():.3f}")


if __name__ == "__main__":
    main()
