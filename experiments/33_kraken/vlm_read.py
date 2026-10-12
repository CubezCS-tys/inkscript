"""Runs ON the rented GPU: PaddleOCR-VL-0.9B (transformers, the model card's own element-level recipe, prompt "OCR:",
greedy, bf16) on every line and page of vlm.tar. Writes vlm_out.jsonl: {kind, id, text, seconds, new_tokens}."""
import json, sys, time
from pathlib import Path
import torch
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

P = "PaddlePaddle/PaddleOCR-VL"
import os
REV = os.environ.get("REV")                                             # a model revision whose code matches the installed transformers
model = AutoModelForCausalLM.from_pretrained(P, trust_remote_code=True, torch_dtype=torch.bfloat16, revision=REV).to("cuda").eval()
proc = AutoProcessor.from_pretrained(P, trust_remote_code=True, revision=REV)
items = json.load(open("items.json"))
with open("vlm_out.jsonl", "w") as f:
    for kind, ids, ext, cap in (("line", items["lines"], ".png", 512), ("page", items["pages"], ".jpg", 4096)):
        for i in ids:
            im = Image.open(Path(kind + "s") / f"{i}{ext}").convert("RGB")
            msgs = [{"role": "user", "content": [{"type": "image", "image": im}, {"type": "text", "text": "OCR:"}]}]
            t = time.time()
            try:
                inp = proc.apply_chat_template(msgs, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to("cuda")
                out = model.generate(**inp, max_new_tokens=cap, do_sample=False)
                new = out[0][inp["input_ids"].shape[1]:]
                text = proc.decode(new, skip_special_tokens=True); n = int(new.shape[0])
            except Exception as e:
                text, n = "ERROR " + repr(e)[:300], 0
            f.write(json.dumps(dict(kind=kind, id=i, text=text, seconds=round(time.time() - t, 2), new_tokens=n, cap=cap), ensure_ascii=False) + "\n"); f.flush()
print("done")
