"""Experiment 43, Batch test: a tiny probe job that answers how the Gemini Batch API reads our request shape.
One page image (0656 p1), a one-line prompt, five requests that differ only in how the image is sent:

  none        inlineData (base64 in the JSONL), no media resolution
  low_camel   inlineData + "mediaResolution": {"level": "MEDIA_RESOLUTION_LOW"}
  high_camel  inlineData + "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}   (what run43.py sends)
  low_snake   inline_data + "media_resolution": {"level": "MEDIA_RESOLUTION_LOW"}  (snake_case throughout)
  file_high   fileData (page uploaded through the File API) + mediaResolution HIGH  (run43.py --upload-images)

The prompt token count of each answer shows whether the field was read (LOW ~ 280 image tokens, HIGH ~ 1120).
Spend goes to out/gemini_spend.jsonl like every other call; result in out/batch_test/probe.json.

    .venv/bin/python probe43.py
"""
from __future__ import annotations

import base64
import io
import json
import time

import run43 as R

OUT = R.OUT / "batch_test"
STEM, PAGE = "0656-016-001-011", 1
PROMPT = "Reply with a JSON object {\"first_word\": <the first word printed at the top of this page>}."


def main():
    from google.genai import types
    client = R.C._client()
    a = next(x for x in R.articles("a") if x["stem"] == STEM)
    im = R.ST.send_jpeg(a, PAGE)
    b64 = base64.b64encode(im).decode()
    up = client.files.upload(file=io.BytesIO(im), config=dict(mime_type="image/jpeg"))
    gen = {"maxOutputTokens": 400, "responseMimeType": "application/json", "thinkingConfig": {"thinkingLevel": "LOW"}}
    variants = {
        "none": {"inlineData": {"mimeType": "image/jpeg", "data": b64}},
        "low_camel": {"inlineData": {"mimeType": "image/jpeg", "data": b64},
                      "mediaResolution": {"level": "MEDIA_RESOLUTION_LOW"}},
        "high_camel": {"inlineData": {"mimeType": "image/jpeg", "data": b64},
                       "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}},
        "low_snake": {"inline_data": {"mime_type": "image/jpeg", "data": b64},
                      "media_resolution": {"level": "MEDIA_RESOLUTION_LOW"}},
        "file_high": {"fileData": {"fileUri": up.uri, "mimeType": "image/jpeg"},
                      "mediaResolution": {"level": "MEDIA_RESOLUTION_HIGH"}},
    }
    lines = []
    for k, part in variants.items():
        gc = gen if k != "low_snake" else {"max_output_tokens": 400, "response_mime_type": "application/json",
                                           "thinking_config": {"thinking_level": "LOW"}}
        key = "generationConfig" if k != "low_snake" else "generation_config"
        lines.append({"key": f"probe_{k}", "request": {"contents": [{"role": "user", "parts": [part, {"text": PROMPT}]}],
                                                      key: gc}})
    OUT.mkdir(parents=True, exist_ok=True)
    bf = OUT / "probe.jsonl"
    bf.write_text("".join(json.dumps(x) + "\n" for x in lines))
    upf = client.files.upload(file=str(bf), config=types.UploadFileConfig(display_name="exp43-probe", mime_type="jsonl"))
    job = client.batches.create(model=R.MODEL, src=upf.name, config={"display_name": "exp43-probe"})
    t0 = time.time()
    state = dict(job=job.name, sent=time.strftime("%Y-%m-%d %H:%M:%S"), jpeg_bytes=len(im))
    R.jdump(OUT / "probe.json", state)
    print("probe job", job.name, flush=True)
    while True:
        job = client.batches.get(name=job.name)
        st = job.state.name
        print(f"  {time.strftime('%H:%M:%S')} {st}", flush=True)
        if st in R.DONE_STATES:
            break
        time.sleep(30)
    state.update(final_state=st, secs=round(time.time() - t0), done=time.strftime("%Y-%m-%d %H:%M:%S"))
    pin, pout = R.price("batch")
    res = {}
    if st == "JOB_STATE_SUCCEEDED":
        rows = [json.loads(s) for s in client.files.download(file=job.dest.file_name).decode().splitlines() if s.strip()]
        for row in rows:
            resp = row.get("response") or {}
            um = resp.get("usageMetadata") or {}
            tin, think = um.get("promptTokenCount") or 0, um.get("thoughtsTokenCount") or 0
            tout = (um.get("candidatesTokenCount") or 0) + think
            usd = tin / 1e6 * pin + tout / 1e6 * pout
            if tin or tout:
                R.log_spend(row.get("key"), tin, tout, think, usd, "probe", "batch")
            cand = (resp.get("candidates") or [{}])[0]
            res[row.get("key")] = dict(usage=um, finish=cand.get("finishReason"), error=row.get("error"),
                                       text="".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts")
                                                    or [] if not p.get("thought")), usd=round(usd, 6),
                                       response_keys=sorted(resp))
    state["results"] = res
    R.jdump(OUT / "probe.json", state)
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
