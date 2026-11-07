"""PaddleOCR-VL-1.6 worker (runs in its own env on the GPU host; see workers/setup_gpu.sh).

Variants (EngineConfig.variant), each its own run so stages are labelled and timed separately:
  pipeline      the official complete parsing pipeline: PaddleOCRVL(pipeline_version="v1.6") with its defaults
                (PP-DocLayoutV3 layout + reading order, then the 0.9B VL recogniser on each region)
  bare_ocr      the VL recogniser alone on the whole page: use_layout_detection=False, prompt_label="ocr"
  layout_stage  the layout model alone (LayoutDetection "PP-DocLayoutV3"): boxes, labels, order; no text
Raw output: the files PaddleOCR itself writes (save_to_json / save_to_markdown), kept as text, verbatim.
"""
from __future__ import annotations

import glob
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from worker_base import GpuSampler, Worker, image_file, log, serve  # noqa: E402


def _sha_dir(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "**", "*"), recursive=True)):
        if os.path.isfile(p) and os.path.getsize(p) > 0 and not p.endswith(".lock"):
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            out[os.path.relpath(p, d)] = h.hexdigest()[:16]
    return out


class PaddleVL(Worker):
    def capabilities(self):
        return dict(engine="paddle_vl", model="PaddlePaddle/PaddleOCR-VL-1.6 (+ PP-DocLayoutV3)",
                    revision=os.environ.get("PADDLE_VL_REVISION"), full_page=True, crops=True,
                    text_granularity="block", box_granularity="block",
                    output_types=["text", "table_html", "latex", "markdown", "layout", "reading_order"],
                    image_budget="pipeline defaults (VL rec: max_pixels per region as configured by PaddleOCR)",
                    configurable=["variant", "use_layout_detection", "prompt_label", "temperature", "max_new_tokens",
                                  "min_pixels", "max_pixels"],
                    known_limitations=["block boxes only (no line or word boxes)",
                                       "per-stage timing inside the pipeline is not exposed; stages are timed as "
                                       "separate variants"],
                    licence="Apache-2.0 (model card)")

    def health(self):
        v = {"python": sys.version.split()[0]}
        try:
            import paddle
            v["paddlepaddle"] = paddle.__version__
            dev = paddle.device.get_device()
            v["cuda"] = str(paddle.version.cuda())
        except Exception as e:  # noqa: BLE001
            return dict(ok=False, detail=f"paddle import failed: {e}", versions=v)
        for m in ("paddleocr", "paddlex"):
            try:
                v[m] = __import__(m).__version__
            except Exception as e:  # noqa: BLE001
                v[m] = f"unavailable: {e}"
        return dict(ok=dev.startswith("gpu"), detail=f"device {dev}", device=dev, versions=v)

    def load(self, config):
        self.config = config
        self.variant = config.get("variant", "pipeline")
        s = dict(config.get("settings") or {})
        t0 = time.monotonic()
        if self.variant == "layout_stage":
            from paddleocr import LayoutDetection
            if os.environ.get("PADDLE_LAYOUT_DIR"):
                s.setdefault("model_dir", os.environ["PADDLE_LAYOUT_DIR"])
            self.model = LayoutDetection(model_name=s.pop("layout_model", "PP-DocLayoutV3"), **s)
        else:
            from paddleocr import PaddleOCRVL
            self.predict_kwargs = s.pop("predict_kwargs", {})
            if self.variant == "bare_ocr":
                s.setdefault("use_layout_detection", False)
                self.predict_kwargs.setdefault("prompt_label", "ocr")
            # pinned local snapshots (setup_gpu.sh downloads exact revisions) instead of PaddleX's own download
            if os.environ.get("PADDLE_VL_DIR"):
                s.setdefault("vl_rec_model_dir", os.environ["PADDLE_VL_DIR"])
            if os.environ.get("PADDLE_LAYOUT_DIR") and s.get("use_layout_detection", True):
                s.setdefault("layout_detection_model_name", "PP-DocLayoutV3")
                s.setdefault("layout_detection_model_dir", os.environ["PADDLE_LAYOUT_DIR"])
            self.model = PaddleOCRVL(pipeline_version=s.pop("pipeline_version", "v1.6"), **s)
        self.load_s = time.monotonic() - t0
        dirs = [d for d in (os.environ.get("PADDLE_VL_DIR"), os.environ.get("PADDLE_LAYOUT_DIR")) if d]
        dirs += glob.glob(os.path.expanduser("~/.paddlex/official_models/*"))
        self.model_files = {d: _sha_dir(d) for d in dirs}
        log("loaded", self.variant, f"{self.load_s:.1f}s", list(self.model_files))
        return dict(load_s=self.load_s, model_files=self.model_files)

    def predict(self, req):
        path = image_file(req, self.tmpdir)
        outdir = os.path.join(self.tmpdir, req["request_id"])
        os.makedirs(outdir, exist_ok=True)
        t0 = time.monotonic()
        with GpuSampler() as g:
            if self.variant == "layout_stage":
                results = list(self.model.predict(path))
            else:
                results = list(self.model.predict(path, **self.predict_kwargs))
        inf = time.monotonic() - t0
        files = {}
        for i, res in enumerate(results):
            d = os.path.join(outdir, f"res{i}")
            os.makedirs(d, exist_ok=True)
            res.save_to_json(save_path=d)
            if self.variant != "layout_stage":
                res.save_to_markdown(save_path=d)
            for p in sorted(glob.glob(os.path.join(d, "**", "*"), recursive=True)):
                if p.endswith((".json", ".md")):
                    with open(p, encoding="utf-8") as f:
                        files[os.path.relpath(p, outdir)] = f.read()
        if not results:
            raise RuntimeError("the pipeline returned no result for the page")
        return dict(request_id=req["request_id"], page_id=req["page_id"], status="succeeded",
                    blocks=[], raw={"files": files, "n_results": len(results)}, raw_format="paddle_files",
                    timing=dict(inference_s=inf, load_s=self.load_s, warm=getattr(self, "_warm", False),
                                null_reasons={"stages": "the pipeline does not report per-stage time; see the "
                                                        "layout_stage and bare_ocr variants"}),
                    resources=dict(peak_gpu_mem_mb=g.peak, peak_gpu_mem_method=GpuSampler.METHOD, device="gpu",
                                   null_reasons={"output_tokens": "not reported by the pipeline"}),
                    settings_used=dict(variant=self.variant, **(self.config.get("settings") or {})))

    def close(self):
        return {}


if __name__ == "__main__":
    w = PaddleVL()
    _orig = w.predict

    def _p(req):  # the first page of a run is cold, later pages warm
        r = _orig(req)
        w._warm = True
        return r
    w.predict = _p
    serve(w)
