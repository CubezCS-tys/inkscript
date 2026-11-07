"""Nuqta-Arabic-OCR-4B worker (transformers, its own env on the GPU host; see workers/setup_gpu.sh).

Official settings from the model card (revision pinned by NUQTA_REVISION): chat template with enable_thinking=False,
greedy decoding (do_sample=False), max_new_tokens=8192, bf16, the card's `prepare` (page-shaped images resized to
~2.4 MP, every image capped at 2.4 MP).  Variants = the card's prompts: as_written (default), markdown, bare.
Raw output: the decoded text, verbatim.  The model gives no boxes; none are invented.
Caveat kept with every result: the card discloses that 234 KITAB-Bench test images were in its training data.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from worker_base import GpuSampler, Worker, image_file, log, serve  # noqa: E402

REPO = "SalahALHaismawi/Nuqta-Arabic-OCR-4B"
PROMPTS = {
    "as_written": "Transcribe the Arabic text in this image exactly as written. Include only the diacritics "
                  "(tashkeel) that are visible in the image.",
    "bare": "Transcribe the Arabic text in this image without any diacritics.",
    "markdown": "Convert this document to Markdown: headings, paragraphs, lists and tables in reading order. "
                "Include only the diacritics visible in the image.",
}


def conv3d_as_linear(model) -> int:
    """The vision patch embedding is a Conv3d whose kernel equals its stride, applied to one patch per row: exactly a
    matrix multiply over the flattened patch.  torch 2.9's bf16 conv3d took ~58 s for one page here (both the cuDNN
    and the native path); the same product as F.linear takes milliseconds.  Same weights, same arithmetic; the
    output text was checked identical on both lab documents.  Off unless the setting asks for it."""
    import torch
    import torch.nn.functional as F
    n = 0
    for mod in model.modules():
        if isinstance(mod, torch.nn.Conv3d) and tuple(mod.kernel_size) == tuple(mod.stride) \
                and tuple(mod.padding) == (0, 0, 0) and mod.groups == 1:
            def fwd(x, mod=mod):
                if tuple(x.shape[-3:]) == tuple(mod.kernel_size):
                    y = F.linear(x.reshape(x.shape[0], -1), mod.weight.reshape(mod.out_channels, -1), mod.bias)
                    return y.view(x.shape[0], mod.out_channels, 1, 1, 1)
                return torch.nn.Conv3d.forward(mod, x)
            mod.forward = fwd
            n += 1
    return n


def prepare(im):
    """The model card's recommended input size, verbatim in logic."""
    from PIL import Image
    w, h = im.size
    page = max(w, h) <= 2 * min(w, h) and min(w, h) >= 450
    if page or w * h > 2_400_000:
        k = (2_400_000 / (w * h)) ** 0.5
        im = im.resize((max(32, int(w * k)), max(32, int(h * k))), Image.LANCZOS)
    return im


