"""The worker side of the JSONL protocol — standard library only, so it runs in any engine's own environment
(it is copied next to the workers on a rented GPU).

One JSON object per line on stdin: {"protocol", "id", "op", "payload"}; one reply per line on stdout:
{"protocol", "id", "ok", "result" | "error"}.  Every log line goes to stderr, so nothing can corrupt stdout.
Ops: capabilities, health, load, predict, close.  The core validates replies with labocr.schemas.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import time
import traceback

PROTOCOL_VERSION = "labocr-jsonl/1"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


class Worker:
    """Subclass: capabilities(), health(), load(config), predict(request) -> dict, close()."""

    def capabilities(self) -> dict:
        raise NotImplementedError

    def health(self) -> dict:
        return {"ok": True, "detail": ""}

    def load(self, config: dict) -> dict:
        return {}

    def predict(self, request: dict) -> dict:
        raise NotImplementedError

    def close(self) -> dict:
        return {}


def image_file(request: dict, tmpdir: str) -> str:
    """A local path for the request's image (writes image_b64 to tmpdir)."""
    if request.get("image_path") and os.path.exists(request["image_path"]):
        return request["image_path"]
    if request.get("image_b64"):
        name = os.path.basename(request.get("image_name") or "page.png") or "page.png"
        p = os.path.join(tmpdir, f"{request['request_id']}_{name}")
        with open(p, "wb") as f:
            f.write(base64.b64decode(request["image_b64"]))
        return p
    raise FileNotFoundError("no image in the request")


class GpuSampler:
    """Peak device memory while a block runs: `nvidia-smi --query-gpu=memory.used` sampled every 0.25 s
    (device-wide: valid because the rented GPU runs one worker at a time)."""
    METHOD = "nvidia-smi memory.used, device-wide, sampled every 0.25 s during the call"

    def __init__(self):
        import threading
        self.peak = None
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    def _sample(self):
        import subprocess
        try:
            o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5).stdout
            return max(float(x) for x in o.split()) if o.strip() else None
        except Exception:  # noqa: BLE001
            return None

    def _run(self):
        while not self._stop.is_set():
            v = self._sample()
            if v is not None:
                self.peak = v if self.peak is None else max(self.peak, v)
            self._stop.wait(0.25)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self._t.join(timeout=5)


def classify_exception(e: BaseException) -> str:
    s = f"{type(e).__name__}: {e}".lower()
    if "out of memory" in s or "outofmemory" in s or "cuda error: out of memory" in s:
        return "oom"
    return "other"


def serve(worker: Worker) -> None:
    # the protocol gets a private copy of fd 1; fd 1 itself is pointed at stderr, so anything an engine prints —
    # from Python or from C/C++ — goes to the log, never into the protocol
    proto_fd = os.dup(1)
    os.dup2(2, 1)
    out = os.fdopen(proto_fd, "w", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr
    if os.environ.get("LABOCR_FAULTHANDLER"):
        import faulthandler
        faulthandler.dump_traceback_later(float(os.environ["LABOCR_FAULTHANDLER"]), repeat=True, file=sys.stderr)
    tmpdir = tempfile.mkdtemp(prefix="labocr_")
    worker.tmpdir = tmpdir
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        mid = None
        try:
            msg = json.loads(line)
            mid = msg.get("id")
            if msg.get("protocol") != PROTOCOL_VERSION:
                raise ValueError(f"protocol {msg.get('protocol')!r} != {PROTOCOL_VERSION}")
            op = msg["op"]
            if op not in ("capabilities", "health", "load", "predict", "close"):
                raise ValueError(f"unknown op {op}")
            fn = getattr(worker, op)
            res = fn(msg.get("payload") or {}) if op in ("load", "predict") else fn()
            reply = {"protocol": PROTOCOL_VERSION, "id": mid, "ok": True, "result": res}
        except Exception as e:  # noqa: BLE001 — every failure becomes a structured reply
            log("error:", traceback.format_exc())
            reply = {"protocol": PROTOCOL_VERSION, "id": mid, "ok": False,
                     "error": {"kind": classify_exception(e), "message": f"{type(e).__name__}: {e}"[:4000],
                               "retryable": False}}
        out.write(json.dumps(reply, ensure_ascii=False) + "\n")
        out.flush()
        if reply.get("ok") and msg.get("op") == "close":
            break
