"""Experiment 75: a COMBINATION run: PaddleOCR-VL-1.6's layout (regions, kinds, reading order) with Nuqta's text,
Nuqta reading each Paddle region as a crop (12 px margin), in Paddle's order.  Not an engine of its own: labelled
"combination" everywhere.

    W=$(python3 gpu_session.py worker nuqta)
    ../../.venv/bin/python combo.py --dataset doc3 --page 0877-007-027-003_p004 --paddle-run RUN --worker-json "$W"

Nuqta runs with the card's settings plus the speed fix (patch embedding as a matrix product: identical text).
Crops follow the card's own `prepare` rule (a page-shaped crop is enlarged, others are read as they are).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cv2  # noqa: E402

from labocr import ingest as I  # noqa: E402
from labocr import runs as R  # noqa: E402
from labocr.adapters.transport import SubprocessAdapter  # noqa: E402
from labocr.schemas import (Block, EngineConfig, PagePrediction, PageRequest, PredictionResult, Resources,  # noqa: E402
                            Timing)

ROOT = HERE / "out" / "data"
PAD = 12


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--paddle-run", required=True)
    ap.add_argument("--worker-json", required=True)
    a = ap.parse_args()
    e = {x.page_id: x for x in I.read_manifest(ROOT, a.dataset)}[a.page]
    rr = I.render_by_id(ROOT, e.render_id)
    img = cv2.imread(str(ROOT / rr.path), cv2.IMREAD_UNCHANGED)
    pad = R.load_predictions(ROOT, a.paddle_run)[a.page]
    # every region with a box, even one Paddle left empty (exactly where another reader may recover text)
    regions = sorted([b for b in pad.result.blocks if b.box is not None and b.type != "figure"], key=lambda b: b.order)
    settings = {"max_new_tokens": 8192, "patch_embed_as_linear": True}
    ad = SubprocessAdapter(json.loads(a.worker_json), stderr_path=str(ROOT / "combo_worker.stderr.log"),
                           timeouts={"predict": 900})
    health = ad.health()
    ad.load(EngineConfig(engine="nuqta", variant="as_written_speedfix", settings=settings,
                         model_revision="6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c"))
    blocks, raws, t_inf, peak = [], [], 0.0, 0.0
    t0 = time.monotonic()
    try:
        for i, b in enumerate(regions):
            x0, y0, x1, y1 = [int(round(v)) for v in b.box]
            x0, y0 = max(0, x0 - PAD), max(0, y0 - PAD)
            x1, y1 = min(rr.width, x1 + PAD), min(rr.height, y1 + PAD)
            ok, buf = cv2.imencode(".png", img[y0:y1, x0:x1])
            req = PageRequest(request_id=f"crop{i}", page_id=a.page, page_number=e.page_number, render_id=rr.render_id,
                              width=x1 - x0, height=y1 - y0, image_b64=base64.b64encode(buf.tobytes()).decode(),
                              image_name=f"crop{i}.png", crop=[x0, y0, x1, y1])
            rep = ad.predict_raw(req)
            raws.append(dict(block=b.block_id, paddle_label=b.raw_label, crop=[x0, y0, x1, y1], reply=rep))
            t_inf += rep["timing"]["inference_s"]
            peak = max(peak, rep["resources"].get("peak_gpu_mem_mb") or 0)
            blocks.append(Block(block_id=f"b{i}", type=b.type, raw_label=f"paddle:{b.raw_label}", box=b.box,
                                box_source=f"PaddleOCR-VL-1.6 region ({a.paddle_run})", raw_text=rep["page_text"].strip(),
                                order=i, order_source="PaddleOCR-VL-1.6 reading order",
                                flags=[f"crop {[x0, y0, x1, y1]}", f"nuqta input {rep['resources'].get('input_pixels')}"]
                                + (["truncated"] if rep.get("truncated") else [])))
            print(f"crop {i} {b.raw_label} {rep['timing']['inference_s']:.1f}s", flush=True)
    finally:
        ad.close()
    wall = time.monotonic() - t0
    res = PredictionResult(request_id="combo", page_id=a.page, status="succeeded", blocks=blocks,
                           raw=dict(crops=raws, padding_px=PAD, paddle_run=a.paddle_run), raw_format="combo_crops",
                           page_text="\n".join(b.raw_text for b in blocks),
                           timing=Timing(inference_s=t_inf, total_s=wall, load_s=ad.load_seconds,
                                         stages={"crops": float(len(regions))}),
                           resources=Resources(peak_gpu_mem_mb=peak or None,
                                               peak_gpu_mem_method="max over crops of the worker's nvidia-smi sampling",
                                               device=health.device),
                           settings_used=dict(settings, prompt="as_written", padding_px=PAD, layout_from=a.paddle_run))
    pred = PagePrediction(run_id="", attempt_id="", document_id=e.document_id, page_number=e.page_number,
                          page_id=a.page, render_id=rr.render_id, width=rr.width, height=rr.height,
                          engine="combo_paddle_nuqta", variant="regions_speedfix", result=res, raw_artifact=None)
    rid = R.import_run(ROOT, a.dataset, "combo_paddle_nuqta", "regions_speedfix", [pred], imported=False,
                       note=f"COMBINATION: PaddleOCR-VL-1.6 regions + order ({a.paddle_run}) read by Nuqta-4B "
                            f"(speed fix), {len(regions)} crops, {PAD} px margin",
                       settings=dict(settings, paddle_run=a.paddle_run, padding_px=PAD))
    print(json.dumps(dict(run=rid, crops=len(regions), inference_s=round(t_inf, 1), wall_s=round(wall, 1), peak_mb=peak)))


if __name__ == "__main__":
    main()