class Nuqta(Worker):
    def capabilities(self):
        return dict(engine="nuqta", model=REPO, revision=os.environ.get("NUQTA_REVISION"), full_page=True,
                    crops=True, text_granularity="page", box_granularity="none",
                    output_types=["text", "markdown", "table_html"],
                    image_budget="card's prepare(): pages resized to ~2.4 MP, all images capped at 2.4 MP",
                    configurable=["variant (prompt)", "max_new_tokens"],
                    known_limitations=["no boxes: layout and geometric reading order are unavailable",
                                       "model card: 234 KITAB-Bench test images overlap its training data "
                                       "(macro CER 0.113 without them)"],
                    licence="Apache-2.0 (model card)")

    def health(self):
        v = {"python": sys.version.split()[0]}
        try:
            import torch
            import transformers
            v.update(torch=torch.__version__, transformers=transformers.__version__, cuda=str(torch.version.cuda))
            ok = torch.cuda.is_available()
            dev = torch.cuda.get_device_name(0) if ok else "cpu"
        except Exception as e:  # noqa: BLE001
            return dict(ok=False, detail=f"import failed: {e}", versions=v)
        return dict(ok=ok, detail=dev, device=dev, versions=v)

    def load(self, config):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        self.config = config
        self.variant = config.get("variant", "as_written")
        # "<prompt>_fast" = the same prompt in an env with the card's fast kernels (flash-linear-attention,
        # causal-conv1d: nuqta-ocr[fast]); recorded as its own variant so it never replaces the card default
        self.prompt_key = self.variant
        for suffix in ("_fast", "_speedfix"):
            if self.prompt_key.endswith(suffix):
                self.prompt_key = self.prompt_key[:-len(suffix)]
        s = config.get("settings") or {}
        self.max_new_tokens = int(s.get("max_new_tokens", 8192))
        rev = config.get("model_revision") or os.environ.get("NUQTA_REVISION")
        local = os.environ.get("NUQTA_DIR")          # a snapshot downloaded at exactly `rev` by setup_gpu.sh
        src, kw = (local, {}) if local else (REPO, {"revision": rev})
        t0 = time.monotonic()
        self.processor = AutoProcessor.from_pretrained(src, **kw)
        self.model = AutoModelForImageTextToText.from_pretrained(src, dtype=torch.bfloat16, device_map="auto", **kw)
        self.model.eval()
        self.speedfix = bool(s.get("patch_embed_as_linear"))
        self.patched = conv3d_as_linear(self.model) if self.speedfix else 0
        self.load_s = time.monotonic() - t0
        self.rev = rev
        log("loaded", REPO, rev, f"{self.load_s:.1f}s")
        return dict(load_s=self.load_s)

    def _kernels(self):
        try:
            import causal_conv1d  # noqa: F401
            import fla  # noqa: F401
            return f"fast: flash-linear-attention {fla.__version__}, causal-conv1d {causal_conv1d.__version__}"
        except Exception:  # noqa: BLE001
            return "torch fallback (flash-linear-attention / causal-conv1d not installed)"

    def predict(self, req):
        import torch
        from PIL import Image
        path = image_file(req, self.tmpdir)
        im0 = Image.open(path).convert("RGB")
        im = prepare(im0)
        messages = [{"role": "user", "content": [{"type": "image", "image": im},
                                                  {"type": "text", "text": PROMPTS[self.prompt_key]}]}]
        inputs = self.processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True,
                                                    return_dict=True, return_tensors="pt",
                                                    enable_thinking=False).to(self.model.device)
        grid = inputs.get("image_grid_thw")
        torch.cuda.reset_peak_memory_stats()
        t0 = time.monotonic()
        with GpuSampler() as g, torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        inf = time.monotonic() - t0
        gen = out[0, inputs["input_ids"].shape[1]:]
        n_out = int(gen.shape[0])
        eos = self.model.generation_config.eos_token_id
        eos = set(eos if isinstance(eos, list) else [eos])
        stopped = n_out > 0 and int(gen[-1]) in eos
        text = self.processor.decode(gen, skip_special_tokens=True)
        torch_peak = torch.cuda.max_memory_allocated() / 2 ** 20
        return dict(request_id=req["request_id"], page_id=req["page_id"], status="succeeded",
                    empty=not text.strip(), blocks=[], raw={"text": text}, raw_format="text", page_text=text,
                    truncated=(not stopped) and n_out >= self.max_new_tokens,
                    timing=dict(inference_s=inf, load_s=self.load_s, warm=getattr(self, "_warm", False)),
                    resources=dict(peak_gpu_mem_mb=g.peak, peak_gpu_mem_method=GpuSampler.METHOD +
                                   f"; torch max_memory_allocated {torch_peak:.0f} MB", output_tokens=n_out,
                                   input_pixels=list(im.size), device=torch.cuda.get_device_name(0)),
                    settings_used=dict(variant=self.variant, kernels=self._kernels(),
                                       patch_embed_as_linear=self.speedfix, patched_convs=self.patched, prompt=PROMPTS[self.prompt_key], do_sample=False,
                                       temperature=None, max_new_tokens=self.max_new_tokens, dtype="bfloat16",
                                       enable_thinking=False, prepare="card 2.4 MP", revision=self.rev,
                                       original_pixels=list(im0.size),
                                       image_grid_thw=grid.tolist() if grid is not None else None))


if __name__ == "__main__":
    w = Nuqta()
    _orig = w.predict

    def _p(req):
        r = _orig(req)
        w._warm = True
        return r
    w.predict = _p
    serve(w)
