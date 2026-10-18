"""Local inspection and genuine pointer-recording surface for experiment 42."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
from pathlib import Path
import re
import threading
from urllib.parse import unquote, urlsplit
import uuid

import cv2

from dataset import OUT, json_write
from geometry import normalise, recover, render

HERE = Path(__file__).resolve().parent
IDENT = re.compile(r"^[0-9a-f]{16}$")
INFERENCE_LOCK = threading.Lock()


def capture_record(payload):
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    strokes = payload.get("strokes")
    if not isinstance(strokes, list) or not strokes or len(strokes) > 1000:
        raise ValueError("Expected 1 to 1000 strokes")
    total, previous = 0, -math.inf
    for stroke in strokes:
        if not isinstance(stroke, list) or not stroke:
            raise ValueError("Every stroke needs points")
        total += len(stroke)
        if total > 50000:
            raise ValueError("Maximum 50,000 recorded points")
        for point in stroke:
            if not isinstance(point, list) or len(point) != 6:
                raise ValueError("Points need x,y,t,pressure,tiltX,tiltY")
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in point):
                raise ValueError("Point channels must be finite numbers")
            if max(abs(point[0]), abs(point[1])) > 100000 or not 0 <= point[3] <= 1:
                raise ValueError("Point coordinate or pressure outside range")
            if point[2] < previous:
                raise ValueError("Recorded timestamps must be monotonic")
            previous = point[2]
    text, writer = payload.get("text", ""), payload.get("writer", "")
    style, device = payload.get("style", "handwriting"), payload.get("device", "unknown")
    if not isinstance(text, str) or len(text) > 300 or not isinstance(writer, str) or len(writer) > 100:
        raise ValueError("Invalid transcription or writer ID")
    if style not in ("handwriting", "calligraphy") or device not in ("pen", "mouse", "touch", "mixed", "unknown"):
        raise ValueError("Invalid style or input device")
    if not isinstance(payload.get("checked", False), bool):
        raise ValueError("Checked must be boolean")
    if payload.get("checked") and not text.strip():
        raise ValueError("A checked transcription cannot be empty")
    reference = normalise(strokes)
    image = render(reference)
    ident = uuid.uuid4().hex[:16]
    return dict(schema="inkscript-strokes/1", id=ident, dataset="Local capture", split="unassigned",
                parent=ident, text=text.strip(), writer=writer.strip() or None, style=style,
                provenance="captured_input", device=device, timing="recorded_event_time_ms",
                channels=["x", "y", "t_ms", "pressure", "tilt_x", "tilt_y"],
                raw_strokes=strokes, reference=reference, recovered=recover(image),
                width=image.shape[1], height=image.shape[0],
                transcription_status="checked" if payload.get("checked") else "draft",
                segmentation="whole freely drawn sample; no character boundaries provided",
                created=datetime.now(timezone.utc).isoformat())


class Handler(BaseHTTPRequestHandler):
    def respond(self, code, data, content_type="application/json; charset=utf-8"):
        if isinstance(data, (dict, list)):
            data = json.dumps(data, ensure_ascii=False).encode()
        if isinstance(data, str):
            data = data.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/api/index":
            index_path = OUT / "index.json"
            data = json.loads(index_path.read_text()) if index_path.exists() else dict(summary={}, samples=[])
            for p in sorted((OUT / "captures").glob("*.json")):
                r = json.loads(p.read_text())
                data["samples"].append({k: r[k] for k in ("id", "dataset", "split", "parent", "text", "provenance", "style")}
                                       | dict(ink_coverage=r["recovered"]["ink_coverage"],
                                              failures=len(r["recovered"]["failures"])))
            self.respond(200, data)
            return
        if path == "/api/results":
            p = OUT / "results.json"
            partial = OUT / "runs" / "pilot" / "partial.json"
            data = json.loads(p.read_text()) if p.exists() else (
                json.loads(partial.read_text()) if partial.exists() else dict(arms={}, status="not_run"))
            retrieval = OUT / "retrieval.json"
            if retrieval.exists():
                data["retrieval"] = json.loads(retrieval.read_text())
            self.respond(200, data)
            return
        if path.startswith("/api/sample/"):
            ident = path.rsplit("/", 1)[-1]
            if not IDENT.fullmatch(ident):
                self.respond(400, dict(error="Invalid sample ID"))
                return
            paths = [OUT / d / f"{ident}.json" for d in ("records", "captures")]
            p = next((p for p in paths if p.exists()), None)
            if not p:
                self.respond(404, dict(error="Sample not found"))
                return
            self.respond(200, p.read_bytes())
            return
        routes = {"/assets/": OUT / "assets", "/vendor/": OUT / "vendor"}
        root, relative = HERE / "app", "index.html" if path == "/" else path.lstrip("/")
        for prefix, folder in routes.items():
            if path.startswith(prefix):
                root, relative = folder, path[len(prefix):]
                break
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            self.respond(404, dict(error="Not found"))
            return
        self.respond(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "application/octet-stream")

    def do_POST(self):
        if urlsplit(self.path).path != "/api/captures":
            self.respond(404, dict(error="Not found"))
            return
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc != self.headers.get("Host"):
            self.respond(403, dict(error="Cross-origin writes are not allowed"))
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 2_000_000:
                raise ValueError("JSON body must be between 1 byte and 2 MB")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Content-Type must be application/json")
            payload = json.loads(self.rfile.read(length))
            with INFERENCE_LOCK:
                record = capture_record(payload)
                target = OUT / "captures" / f"{record['id']}.json"
                # Preserve the observation before any optional reader can fail.
                json_write(target, record)
                asset = OUT / "assets" / f"{record['id']}.png"
                asset.parent.mkdir(parents=True, exist_ok=True)
                if not cv2.imwrite(str(asset), render(record["reference"])):
                    raise OSError("Could not write the capture raster; raw record is retained")
                if (OUT / "index.json").exists():
                    try:
                        from retrieval import recognise as retrieve
                        record["retrieval_predictions"] = retrieve(record)
                    except Exception as exc:
                        record.setdefault("prediction_errors", {})["retrieval"] = str(exc)
                        self.log_error("Optional retrieval failed: %s", exc)
                try:
                    from train import recognise
                    result_path = OUT / "results.json"
                    active = json.loads(result_path.read_text()) if result_path.exists() else {}
                    record["prediction_run"] = active.get("run_name", "pilot")
                    record["predictions"] = recognise(record, run_name=record["prediction_run"])
                    record["prediction_provenance"] = "Calliar pilot models; out-of-domain on natural writing"
                except ImportError:
                    record["predictions"] = {}
                except Exception as exc:
                    record.setdefault("prediction_errors", {})["sequence"] = str(exc)
                    self.log_error("Optional sequence inference failed: %s", exc)
                json_write(target, record)
            self.respond(201, record)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.respond(400, dict(error=str(exc)))
        except OSError as exc:
            self.respond(500, dict(error=str(exc)))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8842)
    args = p.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Experiment 42: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
