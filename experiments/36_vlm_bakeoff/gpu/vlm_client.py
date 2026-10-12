"""Read pages with one model served by vLLM (OpenAI API), each model at its authors' recipe (models.md).

    /opt/vllm/bin/python vlm_client.py TAG [--smoke] [--conc N] [--timeout S] [--limit N] [--ids FILE]

Writes out/raw/TAG/<page_id>.json (raw output verbatim, image size the model saw, tokens, finish_reason, seconds)
and out/raw/TAG/run.json (totals, throughput). Pages already done are skipped (resume). Nothing here is tuned on
the pack: prompts and settings are the model cards' / cookbooks' / authors' inference code.
"""
import argparse, base64, io, json, math, os, socket, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import openai

DOTS_PROMPT = """Please output the layout information from the PDF image, including each layout element's bbox, its category, and the corresponding text content within the bbox.

1. Bbox format: [x1, y1, x2, y2]

2. Layout Categories: The possible categories are ['Caption', 'Footnote', 'Formula', 'List-item', 'Page-footer', 'Page-header', 'Picture', 'Section-header', 'Table', 'Text', 'Title'].

3. Text Extraction & Formatting Rules:
    - Picture: For the 'Picture' category, the text field should be omitted.
    - Formula: Format its text as LaTeX.
    - Table: Format its text as HTML.
    - All Others (Text, Title, etc.): Format their text as Markdown.

4. Constraints:
    - The output text must be the original text from the image, with no translation.
    - All layout elements must be sorted according to human reading order.

5. Final Output: The entire output must be a single JSON object.
"""

DOTS_SET = dict(temperature=0.1, top_p=0.9, max_completion_tokens=32768)
MODELS = {
    "dots_mocr": dict(repo="rednote-hilab/dots.mocr", rev="e539fbb52280393adc081b289ec597430a0f9031", served="model",
                      kind="dots", prompt="<|img|><|imgpad|><|endofimg|>" + DOTS_PROMPT, settings=DOTS_SET, conc=32),
    "dots_ocr": dict(repo="rednote-hilab/dots.ocr", rev="c0111ce6bc07803dbc267932ffef0ae3a51dc951", served="model",
                     kind="dots", prompt="<|img|><|imgpad|><|endofimg|>" + DOTS_PROMPT, settings=DOTS_SET, conc=32),
    "qwen3vl32b_awq": dict(repo="QuantTrio/Qwen3-VL-32B-Instruct-AWQ", rev="c2d44b1376c73fa120fdb4e216c2ef61c1945498",
                           served="qwen", kind="qwen", prompt="qwenvl html",
                           settings=dict(temperature=0.0, presence_penalty=0.0, max_tokens=8192), conc=6),
    "qwen3vl32b_awq_card": dict(repo="QuantTrio/Qwen3-VL-32B-Instruct-AWQ", rev="c2d44b1376c73fa120fdb4e216c2ef61c1945498",
                                served="qwen", kind="qwen", prompt="qwenvl html",
                                settings=dict(temperature=0.7, top_p=0.8, presence_penalty=1.5, max_tokens=8192,
                                              extra_body=dict(top_k=20, repetition_penalty=1.0)), conc=6),
    "qwen3vl8b": dict(repo="Qwen/Qwen3-VL-8B-Instruct", rev="0c351dd01ed87e9c1b53cbc748cba10e6187ff3b",
                      served="qwen", kind="qwen", prompt="qwenvl html",
                      settings=dict(temperature=0.0, presence_penalty=0.0, max_tokens=8192), conc=16),
    "amad_vlm6": dict(repo="amad-iq/amad-vlm6", rev="7daf90cd5e5706173e159c88ca4e6dc2475a485e", served="amad",
                      kind="amad", prompt="Extract the text in the image. Give me the final text, nothing else.",
                      settings=dict(temperature=0.0, max_tokens=4096, extra_body=dict(repetition_penalty=1.05)), conc=16),
}


def smart_resize(h, w, factor, min_pixels, max_pixels):
    """qwen_vl_utils / Qwen2VLImageProcessor smart_resize."""
    h_bar = max(factor, round(h / factor) * factor)
    w_bar = max(factor, round(w / factor) * factor)
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((h * w) / max_pixels)
        h_bar = max(factor, math.floor(h / beta / factor) * factor)
        w_bar = max(factor, math.floor(w / beta / factor) * factor)
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (h * w))
        h_bar = math.ceil(h * beta / factor) * factor
        w_bar = math.ceil(w * beta / factor) * factor
    return h_bar, w_bar


