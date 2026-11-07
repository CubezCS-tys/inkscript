"""FIXTURE worker (CPU, no model): exercises the orchestration only.  It is labelled `is_fixture` and never appears
in results or leaderboards.  Behaviour is driven by the page id so tests can provoke each path:

  "...fail..."   -> a structured failure (invalid_output)
  "...crash..."  -> the process exits mid-request (worker_crash, on the first attempt only when FIXTURE_CRASH_ONCE
                    names a marker file that does not exist yet)
  "...hang..."   -> sleeps past the timeout
  "...empty..."  -> succeeds with no text (empty page)
  otherwise      -> one block of fixed mixed Arabic/Latin text, with a box covering the middle of the page
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "labocr", "adapters"))
from worker_base import Worker, serve  # noqa: E402

FIXED_TEXT = "نصّ تجريبي: «الإسناد» ٣٩٦ — fixture text (not OCR) éàç"


class Fixture(Worker):
    def capabilities(self):
        return dict(engine="fixture", model="fixture (no model)", revision="0", is_fixture=True, full_page=True,
                    crops=True, text_granularity="block", box_granularity="block", output_types=["text"],
                    known_limitations=["not an OCR engine: fixed text for orchestration tests"], licence="n/a")

    def health(self):
        return dict(ok=True, detail="fixture", device="cpu", versions={"python": sys.version.split()[0]})

    def load(self, config):
        self.config = config
        return {}

    def predict(self, req):
        pid = req["page_id"]
        t0 = time.monotonic()
        if "crash" in pid:
            marker = os.environ.get("FIXTURE_CRASH_ONCE")
            if not marker or not os.path.exists(marker):
                if marker:
                    open(marker, "w").close()
                os._exit(3)
        if "hang" in pid:
            time.sleep(3600)
        if "fail" in pid:
            raise ValueError("fixture failure requested by the page id")
        w, h = req["width"], req["height"]
        blocks = [] if "empty" in pid else [dict(block_id="b0", type="paragraph", raw_label="fixture_text",
                                                 box=[w * 0.1, h * 0.4, w * 0.9, h * 0.6], box_source="engine",
                                                 raw_text=FIXED_TEXT, order=0, order_source="engine")]
        return dict(request_id=req["request_id"], page_id=pid, status="succeeded", empty=not blocks,
                    blocks=blocks, raw={"fixture": True, "text": FIXED_TEXT if blocks else ""}, raw_format="json",
                    page_text=FIXED_TEXT if blocks else "", truncated=False,
                    timing=dict(inference_s=time.monotonic() - t0, warm=True),
                    resources=dict(device="cpu", null_reasons={"peak_gpu_mem_mb": "no GPU (fixture)"}),
                    settings_used={})


if __name__ == "__main__":
    serve(Fixture())
