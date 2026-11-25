"""Experiment 102: LoRA fine-tune of Qwen3.5-4B to read one printed line (runs on the rented host; --dry_run on a CPU).

    python train102.py --model DIR --set sets/S.jsonl --crops crops/M --dev sets/dev.jsonl --dev_crops crops/dev \
        --out /work/run_S --epochs 2 [--H 96] [--save_every 100]
    python train102.py --dry_run 50 --tiny_config ../101_qwen_base_exam/card/config_4B.json --model TOKENIZER_DIR ...

Recipe (README, "The recipe"; sources there):
- LoRA on the LANGUAGE MODEL only: every nn.Linear under model.language_model (attention, Gated DeltaNet projections,
  MLP), rank 32, alpha 64, dropout 0.05; vision tower and merger frozen (ms-swift's default freeze_vit/freeze_aligner;
  vLLM serves LoRA on the language backbone of this model, so no merge is needed to evaluate).
- bf16 weights, LoRA weights in fp32 (PEFT's autocast_adapter_dtype), AdamW lr 1e-4, weight decay 0, cosine to 0 with
  3% linear warm-up, gradient clip 1.0, micro-batch 16 x accumulation 4 = 64 lines a step, gradient checkpointing.
- Loss: cross-entropy on the answer tokens only (the line's text + <|im_end|>), token-weighted over the 64 lines; the
  logits are computed only at answer positions (a 248k vocabulary over every prompt token would cost ~4 GB).
- Resumable: run_dir/last/ (adapter + optimizer + scheduler + position) is rewritten every --save_every steps, and
  run_dir/ckpt-<step>/ keeps each adapter (~0.2 GB) for the choice on DEV (eval102.py).  A restart with the same
  arguments continues from last/ at the same place in the same shuffled order.
- Guard: refuses to start if any training or DEV key is in forbidden102.json (guard102.py export), or if any label
  source is not allowed.
Mirrors nothing itself (the lab monitor copies /work/out and /work/run_* every 10 minutes).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data102 as D  # noqa: E402
from cut102 import model_image  # noqa: E402

ALLOWED_SOURCES = {"azure_consensus", "azure_r77", "v6r_judged", "v6r_rule85", "t91_title"}
_STEM = re.compile(r"\d{4}-\d{3}-[\d,]+-\d{3}")


def guard(rows, forbid_path):
    F = json.loads(Path(forbid_path).read_text())
    J, Dd = set(F["journal_codes"]), set(F["document_stems"])
    bad = []
    for r in rows:
        k = r["key"]
        m = _STEM.search(k)
        if k[:4] in J or (m and m.group() in Dd):
            bad.append(k)
        if r.get("label_source") not in ALLOWED_SOURCES:
            bad.append(f"{k}: source {r.get('label_source')}")
    if bad:
        raise SystemExit(f"REFUSED: {len(bad)} forbidden key(s) or source(s), e.g. {bad[:5]}")
    return len(rows)


# ------------------------------------------------------------------------------------------------ examples
class Encoder:
    """line (key, label) -> prompt ids (image tokens expanded) + answer ids + vision tensors."""

    def __init__(self, processor, H: int, system: str, max_answer: int):
        self.p, self.H, self.max_answer = processor, H, max_answer
        self.prompt = processor.apply_chat_template(D.messages(system), tokenize=False, add_generation_prompt=True,
                                                    enable_thinking=False)
        assert self.prompt.rstrip().endswith("</think>"), "the chat template did not switch thinking off"
        self.tok = processor.tokenizer

    def __call__(self, gray, label: str | None):
        img = model_image(gray, self.H)
        enc = self.p(text=[self.prompt], images=[img], return_tensors="pt")
        out = {k: v for k, v in enc.items()}
        out["n_prompt"] = int(enc["input_ids"].shape[1])
        if label is not None:
            a = self.tok(unicodedata.normalize("NFC", label) + D.IM_END, add_special_tokens=False)["input_ids"]
            out["truncated"] = len(a) > self.max_answer
            out["answer"] = a[: self.max_answer]
        return out


class LineData:
    def __init__(self, rows, store, enc):
        self.rows, self.store, self.enc = rows, store, enc

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        return self.enc(self.store.gray(r["key"]), r["label"])


def collate(items, pad_id: int):
    import torch
    L = max(it["n_prompt"] + len(it["answer"]) for it in items)
    B = len(items)
    ids = torch.full((B, L), pad_id, dtype=torch.long)
    att = torch.zeros((B, L), dtype=torch.long)
    lab = torch.full((B, L), -100, dtype=torch.long)
    seq_extra = {}
    other = {}
    for b, it in enumerate(items):
        n, a = it["n_prompt"], torch.tensor(it["answer"], dtype=torch.long)
        ids[b, :n] = it["input_ids"][0]
        ids[b, n:n + len(a)] = a
        att[b, :n + len(a)] = 1
        lab[b, n:n + len(a)] = a
        for k, v in it.items():
            if k in ("input_ids", "attention_mask", "n_prompt", "answer", "truncated"):
                continue
            if hasattr(v, "dim") and v.dim() == 2 and v.shape[0] == 1 and v.shape[1] == n:   # per-token (e.g. mm type ids)
                t = seq_extra.setdefault(k, torch.zeros((B, L), dtype=v.dtype))
                t[b, :n] = v[0]
            elif hasattr(v, "dim"):
                other.setdefault(k, []).append(v)
    batch = dict(input_ids=ids, attention_mask=att, labels=lab, **seq_extra)
    for k, vs in other.items():
        batch[k] = torch.cat(vs, 0)
    batch["_truncated"] = sum(bool(it.get("truncated")) for it in items)
    return batch


# ------------------------------------------------------------------------------------------------ model
def lm_linear_names(model) -> list[str]:
    import torch.nn as nn
    names = [n for n, m in model.named_modules() if isinstance(m, nn.Linear) and ".language_model." in f".{n}."
             and "lm_head" not in n and not n.split(".")[-1].startswith("mtp")]
    if not names:
        raise SystemExit("no Linear layer found under language_model: module names changed, look at model.named_modules()")
    return names


def load_model(a, device):
    import torch
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration
    from peft import LoraConfig, get_peft_model, PeftModel
    processor = AutoProcessor.from_pretrained(a.model)
    if a.dry_run:
        from transformers import Qwen3_5Config
        cfg = json.loads(Path(a.tiny_config).read_text())
        t = cfg["text_config"]
        t.update(hidden_size=128, intermediate_size=256, num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2,
                 head_dim=32, linear_key_head_dim=16, linear_value_head_dim=16, linear_num_key_heads=4,
                 linear_num_value_heads=4, layer_types=["linear_attention"] * 3 + ["full_attention"],
                 mtp_num_hidden_layers=0)
        v = cfg["vision_config"]
        v.update(depth=2, hidden_size=64, intermediate_size=128, num_heads=4, out_hidden_size=128)
        cfg.pop("architectures", None)
        torch.manual_seed(0)
        model = Qwen3_5ForConditionalGeneration(Qwen3_5Config(**cfg)).to(torch.float32)
    else:
        model = Qwen3_5ForConditionalGeneration.from_pretrained(a.model, dtype=torch.bfloat16, attn_implementation=a.attn)
    model.config.use_cache = False
    if a.grad_ckpt:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    targets = lm_linear_names(model)
    if a.resume_adapter:
        model = PeftModel.from_pretrained(model, a.resume_adapter, is_trainable=True)
    else:
        lc = LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=a.dropout, target_modules=targets, bias="none",
                        task_type="CAUSAL_LM")
        model = get_peft_model(model, lc)
    model.to(device)
    ntr = sum(p.numel() for p in model.parameters() if p.requires_grad)
    ntot = sum(p.numel() for p in model.parameters())
    return model, processor, targets, ntr, ntot


def answer_loss(model, batch, fast: bool):
    """Sum of token cross-entropies on the answer tokens, and their count."""
    import torch
    import torch.nn.functional as F
    labels = batch["labels"]
    inputs = {k: v for k, v in batch.items() if k not in ("labels", "_truncated")}
    if fast:
        base = model.get_base_model()
        out = base.model(**inputs, use_cache=False, return_dict=True)
        h = out.last_hidden_state[:, :-1]
        y = labels[:, 1:]
        m = y != -100
        logits = base.lm_head(h[m]).float()
        return F.cross_entropy(logits, y[m], reduction="sum"), int(m.sum())
    out = model(**inputs, labels=labels, use_cache=False)
    n = int((labels[:, 1:] != -100).sum())
    return out.loss * n, n


# ------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="model dir (on the host) or, with --dry_run, a tokenizer/processor dir")
    ap.add_argument("--set", required=True)
    ap.add_argument("--crops", nargs="+", required=True)
    ap.add_argument("--dev")
    ap.add_argument("--dev_crops", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument("--forbid", default=str(HERE / "forbidden102.json"))
    ap.add_argument("--system", default=str(D.SYSTEM_FILE))
    ap.add_argument("--H", type=int, default=96)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--warmup", type=float, default=0.03)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--alpha", type=int, default=64)
    ap.add_argument("--dropout", type=float, default=0.05)
    ap.add_argument("--micro", type=int, default=16)
    ap.add_argument("--accum", type=int, default=4)
    ap.add_argument("--save_every", type=int, default=200)
    ap.add_argument("--dev_loss_n", type=int, default=256)
    ap.add_argument("--max_answer", type=int, default=192)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--seed", type=int, default=102)
    ap.add_argument("--attn", default="sdpa")
    ap.add_argument("--no_grad_ckpt", dest="grad_ckpt", action="store_false")
    ap.add_argument("--slow_loss", dest="fast_loss", action="store_false")
    ap.add_argument("--max_steps", type=int, default=0, help="stop after this many steps (the schedule is still the full one)")
    ap.add_argument("--dry_run", type=int, default=0, help="CPU: a tiny random model from --tiny_config, N lines, 2 steps")
    ap.add_argument("--tiny_config")
    ap.add_argument("--resume_adapter", default="")
    a = ap.parse_args()

    import torch
    from torch.utils.data import DataLoader
    random.seed(a.seed)
    torch.manual_seed(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "train_log.jsonl", "a")

    def say(**kw):
        kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        log.write(json.dumps(kw, ensure_ascii=False) + "\n")
        log.flush()
        print(json.dumps(kw, ensure_ascii=False), flush=True)

    rows = D.read_set(a.set, a.dry_run)
    dev = D.read_set(a.dev, a.dev_loss_n) if a.dev else []
    n_checked = guard(rows + dev, a.forbid)
    store = D.LineStore(a.crops)
    dstore = D.LineStore(a.dev_crops) if a.dev_crops else store
    missing = [r["key"] for r in rows if r["key"] not in store]
    if missing:
        raise SystemExit(f"{len(missing)} training lines have no crop, e.g. {missing[:3]}")
    dev = [r for r in dev if r["key"] in dstore]

    device = "cpu" if a.dry_run else "cuda"
    model, processor, targets, ntr, ntot = load_model(a, device)
    enc = Encoder(processor, a.H, D.system_prompt(a.system), a.max_answer)
    pad_id = processor.tokenizer.pad_token_id if processor.tokenizer.pad_token_id is not None else processor.tokenizer.eos_token_id
    eff = a.micro * a.accum
    steps_per_epoch = max(1, len(rows) // eff)
    total = max(1, int(math.ceil(steps_per_epoch * a.epochs)))
    if a.dry_run:
        total = 2
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    warm = max(1, int(a.warmup * total))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: (s + 1) / warm if s < warm else 0.5 * (1 + math.cos(math.pi * min(1.0, (s - warm) / max(1, total - warm)))))
    step = 0
    last = out / "last"
    if (last / "state.json").exists():
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file
        st = json.loads((last / "state.json").read_text())
        set_peft_model_state_dict(model, load_file(str(last / "adapter_model.safetensors")))
        opt.load_state_dict(torch.load(last / "optimizer.pt", map_location=device))
        sched.load_state_dict(torch.load(last / "scheduler.pt"))
        step = st["step"]
        say(event="resumed", step=step)
    say(event="start", lines=len(rows), dev_loss_lines=len(dev), guard_checked=n_checked, lora_targets=len(targets),
        trainable=ntr, total_params=ntot, steps=total, steps_per_epoch=steps_per_epoch, eff_batch=eff, H=a.H,
        lr=a.lr, rank=a.rank, alpha=a.alpha, prompt_chars=len(enc.prompt), args=vars(a))
    (out / "lora_targets.json").write_text(json.dumps(targets[:40] + ([f"... {len(targets)} in all"] if len(targets) > 40 else [])))

    def order_for(epoch: int):
        idx = list(range(len(rows)))
        random.Random(a.seed * 1000 + epoch).shuffle(idx)
        return idx

    def dev_loss():
        if not dev:
            return None
        model.eval()
        tot = n = 0
        with torch.no_grad():
            for i in range(0, len(dev), a.micro):
                items = [enc(dstore.gray(r["key"]), r["label"]) for r in dev[i:i + a.micro]]
                b = {k: (v.to(device) if hasattr(v, "to") else v) for k, v in collate(items, pad_id).items()}
                with torch.autocast(device, dtype=torch.bfloat16, enabled=not a.dry_run):
                    s, c = answer_loss(model, b, a.fast_loss)
                tot += float(s)
                n += c
        model.train()
        return tot / max(1, n)

    def save(tag_step: int):
        from peft import get_peft_model_state_dict
        from safetensors.torch import save_file
        ck = out / f"ckpt-{tag_step}"
        model.save_pretrained(str(ck))
        tmp = out / "last.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        save_file({k: v.contiguous() for k, v in get_peft_model_state_dict(model).items()}, str(tmp / "adapter_model.safetensors"))
        torch.save(opt.state_dict(), tmp / "optimizer.pt")
        torch.save(sched.state_dict(), tmp / "scheduler.pt")
        (tmp / "state.json").write_text(json.dumps(dict(step=tag_step, args=vars(a))))
        shutil.rmtree(last, ignore_errors=True)
        tmp.rename(last)

    model.train()
    t0, seen, toks, trunc = time.time(), 0, 0, 0
    first = True
    while step < total and (not a.max_steps or step < a.max_steps):
        epoch, pos = divmod(step * eff, steps_per_epoch * eff)
        idx = order_for(epoch)[pos:]
        dl = DataLoader(LineData([rows[i] for i in idx], store, enc), batch_size=a.micro, shuffle=False,
                        num_workers=0 if a.dry_run else a.workers, collate_fn=lambda it: collate(it, pad_id),
                        persistent_workers=False, prefetch_factor=None if a.dry_run else 4)
        acc_s = acc_n = 0
        k = 0
        opt.zero_grad(set_to_none=True)
        for batch in dl:
            trunc += batch.pop("_truncated")
            b = {kk: (v.to(device, non_blocking=True) if hasattr(v, "to") else v) for kk, v in batch.items()}
            with torch.autocast(device, dtype=torch.bfloat16, enabled=not a.dry_run):
                try:
                    s, n = answer_loss(model, b, a.fast_loss)
                except Exception as e:                       # noqa: BLE001
                    if first and a.fast_loss:
                        say(event="fast_loss_failed_fallback", error=repr(e)[:300])
                        a.fast_loss = False
                        s, n = answer_loss(model, b, False)
                    else:
                        raise
            first = False
            (s / max(1, n * a.accum) * 1.0).backward()   # per-micro mean; equal weights across the accumulation
            acc_s += float(s)
            acc_n += n
            seen += b["input_ids"].shape[0]
            toks += int(b["attention_mask"].sum())
            k += 1
            if k % a.accum:
                continue
            gn = torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            step += 1
            if step % 10 == 0 or a.dry_run or step == 1:
                el = time.time() - t0
                mem = torch.cuda.max_memory_allocated() / 2**30 if device == "cuda" else 0
                say(event="step", step=step, of=total, epoch=epoch, loss=round(acc_s / max(1, acc_n), 4),
                    grad_norm=round(float(gn), 3), lr=sched.get_last_lr()[0], lines_per_s=round(seen / el, 2),
                    tokens_per_s=round(toks / el), max_mem_gb=round(mem, 2), truncated=trunc)
            acc_s = acc_n = 0
            if step % a.save_every == 0 or step == total or (a.max_steps and step == a.max_steps):
                dl_ = dev_loss()
                save(step)
                say(event="saved", step=step, dev_loss=None if dl_ is None else round(dl_, 4))
            if step >= total or (a.max_steps and step >= a.max_steps) or step % steps_per_epoch == 0:
                break                                    # an epoch's last < 64 lines are left out of that epoch
    say(event="done", step=step, seconds=round(time.time() - t0), lines_per_s=round(seen / max(1e-6, time.time() - t0), 2))


if __name__ == "__main__":
    main()