def prepare(path, kind, dpi):
    """The image each model's recipe would see, resized here so that what we send is exactly what it sees."""
    im = Image.open(path).convert("RGB")
    W, H = im.size
    if kind == "qwen":     # cookbook: smart_resize(factor 32, 512*32*32 .. 2048*32*32) from the page as given
        h, w = smart_resize(H, W, 32, 512 * 32 * 32, 2048 * 32 * 32)
    else:                  # dots: PDFs rendered at 200 dpi, processor caps (28, 3136, 11289600); amad: same page,
        s = 200.0 / dpi    # its processor's default cap 12845056
        mx = 11289600 if kind == "dots" else 12845056
        h, w = smart_resize(round(H * s), round(W * s), 28, 3136, mx)
    if (w, h) != (W, H):
        im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, format="PNG")
    return (W, H), (w, h), base64.b64encode(buf.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag"); ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--conc", type=int); ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--limit", type=int); ap.add_argument("--ids")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    M = MODELS[a.tag]; conc = a.conc or M["conc"]
    man = json.load(open("/work/manifest.json"))
    pages = man["pages"] if isinstance(man, dict) else man
    if a.smoke:
        pages = [p for p in pages if p["split"] == "dev"][:2]
    if a.ids:
        want = set(open(a.ids).read().split()); pages = [p for p in pages if p["page_id"] in want]
    if a.limit:
        pages = pages[:a.limit]
    out = f"/work/out/{'smoke' if a.smoke else 'raw'}/{a.tag}"; os.makedirs(out, exist_ok=True)
    todo = [p for p in pages if not os.path.exists(f"{out}/{p['page_id']}.json")]
    cli = openai.OpenAI(base_url=f"http://127.0.0.1:{a.port}/v1", api_key="x", timeout=a.timeout, max_retries=0)
    settings = dict(M["settings"])
    print(f"{a.tag}: {len(todo)} of {len(pages)} pages to do, conc {conc}", flush=True)

    def one(p):
        orig, seen, b64 = prepare(f"/work/{p['file']}", M["kind"], p.get("dpi", 300))
        msgs = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": M["prompt"]}]}]
        rec = dict(page_id=p["page_id"], tag=a.tag, repo=M["repo"], revision=M["rev"], prompt=M["prompt"],
                   settings=M["settings"], concurrency=conc, timeout_s=a.timeout, orig_size=list(orig),
                   seen_size=list(seen), resize_note="client-side resize; sent image == image the model saw")
        t0 = time.time(); rec["started"] = t0
        try:
            r = cli.chat.completions.create(model=M["served"], messages=msgs, **settings)
            ch = r.choices[0]
            rec.update(status="ok", output=ch.message.content, finish_reason=ch.finish_reason,
                       completion_tokens=r.usage.completion_tokens, prompt_tokens=r.usage.prompt_tokens)
            cap = settings.get("max_completion_tokens") or settings.get("max_tokens")
            rec["hit_cap"] = ch.finish_reason == "length" or r.usage.completion_tokens >= cap
        except openai.APITimeoutError as e:
            rec.update(status="timeout", output=None, error=repr(e))
        except Exception as e:
            rec.update(status="error", output=None, error=repr(e)[:2000])
        rec["seconds"] = round(time.time() - t0, 2)
        if rec["status"] == "ok":
            json.dump(rec, open(f"{out}/{p['page_id']}.json", "w"), ensure_ascii=False)
        else:   # failures under another name, so a resume retries them once; the record is kept
            json.dump(rec, open(f"{out}/{p['page_id']}.{rec['status']}.json", "w"), ensure_ascii=False)
        return rec

    T0 = time.time(); recs = []
    with ThreadPoolExecutor(conc) as ex:
        for f in as_completed([ex.submit(one, p) for p in todo]):
            r = f.result(); recs.append(r)
            print(f"{len(recs)}/{len(todo)} {r['page_id']} {r['status']} {r.get('finish_reason')} "
                  f"{r.get('completion_tokens')} tok {r['seconds']} s", flush=True)
    wall = time.time() - T0
    # totals over every page record in the directory (so resumed runs add up)
    allrec = [json.load(open(f"{out}/{f}")) for f in sorted(os.listdir(out)) if f.endswith(".json") and f != "run.json"
              and f.count(".") == 1]
    prev = json.load(open(f"{out}/run.json")) if os.path.exists(f"{out}/run.json") else {}
    sessions = prev.get("sessions", []) + [dict(start=T0, wall_s=round(wall, 1), pages=len(todo), conc=conc,
                                                 ok=sum(r["status"] == "ok" for r in recs))]
    okp = sum(s["ok"] for s in sessions); wall_all = sum(s["wall_s"] for s in sessions)
    fails = [f for f in os.listdir(out) if f.count(".") == 2]
    import vllm  # noqa: version only
    run = dict(tag=a.tag, repo=M["repo"], revision=M["rev"], prompt=M["prompt"], settings=M["settings"],
               concurrency=conc, timeout_s=a.timeout, pages_in_set=len(pages), pages_ok=len(allrec),
               hit_cap=sum(bool(r.get("hit_cap")) for r in allrec),
               failed_records=sorted(fails), sessions=sessions, wall_s=round(wall_all, 1),
               pages_per_hour=round(3600 * okp / wall_all, 1) if wall_all else None,
               mean_s_per_page=round(sum(r["seconds"] for r in allrec) / max(1, len(allrec)), 2),
               completion_tokens=sum(r.get("completion_tokens") or 0 for r in allrec),
               vllm=vllm.__version__, host=socket.gethostname(),
               gpu=os.popen("nvidia-smi --query-gpu=name --format=csv,noheader").read().strip())
    json.dump(run, open(f"{out}/run.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: run[k] for k in ("pages_ok", "hit_cap", "pages_per_hour", "wall_s")}), flush=True)
    bad = [r for r in recs if r["status"] != "ok"]
    sys.exit(1 if a.smoke and (bad or any(r.get("finish_reason") != "stop" for r in recs)) else 0)


if __name__ == "__main__":
    main()
