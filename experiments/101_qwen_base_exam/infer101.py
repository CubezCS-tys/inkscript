"""Experiment 101, on the GPU host: send every page image of a set to the local vLLM server (plain Qwen3.5-4B or -9B,
served as "qwen") and keep the raw answer.  Experiment 100's infer100.py (copied 2026-11-24); changes: our own prompt
file (prompts/P1.txt or P2.txt) as the system message, and the user message = the page image followed by one fixed
line of text, USER_TEXT below (the plain chat model was never trained to act on an image alone); --tag recorded.
Standard library + Pillow (both in the vLLM venv).

    python infer101.py --set exam --in /work/in/exam --out /work/out/4B/exam --prompt /work/prompts/P1.txt \
        --max-pixels 2000000 --concurrency 16 --tag "4B exam P1" [--max-tokens 24576] [--limit N]

Temperature 0, thinking off (chat_template_kwargs enable_thinking=False; the template thinks by default),
max_tokens 24,576, no repetition / presence penalty (the card suggests presence_penalty 1.5 for chat; not used, as in
experiment 100: greedy and nothing else).  The image is downscaled
(Lanczos, the card's own snippet) to at most --max-pixels pixels (0 = sent as it is) and sent as PNG when resized,
as the original JPEG bytes otherwise.

One JSON per page: OUT/<stem>_pNNN.json with the raw answer, prompt / completion tokens, finish reason, seconds,
image size sent, settings.  Resumable: a page whose JSON exists is skipped; nothing is ever overwritten (written to
a .tmp file and renamed; a failed request writes OUT/_errors/<page>.json and is retried on the next run).
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import io
import json
import os
import sys
import time
import urllib.request

from PIL import Image

URL = "http://127.0.0.1:8000/v1/chat/completions"
USER_TEXT = "Transcribe this page."


def encode(path, max_pixels):
    im = Image.open(path)
    w, h = im.size
    if max_pixels and w * h > max_pixels:
        scale = min(1.0, (max_pixels / (w * h)) ** 0.5)
        im = im.convert("RGB").resize((round(w * scale), round(h * scale)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return "image/png", buf.getvalue(), (w, h), im.size
    return "image/jpeg", open(path, "rb").read(), (w, h), (w, h)


def one(path, out_dir, prompt, a):
    name = os.path.splitext(os.path.basename(path))[0]
    dst = os.path.join(out_dir, name + ".json")
    if os.path.exists(dst):
        return name, "skip"
    mime, data, orig, sent = encode(path, a.max_pixels)
    body = dict(model="qwen", temperature=0.0, max_tokens=a.max_tokens,
                chat_template_kwargs=dict(enable_thinking=False),
                messages=[dict(role="system", content=prompt),
                          dict(role="user", content=[dict(type="image_url", image_url=dict(
                              url=f"data:{mime};base64,{base64.b64encode(data).decode()}")),
                              dict(type="text", text=USER_TEXT)])])
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            resp = json.loads(r.read())
    except Exception as e:  # noqa: BLE001
        os.makedirs(os.path.join(out_dir, "_errors"), exist_ok=True)
        detail = getattr(e, "read", lambda: b"")()
        json.dump(dict(page=name, error=f"{type(e).__name__}: {e}", detail=detail.decode(errors="replace")[:2000],
                       seconds=round(time.time() - t0, 2)), open(os.path.join(out_dir, "_errors", name + ".json"), "w"))
        return name, "error"
    sec = time.time() - t0
    ch = resp["choices"][0]
    rec = dict(page=name, set=a.set, raw=ch["message"].get("content") or "",
               reasoning=ch["message"].get("reasoning_content") or ch["message"].get("reasoning"),
               finish_reason=ch.get("finish_reason"), usage=resp.get("usage"), seconds=round(sec, 2),
               image_original=orig, image_sent=list(sent), mime=mime,
               settings=dict(max_pixels=a.max_pixels, max_tokens=a.max_tokens, concurrency=a.concurrency,
                             temperature=0.0, enable_thinking=False, prompt=os.path.basename(a.prompt),
                             user_text=USER_TEXT, tag=a.tag),
               started=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)))
    tmp = dst + ".tmp"
    with open(tmp, "w") as f:
        json.dump(rec, f, ensure_ascii=False)
    if os.path.exists(dst):              # never overwrite (a parallel run got there first)
        os.remove(tmp)
        return name, "skip"
    os.replace(tmp, dst)
    return name, "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", required=True)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-pixels", type=int, default=4_100_000)
    ap.add_argument("--max-tokens", type=int, default=24576)
    ap.add_argument("--concurrency", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    prompt = open(a.prompt).read()
    os.makedirs(a.out, exist_ok=True)
    pages = sorted(os.path.join(a.inp, f) for f in os.listdir(a.inp) if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if a.limit:
        pages = pages[:a.limit]
    t0 = time.time()
    n = dict(ok=0, skip=0, error=0)
    print(f"{a.set} [{a.tag}] prompt {a.prompt}: {len(pages)} pages, max_pixels {a.max_pixels}, concurrency {a.concurrency}", flush=True)
    with cf.ThreadPoolExecutor(a.concurrency) as ex:
        futs = [ex.submit(one, p, a.out, prompt, a) for p in pages]
        for k, f in enumerate(cf.as_completed(futs), 1):
            name, st = f.result()
            n[st] += 1
            print(f"{time.strftime('%H:%M:%S')} {k}/{len(pages)} {name} {st} ({time.time() - t0:.0f} s)", flush=True)
    json.dump(dict(set=a.set, pages=len(pages), **n, wall_seconds=round(time.time() - t0, 1),
                   settings=dict(max_pixels=a.max_pixels, max_tokens=a.max_tokens, concurrency=a.concurrency,
                                 prompt=os.path.basename(a.prompt), tag=a.tag)),
              open(os.path.join(a.out, f"_run_{int(t0)}.json"), "w"))
    print("done", n, flush=True)
    sys.exit(1 if n["error"] else 0)


if __name__ == "__main__":
    main()
