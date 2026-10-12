"""PaddleOCR-VL-1.5 full pipeline (PP-DocLayoutV3 + VL-1.5-0.9B on a vLLM server), at the documented defaults.

    /opt/paddle/bin/python paddle_run.py TAG [--smoke] [--chunk N] [--version v1.5]

The VL server must be up on :8118 (served name PaddleOCR-VL-1.5-0.9B). Pages go in chunks (batching is internal,
use_queues); per-page seconds = time between results within a chunk (a throughput share, not a latency). Writes
out/raw/TAG/<page_id>.json holding the pipeline's own JSON verbatim (parsing_res_list, layout_det_res) plus timing.
"""
import argparse, glob, json, os, shutil, socket, sys, time
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("tag"); ap.add_argument("--smoke", action="store_true")
ap.add_argument("--chunk", type=int, default=32); ap.add_argument("--version", default="v1.5")
ap.add_argument("--served", default="PaddleOCR-VL-1.5-0.9B")
a = ap.parse_args()
REPO = {"v1.5": ("PaddlePaddle/PaddleOCR-VL-1.5", "2a4195faa5e7914c12f2fc601d72c81caf8d2da5"),
        "v1.6": ("PaddlePaddle/PaddleOCR-VL-1.6", "c5630abae1d940eafe0697512a0325494b02ab42")}[a.version]
pages = json.load(open("/work/manifest.json"))["pages"]
if a.smoke:
    pages = [p for p in pages if p["split"] == "dev"][:2]
out = f"/work/out/{'smoke' if a.smoke else 'raw'}/{a.tag}"; os.makedirs(out, exist_ok=True)
tmp = f"/work/tmp_{a.tag}"; os.makedirs(tmp, exist_ok=True)
todo = [p for p in pages if not os.path.exists(f"{out}/{p['page_id']}.json")]
by_path = {os.path.abspath(f"/work/{p['file']}"): p for p in todo}

from paddleocr import PaddleOCRVL
import paddleocr, paddlex, paddle
pipe = PaddleOCRVL(pipeline_version=a.version, device="gpu", vl_rec_backend="vllm-server",
                   vl_rec_server_url="http://127.0.0.1:8118/v1", vl_rec_api_model_name=a.served)
print(f"{a.tag}: {len(todo)} pages", flush=True)
T0 = time.time(); n = 0; sessions_ok = 0; errors = []
for i in range(0, len(todo), a.chunk):
    chunk = todo[i:i + a.chunk]; t_prev = time.time(); t_chunk = t_prev
    try:
        for res in pipe.predict([os.path.abspath(f"/work/{p['file']}") for p in chunk]):
            now = time.time()
            ip = os.path.abspath(res["input_path"]); p = by_path.get(ip)
            pid = p["page_id"] if p else os.path.splitext(os.path.basename(ip))[0]
            d = f"{tmp}/{pid}"; shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
            res.save_to_json(save_path=d); res.save_to_markdown(save_path=d)
            js = [json.load(open(f)) for f in glob.glob(f"{d}/*.json")]
            md = [open(f).read() for f in glob.glob(f"{d}/*.md")]
            W, H = Image.open(ip).size
            rec = dict(page_id=pid, tag=a.tag, repo=REPO[0], revision=REPO[1], pipeline_version=a.version,
                       settings="PaddleOCRVL defaults (layout on, threshold 0.5, merge on, shape auto; orientation/"
                                "unwarp/chart/seal off; VL sampling/max_new_tokens/min/max_pixels None = pipeline's own)",
                       chunk=a.chunk, orig_size=[W, H], seen_size=[W, H],
                       resize_note="block_bbox in original-image pixels (pipeline input = 300 dpi JPEG)",
                       status="ok", output=js[0] if len(js) == 1 else js, markdown=md[0] if len(md) == 1 else md,
                       seconds=round(now - t_prev, 2), chunk_started=t_chunk)
            json.dump(rec, open(f"{out}/{pid}.json", "w"), ensure_ascii=False)
            n += 1; t_prev = now
            print(f"{n}/{len(todo)} {pid} {rec['seconds']} s blocks "
                  f"{len(rec['output'].get('parsing_res_list', [])) if isinstance(rec['output'], dict) else '?'}", flush=True)
    except Exception as e:
        errors.append(repr(e)[:2000]); print("CHUNK ERROR", repr(e)[:500], flush=True)
wall = time.time() - T0
prev = json.load(open(f"{out}/run.json")) if os.path.exists(f"{out}/run.json") else {}
sessions = prev.get("sessions", []) + [dict(start=T0, wall_s=round(wall, 1), pages=len(todo), ok=n, errors=errors)]
okp = sum(s["ok"] for s in sessions); wall_all = sum(s["wall_s"] for s in sessions)
done = [f for f in os.listdir(out) if f.endswith(".json") and f != "run.json"]
run = dict(tag=a.tag, repo=REPO[0], revision=REPO[1], pipeline_version=a.version, chunk=a.chunk,
           pages_in_set=len(pages), pages_ok=len(done), sessions=sessions, wall_s=round(wall_all, 1),
           pages_per_hour=round(3600 * okp / wall_all, 1) if wall_all else None,
           paddle=paddle.__version__, paddleocr=paddleocr.__version__, paddlex=paddlex.__version__,
           host=socket.gethostname(), gpu=os.popen("nvidia-smi --query-gpu=name --format=csv,noheader").read().strip())
json.dump(run, open(f"{out}/run.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: run[k] for k in ("pages_ok", "pages_per_hour", "wall_s")}), flush=True)
sys.exit(1 if (errors or n < len(todo)) and a.smoke else 0)
