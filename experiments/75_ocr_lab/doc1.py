"""Experiment 75, document 1: set up the page and our pipeline's existing outputs (no calls, no GPU).

    /home/appuser/inkscript/.venv/bin/python experiments/75_ocr_lab/doc1.py                       # document 1
    /home/appuser/inkscript/.venv/bin/python experiments/75_ocr_lab/doc1.py --dataset doc2 --stem STEM --page N \
        --category older_print                                                                    # any next document

Document 1 (the lead, 2026-11-04): 2399-003-008-002 page 21 (مجلة المعهد العالي للدراسات النوعية, 2023), a clean
modern Arabic academic page: running head, numbered finding, bold run-in subheadings, numbers in parentheses, a
footnote call and its footnote, a running foot, a boxed page number.

1. ingest the article PDF (immutable copy + SHA-256), render page 21 at 300 dpi (pypdfium2 5.12.1, grey PNG);
2. no truth is read here: the owner's instruction (2026-11-04) is a FRESH correction on /lab; the exp-34 gold
   files are not used or shown.  Scores come only from the owner's saved correction (labocr.annotations);
3. our pipeline's outputs for the page that exist on disk: Azure Read (2024-11-30, prebuilt-read) lines and
   paragraphs (experiment 28).  No Gemini/Argon answer exists for this article on this machine, so "ours" here is
   Azure alone;
4. bonus comparator already on disk: experiment 36's PaddleOCR-VL-1.5 full pipeline on this exact page (RTX 5090,
   2026-10-12), imported unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(HERE))

from labocr import ingest as I  # noqa: E402
from labocr import runs as R  # noqa: E402
from labocr.adapters.normalise import normalise_paddle  # noqa: E402
from labocr.schemas import Block, ManifestEntry, PagePrediction, PredictionResult, Resources, Timing  # noqa: E402

ROOT = HERE / "out" / "data"
DATASET = "doc1"
STEM, PAGE = "2399-003-008-002", 21
PID = f"{STEM}_p{PAGE:03d}"
PDF = E / "28_scale/out/azure" / STEM / f"{STEM}.pdf"
AZURE = E / "28_scale/out/azure" / STEM / f"{STEM}.json"
P15 = E / "36_vlm_bakeoff/out/raw/paddle_vl15" / f"{PID}.json"

def azure_prediction(rr) -> PagePrediction:
    d = json.loads(AZURE.read_text(encoding="utf-8"))
    pg = next(p for p in d["pages"] if p["pageNumber"] == PAGE)
    s = 300.0 if pg["unit"] == "inch" else 1.0
    span_lo = pg["spans"][0]["offset"]
    span_hi = span_lo + pg["spans"][0]["length"]
    blocks = []
    paras = [p for p in d["paragraphs"] if p.get("boundingRegions")]   # a few Azure paragraphs carry no region
    for p in paras:
        br = p["boundingRegions"][0]
        if br["pageNumber"] != PAGE:
            continue
        poly = br["polygon"]
        xs, ys = poly[0::2], poly[1::2]
        blocks.append(Block(block_id=f"b{len(blocks)}", type="text", raw_label="paragraph (prebuilt-read: no role)",
                            box=[min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s], box_source="engine",
                            raw_text=p["content"], order=len(blocks), order_source="Azure paragraph order"))
    assert all(span_lo <= p["spans"][0]["offset"] < span_hi for p in paras
               if p["boundingRegions"][0]["pageNumber"] == PAGE)
    raw = dict(page=pg, paragraphs=[p for p in paras if p["boundingRegions"][0]["pageNumber"] == PAGE],
               modelId=d["modelId"], apiVersion=d["apiVersion"])
    res = PredictionResult(request_id="import", page_id=PID, status="succeeded", blocks=blocks, raw=raw,
                           raw_format="azure_read_page", page_text="\n".join(l["content"] for l in pg["lines"]),
                           timing=Timing(null_reasons={"total_s": "read in 2026-08 by experiment 28; not timed per page"}),
                           resources=Resources(device="Azure (hosted, already paid)",
                                               null_reasons={"peak_gpu_mem_mb": "hosted service"}),
                           settings_used=dict(model=d["modelId"], api_version=d["apiVersion"]))
    return PagePrediction(run_id="", attempt_id="", document_id=STEM, page_number=PAGE, page_id=PID,
                          render_id=rr.render_id, width=rr.width, height=rr.height, engine="azure_read",
                          variant="existing", result=res, raw_artifact=None)


ARGON_TYPES = {"paragraph": "paragraph", "heading": "heading", "title": "title", "header": "header", "footer": "footer",
               "page_number": "page_number", "footnote": "footnote", "list_item": "list", "reference": "bibliography",
               "table": "table", "equation": "equation", "caption": "caption", "figure": "figure",
               "abstract": "abstract"}


def argon_prediction(rr) -> PagePrediction | None:
    """Our pipeline's structure layer, when it exists on disk: experiment 41's Argon run (Azure's lines, Gemini 4
    Argon's types / order / fixes).  Blocks = Argon's blocks, box = the union of their Azure line boxes."""
    f = E / "41_azure_structure/out/argon/labels" / f"{STEM}.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text(encoding="utf-8"))
    lines = [ln for ln in d["lines"] if ln["page"] == PAGE]
    if not lines:
        return None
    byb = {}
    for ln in sorted(lines, key=lambda x: (x["order"], x["k"])):
        byb.setdefault(ln["block"], []).append(ln)
    blocks = []
    for n, ls in sorted(byb.items(), key=lambda kv: kv[1][0]["order"]):
        bx = [ln["box"] for ln in ls if ln.get("box")]
        typ = ls[0]["type"]
        blocks.append(Block(block_id=f"b{len(blocks)}", type=ARGON_TYPES.get(typ, "unknown"), raw_label=typ,
                            box=[min(b[0] for b in bx), min(b[1] for b in bx), max(b[2] for b in bx), max(b[3] for b in bx)]
                            if bx else None, box_source="union of Azure line boxes" if bx else None,
                            raw_text="\n".join(ln["text"] for ln in ls), order=len(blocks),
                            order_source="Argon block order",
                            flags=[f"fixed: {ln['azure_text']} -> {ln['text']}" for ln in ls if ln.get("azure_text")]))
    res = PredictionResult(request_id="import", page_id=PID, status="succeeded", blocks=blocks,
                           raw=dict(lines=lines, model=d.get("model"), run=d.get("run")), raw_format="exp41_labels",
                           timing=Timing(null_reasons={"total_s": "batch run of experiment 41, not timed per page"}),
                           resources=Resources(device="Azure + Gemini (hosted, already paid)",
                                               null_reasons={"peak_gpu_mem_mb": "hosted service"}),
                           settings_used=dict(model=d.get("model"), run=d.get("run")))
    return PagePrediction(run_id="", attempt_id="", document_id=STEM, page_number=PAGE, page_id=PID,
                          render_id=rr.render_id, width=rr.width, height=rr.height, engine="azure_argon",
                          variant="existing", result=res, raw_artifact=None)


def paddle15_prediction(rr) -> PagePrediction:
    d = json.loads((E / "36_vlm_bakeoff/out/raw/paddle_vl15" / f"{PID}.json").read_text(encoding="utf-8"))
    raw = {"files": {"res0/page.json": json.dumps(d["output"], ensure_ascii=False), "res0/page.md": d["markdown"]}}
    blocks = normalise_paddle(raw, "pipeline")
    res = PredictionResult(request_id="import", page_id=PID, status="succeeded", blocks=blocks, raw=raw,
                           raw_format="paddle_files",
                           timing=Timing(null_reasons={"total_s": "batched run (chunks of 32): per-page time is a "
                                                                  "throughput share, not comparable"}),
                           resources=Resources(device="RTX 5090 (exp 36)", null_reasons={"peak_gpu_mem_mb": "not kept"}),
                           settings_used=dict(repo=d["repo"], revision=d["revision"], settings=d["settings"]))
    return PagePrediction(run_id="", attempt_id="", document_id=STEM, page_number=PAGE, page_id=PID,
                          render_id=rr.render_id, width=rr.width, height=rr.height, engine="paddle_vl15_exp36",
                          variant="pipeline", result=res, raw_artifact=None)


def main():
    import argparse
    global DATASET, STEM, PAGE, PID, PDF, AZURE
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=DATASET)
    ap.add_argument("--stem", default=STEM)
    ap.add_argument("--page", type=int, default=PAGE)
    ap.add_argument("--category", default="clean_modern_arabic")
    a = ap.parse_args()
    DATASET, STEM, PAGE = a.dataset, a.stem, a.page
    PID = f"{STEM}_p{PAGE:03d}"
    PDF = E / "28_scale/out/azure" / STEM / f"{STEM}.pdf"
    AZURE = E / "28_scale/out/azure" / STEM / f"{STEM}.json"
    src = I.ingest_source(PDF, ROOT)
    rr = I.render_page(src, ROOT, PAGE, dpi=300, grey=True)
    nat = I.native_text(src, ROOT, PAGE)
    entry = ManifestEntry(dataset=DATASET, document_id=STEM, page_id=PID, page_number=PAGE, source_id=src.source_id,
                          render_id=rr.render_id, category=a.category, languages=["ar"],
                          provenance="Mandumah archive scan (S3 PDF with a third-party text layer), exp 28 copy",
                          usage="private Mandumah page: local or rented-GPU processing only; never uploaded to "
                                "hosted APIs or published", split="test",
                          annotation=None, native_text=nat.model_copy(update={"text": None}),
                          force_ocr=True, source_policy="ocr_only")
    mh = I.write_manifest(ROOT, DATASET, [entry])
    ours = R.import_run(ROOT, DATASET, "azure_read", "existing", [azure_prediction(rr)],
                        note="our pipeline's existing Azure Read output (exp 28); no Argon answer exists for this "
                             "article on this machine", settings={"model": "prebuilt-read", "api": "2024-11-30"})
    arg = argon_prediction(rr)
    arg_run = R.import_run(ROOT, DATASET, "azure_argon", "existing", [arg],
                           note="our pipeline's existing Azure + Argon output (experiment 41's argon run)") if arg else None
    p15 = None
    if (E / "36_vlm_bakeoff/out/raw/paddle_vl15" / f"{PID}.json").exists():
        p15 = R.import_run(ROOT, DATASET, "paddle_vl15_exp36", "pipeline", [paddle15_prediction(rr)],
                           note="experiment 36's PaddleOCR-VL-1.5 full pipeline on this page, imported unchanged",
                           settings={"revision": "2a4195faa5e7914c12f2fc601d72c81caf8d2da5"})
    print(json.dumps(dict(source=src.model_dump(), render=rr.model_dump(),
                          native_text=dict(nat.model_dump(), text=(nat.text or "")[:80]), manifest_hash=mh,
                          runs=[ours, arg_run, p15]),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
