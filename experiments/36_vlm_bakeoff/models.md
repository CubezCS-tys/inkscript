# 36 — Which VLMs to bake off, and exactly how to run each

Research date **2026-10-12**. This is web research only: nothing was downloaded to a GPU and nothing was paid for.
It builds on [../32_open_stack/research/01_models.md](../32_open_stack/research/01_models.md) (candidates and licences) and on
the PaddleOCR-VL smoke test in [../33_kraken/README.md](../33_kraken/README.md). That smoke test took three tries because
the library versions did not match.

Target machine: **one RTX 5090 (32 GB, sm_120)** on Vast. The base image is `pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime`.
Weights come from Hugging Face on the host.

## The picks

| # | Model (HF repo @ revision) | Why | Licence | Weights | Fits 32 GB? |
|---|---|---|---|---|---|
| 1 | **dots.mocr** (= dots.ocr‑1.5) `rednote-hilab/dots.mocr` @ `e539fbb52280393adc081b289ec597430a0f9031` (2026‑07‑04) | **Best open model on Arabic pages** in the only independent multilingual page test (MDPBench AR **83.3**, Gemini‑3‑Pro 89.4). Gives block boxes, categories, reading order, HTML tables and LaTeX. | MIT **plus a "LICENSE AGREEMENT"** (see the flags below) | 6.1 GB bf16 | yes, with plenty of room |
| 1b | the same server with **dots.ocr** `rednote-hilab/dots.ocr` @ `c0111ce6bc07803dbc267932ffef0ae3a51dc951` | Same architecture and the same recipe, so it costs only a model swap. It has the most Arabic evidence (MDPBench AR 75.9, MORE, Misraj, KITAB) and serves as a control for 1. | same | 6.1 GB | yes |
| 2 | **PaddleOCR‑VL‑1.5 full pipeline** (PP‑DocLayoutV3 layout model, then the 0.9B VL on each block) `PaddlePaddle/PaddleOCR-VL-1.5` @ `2a4195faa5e7914c12f2fc601d72c81caf8d2da5` | Second best specialised open model on Arabic (MDPBench AR **71.3**, against 65.8 for v1). Strongest table TEDS of the open models. Fast. Its layout boxes come from a detector, not from the LLM. | Apache‑2.0 | 1.9 GB VL + small layout model | yes (it shares the GPU with Paddle) |
| 2b | the same pipeline with `pipeline_version="v1.6"` (`PaddlePaddle/PaddleOCR-VL-1.6` @ `c5630abae1d940eafe0697512a0325494b02ab42`) | A drop‑in successor (2026‑05‑28) with **no Arabic evidence**, and its card does not mention Arabic. Run it only if 2 works, as a variant. | Apache‑2.0 | 1.9 GB | yes |
| 3 | **Qwen3‑VL‑32B‑Instruct, AWQ 4‑bit** `QuantTrio/Qwen3-VL-32B-Instruct-AWQ` @ `c2d44b1376c73fa120fdb4e216c2ef61c1945498` (base `Qwen/Qwen3-VL-32B-Instruct` @ `0cfaf48183f594c314753d30a4c4974bc75f3ccb`) | A general reader with different failure modes from 1 and 2. It is the largest Qwen‑VL that fits with KV room (choice below). Its "qwenvl html" mode gives blocks with boxes. | Apache‑2.0 | 20.5 GB | yes, with ~7 GB of KV (~14 GB with fp8 KV) |
| 4 (optional) | **amad‑vlm6** `amad-iq/amad-vlm6` @ `7daf90cd5e5706173e159c88ca4e6dc2475a485e` (2026‑09‑09) | An Arabic‑only fine‑tune (a TIES merge of two Qwen2.5‑VL‑7B Arabic OCR models). It is **best of the completed runs in the one third‑party Arabic page benchmark** (Clouda, 462 Misraj/KITAB pages: normalised CER 0.406 against 0.435 for HunyuanOCR). It gives **plain text only**: no boxes, tables or layout. It is a character‑accuracy reference, not a candidate for the main reader. | Apache‑2.0 | 16.6 GB bf16 | yes |

**Qwen choice (32B AWQ against the alternatives).**
- `Qwen3-VL-32B-Instruct-FP8` (35.5 GB) and `Qwen3-VL-30B-A3B-Instruct-FP8` (32.3 GB) **do not fit** in 32 GB.
- `Qwen3.6-27B-FP8` (30.9 GB) and Qwen's own `Qwen3.5-27B-GPTQ-Int4` (30.2 GB, with unquantised parts) do not fit either.
- What fits is a 4‑bit 32B (20.5 GB), a 4‑bit 30B‑A3B MoE (17.9 GB, ~3× faster, but smaller active capacity), or 8B in bf16 (17.5 GB).
- I pick **32B dense AWQ**: it is the most capable reader that fits.
- **Qwen3‑VL‑8B bf16** (`Qwen/Qwen3-VL-8B-Instruct` @ `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`) is the fallback if AWQ misbehaves on sm_120. It is also the only Qwen size with Arabic page evidence (MDPBench AR 63.1). Same client, same prompt.
- **Not Qwen3.5/3.6.** On MDPBench Arabic, Qwen3.5‑9B (53.4) is *worse* than Qwen3‑VL‑8B (63.1). Qwen3.6‑27B has no Arabic document numbers, needs vLLM ≥ 0.19, and is a thinking model by default.

### Left out, and why

- **HunyuanOCR / ‑1.5** (Tencent).
  - Its licence territory **excludes the EU, UK and South Korea**.
  - Section 5(b) **forbids using its outputs to improve any other AI model**, which rules out training Kraken on its readings.
  - It needs CUDA 13 and vLLM ≥ 0.25.1.
  - MDPBench AR is only 68.3; its high MORE score comes from Tencent's own benchmark.
- **Chandra OCR 2**: modified OpenRAIL‑M (free only under $2M revenue, no competing with Datalab). Arabic 68.4 on its own benchmark.
- **Baseer** (`Misraj/Baseer__Nakba`): **CC‑BY‑NC‑SA‑4.0**.
- **MinerU2.5** (MDPBench AR 1.3; the toolkit is AGPL), **GLM‑OCR** (21.7), **DeepSeek‑OCR** (56.9), **olmOCR‑2** (59.0), **Nanonets‑OCR2** (60.2).
- **Qari‑OCR 0.4** and **AIN**: loop tails; normalised CER 2.16 and 2.18 on Clouda.

### Licence flags to show the owner (dots.ocr and dots.mocr)

The Hugging Face tag says MIT, but the repo also ships `dots.mocr LICENSE AGREEMENT`, and its §1.6 says MIT prevails wherever the two conflict. Two clauses still matter here:
- **§3.3(c)**: "Licensees shall not use the tool for unauthorized digitization of publications/document scanning or bulk scraping of content. Any use involving publications or other copyright‑protected materials must first obtain relevant permissions." Mandumah's rights to its journals need to cover this.
- **§5.4**: "Licensee may only use user‑provided input or Outputs for training, fine‑tuning, or improving other AI models if it has obtained the specific and informed consent of data subjects." This touches the plan to train Kraken on VLM silver lines.

The bake‑off itself (evaluation) is fine. Using the outputs for training needs the owner's call.

## The Arabic evidence

**MDPBench**, 3,400 pages in 17 languages, Arabic included. It is from HUST and Kingsoft, so it is independent of the model makers. Mar 2026 ([paper](https://arxiv.org/abs/2603.28130), Table 2).
- The score is 1 − normalised edit distance per page, so higher is better. Headers, footers and footnotes are ignored.
- I read the AR column from the PDF. Each group starts with its average, and the PaddleOCR‑VL‑1.5 card's `.eval_results/mdpbench.yaml` confirms **71.3**.

| Model | AR | All | AR text edit ↓ (cropped blocks, Table 3) | AR layout PageIoU (Table 4) |
|---|---|---|---|---|
| Gemini‑3‑Pro | 89.4 | 86.4 | 0.040 | — |
| **dots.mocr** | **83.3** | 80.5 | **0.059** | **95.4** |
| Doubao‑2.0‑pro | 81.3 | 74.2 | — | — |
| **dots.ocr** | 75.9 | 76.5 | — | — |
| **PaddleOCR‑VL‑1.5** | 71.3 | 78.3 | 0.262 | 87.5 |
| HunyuanOCR | 68.3 | 68.3 | — | — |
| Claude‑Sonnet‑4.6 | 67.8 | 73.1 | — | — |
| PaddleOCR‑VL (v1) | 65.8 | 69.6 | — | 84.6 |
| **Qwen3‑VL‑8B** | 63.1 | 68.3 | 0.412 | — |
| Nanonets‑OCR2‑3B | 60.2 | 64.2 | — | — |
| olmOCR‑2 | 59.0 | 70.4 | — | — |
| DeepSeek‑OCR | 56.9 | 51.8 | — | — |
| Qwen3.5‑9B | 53.4 | 65.7 | — | — |
| GLM‑OCR | 21.7 | 67.3 | — | — |
| MinerU‑2.5‑VLM | 1.3 | 46.3 | — | — |

The paper's own observations bear directly on Mandumah pages:
- "for two‑column Arabic document images, models such as PaddleOCR‑VL‑1.5 and dots.ocr often incorrectly process the text in a left‑to‑right order" (Fig. 7). **Measure reading order on the multi‑column magazines.**
- "PaddleOCR‑VL‑1.5 exhibits issues such as missing content and repetitive outputs when processing Arabic document" (Fig. 6).

Other evidence:
- **MORE** (Tencent, 2026‑07), Arabic text / formula / reading order:
  - dots.ocr 76.2 / 94.0 / 94.6;
  - PaddleOCR‑VL v1 80.5 / 97.4 / 76.8;
  - Qwen3‑VL‑2B 78.9 / 40.7 / 88.5 ([arXiv 2607.02956](https://arxiv.org/html/2607.02956)).
- **Misraj‑DocOCR** (400 Arabic pages, from the Baseer paper), WER / CER: Azure 0.44 / 0.27, Gemini‑2.5‑Pro 0.37 / 0.31, dots.ocr 0.50 / 0.40 ([arXiv 2509.18174](https://arxiv.org/abs/2509.18174)). The paper notes that base Qwen sometimes reverts to left‑to‑right output and handles vowelled text poorly.
- **Clouda Arabic benchmark** (2026‑09, 462 Misraj + KITAB‑reviewed pages, greedy decoding, each model with its card's prompt), normalised Arabic CER:
  - amad‑vlm6 0.4055, amad‑vlm5 0.4062, HunyuanOCR 0.4346;
  - Qari‑0.4 2.16 and AIN 2.18 (loop tails);
  - dots, Paddle and Qwen were not run ([repo](https://github.com/sahrasayed3-crypto/clouda-ocr-model-selection-benchmark)).
- **amad‑vlm6's own card** (KITAB `ocr-eval`, macro over 13 sets): CER 0.235. The card itself warns that WER got worse (0.36 → 0.46), that two sets regressed sharply from over‑generation, and that "gains come mainly from fewer thinking and truncation errors".
- **Inria line crops** (printed Arabic books): Qwen3‑VL‑8B CER 11.3%, against 3.1% for Kraken‑OpenITI ([arXiv 2605.27750](https://arxiv.org/html/2605.27750)).
- **PaddleOCR‑VL v1 paper**, in‑house Arabic edit distance: 0.122, against 0.405 for Qwen2.5‑VL‑72B ([arXiv 2510.14528](https://arxiv.org/html/2510.14528), Table 6a).

None of these sets has old print, vowelled Quran, or Arabic equations. The bake‑off is the first measurement of those.

## Serving stack: one decision for all four

**Use vLLM 0.13.0 for every model.** It pins `torch==2.9.0`, `transformers>=4.56,<5` and `flashinfer-python==0.5.3` (from PyPI metadata).

Why this version:
- It is the last line whose torch matches the base image (torch 2.9.0), and every model here is supported:
  - dots.ocr integrated in vLLM ≥ 0.11.0;
  - Qwen3‑VL ≥ 0.11.0;
  - PaddleOCR‑VL and VL‑1.5 ≥ 0.11.1 (the [vLLM recipe](https://recipes.vllm.ai/PaddlePaddle/PaddleOCR-VL-1.5) says "Architecture is identical to PaddleOCR‑VL");
  - amad‑vlm6 is a Qwen2.5‑VL.
- It keeps **transformers 4.x**, which every remote‑code processor here was written for:
  - dots' own `requirements.txt` pins `transformers==4.57.6`;
  - amad‑vlm6 and Qwen3‑VL configs say 4.56.x.
- The dots.ocr remote code breaks under transformers 5.x: `cache_position` is None ([HF discussion #52](https://huggingface.co/dots-studio/dots.ocr/discussions/52)), and there is a missing video‑processor error ([#38](https://huggingface.co/dots-studio/dots.ocr/discussions/38)).
- vLLM ≥ 0.25 *requires* transformers ≥ 5.5.3, so avoid it here.

**Do not `pip install vllm` into the base image's Python.**
- The PyPI vLLM wheel is compiled against CUDA 12.9 torch: the v0.13.0 release has a `+cu130` wheel but no cu128 one.
- The base image's torch is `2.9.0+cu128`, and pip would treat it as satisfying `torch==2.9.0` and keep it.
- Put each stack in its own venv:

```bash
# vLLM stack (dots, PaddleOCR-VL server, Qwen, amad). This brings its own torch 2.9.0+cu129; the 12.9 runtime
# runs on a 12.8-era driver (>=570) by CUDA minor-version compatibility.
python -m venv /opt/vllm && /opt/vllm/bin/pip install -U pip
/opt/vllm/bin/pip install "vllm==0.13.0" --extra-index-url https://download.pytorch.org/whl/cu129
/opt/vllm/bin/pip install "huggingface_hub[hf_transfer]" openai pillow qwen-vl-utils
/opt/vllm/bin/python -c "import torch, vllm, transformers; print(torch.__version__, torch.version.cuda, vllm.__version__, transformers.__version__, torch.cuda.get_device_capability())"
# expect: 2.9.0+cu129 12.9 0.13.0 4.57.x (12, 0)
```

**Alternative image:** `vllm/vllm-openai:v0.13.0`. It is self‑consistent (torch cu129), but two cautions:
- The image is built on CUDA 12.9, so the NVIDIA container runtime **refuses hosts whose driver is older than CUDA 12.9** (≥ 575). Filter Vast offers on `cuda_vers >= 12.9`.
- Its ENTRYPOINT is `vllm serve`. Use Vast's "args/entrypoint" launch mode, or override the entrypoint to `/bin/bash` for SSH work.

Tags from v0.22 on default to CUDA 13.0 and have `-cu129` variants. They need transformers 5.x from v0.25, so they are not for this set.

**Paddle stack (the layout pipeline client only).** It goes in its own venv, as the PaddleOCR docs require: "the transformers library versions required by vLLM, SGLang and Transformers engine are currently incompatible".

```bash
python -m venv /opt/paddle && /opt/paddle/bin/pip install -U pip
/opt/paddle/bin/pip install paddlepaddle-gpu==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cu129/   # the Blackwell guide's line
/opt/paddle/bin/pip install "paddleocr[doc-parser]==3.7.0"    # pulls paddlex>=3.7,<3.8 (3.7.2 today)
```

Never install these into inkscript's own `.venv`: PaddleX pulls `pypdfium2>=4`, and inkscript pins pypdfium2 5.12.1.

**Blackwell (sm_120) known issues.**
- Torch below 2.7 or cu12.6 wheels have no sm_120 kernels.
- FA3 is Hopper‑only; vLLM picks FA2 or FlashInfer itself, and you can force it with `VLLM_FLASH_ATTN_VERSION=2` if needed.
- One report describes vLLM 0.11.2 on a 5090 segfaulting in CUDA‑graph capture and deadlocking after ~50 requests under 30‑way load (Qwen3‑8B + LoRA + bnb int8; [vLLM forum](https://discuss.vllm.ai/t/bug-segfault-in-pythonsymnodeimpl-and-deadlock-on-rtx-5090-blackwell-with-vllm-0-11-2/2688)). That recipe used bitsandbytes int8, which is unsupported on sm_120 ("Int8 not supported"). **Use no bnb/int8**: AWQ‑Marlin, bf16 and FP8 are fine.
- If graph capture crashes, re‑run with `--enforce-eager`. Keep `--max-num-seqs` modest (≤ 16).
- PaddleOCR's Blackwell guide was verified on an RTX 5070 only, and needs a driver for CUDA ≥ 12.9 for its docker images ([guide](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL-NVIDIA-Blackwell.html)).

**Disk and download.**
- Weights: ~6 + 6 + 2 + 2 + 20.5 + 16.6 ≈ 55 GB. Venvs: ~12 GB.
- Rent ≥ 120 GB of disk. Use `HF_HUB_ENABLE_HF_TRANSFER=1 hf download <repo> --revision <sha>`.
- Serve **one model at a time** on the GPU, and stop each server before starting the next.

**Smoke‑test each model on 2 pages before the run.** That would have saved experiment 33 two of its three tries.

---

## 1. dots.mocr / dots.ocr

Sources: [GitHub rednote-hilab/dots.mocr](https://github.com/rednote-hilab/dots.mocr) (dots.ocr redirects to it), [HF card](https://huggingface.co/rednote-hilab/dots.mocr), and `dots_mocr/utils/prompts.py`, `dots_mocr/model/inference.py`, `dots_mocr/parser.py`, `dots_mocr/utils/consts.py` (read 2026‑10‑12).

**Serve.** These are the authors' flags; the model needs `--trust-remote-code`.

```bash
/opt/vllm/bin/vllm serve rednote-hilab/dots.mocr --revision e539fbb52280393adc081b289ec597430a0f9031 \
  --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --chat-template-content-format string \
  --served-model-name model --trust-remote-code --max-model-len 40960
# dots.ocr: same line with rednote-hilab/dots.ocr --revision c0111ce6bc07803dbc267932ffef0ae3a51dc951
```

The authors also say: "use a model directory name without periods (e.g. `DotsMOCR`)". That applies only to their transformers path when loading from a local directory; with vLLM and a hub id it does not matter.

**Request** (exactly what `inference.py` sends):
- OpenAI chat: one user message with the `image_url` (base64 PNG), then the text **`"<|img|><|imgpad|><|endofimg|>" + prompt`**. The source comments: "if no `<|img|><|imgpad|><|endofimg|>` here, vllm v1 will add `\n` here".
- `temperature=0.1, top_p=0.9, max_completion_tokens=32768`. The parser class defaults to `top_p=1.0`, and `inference_with_vllm` uses 0.9.
- No repetition penalty.

**Prompt, `prompt_layout_all_en`, verbatim** (the default mode):

```
Please output the layout information from the PDF image, including each layout element's bbox, its category, and the corresponding text content within the bbox.

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
```

(The string ends with a newline after the last line.)

Other modes:
- `prompt_ocr` = `Extract the text content from this image.` (text only; drops page header and footer);
- `prompt_layout_only_en` (boxes only);
- `prompt_grounding_ocr` = `Extract text from the given bounding box on the image (format: [x1, y1, x2, y2]).\nBounding Box:\n` + bbox;
- `prompt_scene_spotting` = `Detect and recognize the text in the image.`

**Resolution.**
- `MIN_PIXELS=3136`, `MAX_PIXELS=11289600`, factor 28 (patch 14 × merge 2); the image processor is `Qwen2VLImageProcessor`.
- For images, the parser does **not** resize unless you set min or max pixels; the processor caps the image at 11.29 MP.
- For PDFs it renders at **dpi=200**. Feed each scan at ~200 dpi (an A4 page is then ~1650×2340, ~3.9 MP, ~4.9k visual tokens). Never go above 11.29 MP.

**Output.**
- A JSON list `[{"bbox":[x1,y1,x2,y2],"category":"Text","text":"..."}, ...]` in reading order.
- **bbox is in the pixel space of the image the model saw**, after `smart_resize(h, w, factor=28, 3136, 11289600)`. Scale it by `orig_w/input_w`, `orig_h/input_h` (this is what the parser's `post_process_output` does).
- Tables are `<table>` HTML, formulas LaTeX, everything else Markdown. `Page-header` and `Page-footer` are separate blocks, which is good for us.
- If the JSON does not parse, the parser falls back to "filtered" raw text. **Always save the raw response.**

**Lines.** dots gives no lines. Split each Text block's `text` on `\n` (paragraphs, not printed lines), and attach it to our own line finder's lines (experiment 33) by box overlap.

**Known failures.**
- Endless output on runs of repeated characters (`.....`, `____`). The dot leaders of a table of contents trigger it, so cap `max_completion_tokens` and flag any output that hit the cap.
- The card: "complex tables and formulas remain difficult".
- MDPBench: left‑to‑right reading of two‑column Arabic (dots.ocr).

**Throughput.** dots.ocr did 0.352 pages/s on one A100 (vLLM 0.10.2, 200 concurrent threads, OmniDocBench; [PaddleOCR‑VL paper](https://arxiv.org/html/2510.14528) Table 13). Expect ~0.3–0.5 pages/s on a 5090 with 32–64 concurrent requests (my estimate). The KV cache is tiny: ~28 KB per token.

## 2. PaddleOCR‑VL‑1.5, full pipeline (PP‑DocLayoutV3 + VL‑1.5‑0.9B)

Sources: [HF card 1.5](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5), [HF card 1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6), the [PaddleOCR‑VL tutorial](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html), the [Blackwell guide](https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL-NVIDIA-Blackwell.html), the [vLLM recipe](https://recipes.vllm.ai/PaddlePaddle/PaddleOCR-VL-1.5), and the [1.5 paper](https://arxiv.org/html/2601.21957v2) (two stages: PP‑DocLayoutV3, which predicts polygons and reading order, then the VL on each block).

**Server (VL stage).** This is vanilla vLLM, which the tutorial documents as "Using a service started with the default parameters of vllm serve". The flags are the vLLM recipe's.

```bash
/opt/vllm/bin/vllm serve PaddlePaddle/PaddleOCR-VL-1.5 --revision 2a4195faa5e7914c12f2fc601d72c81caf8d2da5 \
  --trust-remote-code --max-num-batched-tokens 16384 --no-enable-prefix-caching --mm-processor-cache-gb 0 \
  --gpu-memory-utilization 0.5 --port 8118 --served-model-name PaddleOCR-VL-1.5-0.9B
```

Notes on the flags:
- `--gpu-memory-utilization 0.5` leaves room for the Paddle layout model on the same GPU. PaddleOCR's own config example is 0.3, with `max-num-seqs: 128`.
- `--served-model-name`: the recipe says "If you get a 'model does not exist' error, add `--served-model-name PaddleOCR-VL-1.5-0.9B`".

**Fallback server: the authors' own.** Use it if the repo's remote‑code processor fails under transformers 4.57. In a third venv:

```bash
python -m venv /opt/pvlm
/opt/pvlm/bin/pip install "paddleocr[doc-parser]==3.7.0"
/opt/pvlm/bin/paddleocr install_genai_server_deps vllm      # installs paddlex[genai-vllm-server]: vllm==0.10.2, torch==2.8.0, transformers<5
/opt/pvlm/bin/pip install https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.3.14/flash_attn-2.8.3+cu128torch2.8-cp310-cp310-linux_x86_64.whl   # the Blackwell guide's wheel; cp310 = Python 3.10, so pick the wheel matching the venv's Python
/opt/pvlm/bin/paddleocr genai_server --model_name PaddleOCR-VL-1.5-0.9B --backend vllm --port 8118
```

On PaddleOCR v1, experiment 33 found that the current remote code breaks transformers 4.55 and 5.x, while revision `7faba727` works with 4.57.1. On 1.5, smoke‑test the pinned revision first.

**Client (the full pipeline, at the authors' defaults):**

```python
from paddleocr import PaddleOCRVL          # /opt/paddle/bin/python
pipe = PaddleOCRVL(pipeline_version="v1.5", device="gpu",
                   vl_rec_backend="vllm-server", vl_rec_server_url="http://127.0.0.1:8118/v1",
                   vl_rec_api_model_name="PaddleOCR-VL-1.5-0.9B")
for res in pipe.predict(list_of_page_paths):      # pass the whole list: batching is internal (use_queues=True)
    res.save_to_json(save_path="out/paddle")      # keep the JSON; the Markdown drops footnotes
    res.save_to_markdown(save_path="out/paddle")
```

The CLI equivalent is `paddleocr doc_parser --input <img> --pipeline_version v1.5 --vl_rec_backend vllm-server --vl_rec_server_url http://127.0.0.1:8118/v1 --vl_rec_api_model_name PaddleOCR-VL-1.5-0.9B`.

**Defaults to keep** (documented):
- `use_layout_detection=True`, `layout_threshold=0.5`, `merge_layout_blocks=True`, `layout_shape_mode="auto"`;
- `use_doc_orientation_classify=False`, `use_doc_unwarping=False`, `use_chart_recognition=False`, `use_seal_recognition=False`, `format_block_content=False`;
- the VL's `temperature`, `top_p`, `repetition_penalty`, `max_new_tokens`, `min_pixels` and `max_pixels` left `None`, so the pipeline's own settings apply;
- `vl_rec_max_concurrency` tunes throughput.

**Caution:** `markdown_ignore_labels` defaults to `['number','footnote','header','header_image','footer','footer_image','aside_text']`. **The Markdown output silently drops footnotes and running heads.** Score from the JSON.

**Element‑level prompts** (used by the pipeline per block, or directly over plain vLLM with `temperature=0.0`): `OCR:`, `Table Recognition:`, `Formula Recognition:`, `Chart Recognition:`, `Spotting:`, `Seal Recognition:`.
- Card resolution: `max_pixels = 1280*28*28` (1,003,520) per element. For `Spotting:` it is `2048*28*28`, and images under 1500 px on both sides are upscaled ×2 first.
- `Spotting:` on a whole page gives **text lines with positions** (polygons). The card does not document the coordinate format, so check it on the smoke pages. It is the only one of these models that offers line‑level boxes natively.

**Output (JSON):**
- `parsing_res_list` holds one entry per block in reading order: `block_label`, `block_content`, `block_bbox` (original‑image pixels), `block_id`, `block_order`.
- `layout_det_res.boxes` holds `cls_id`, `label`, `score`, `coordinate`.
- Tables are HTML in `block_content`, formulas LaTeX.

**Throughput.** PaddleOCR‑VL v1 did **1.345 pages/s** on one A100 with vLLM 0.10.2 (1.62 pages/s with FastDeploy), batches of 512 (paper Table 13). Expect ~1 page/s on the 5090 (my estimate).

**Known Arabic issues:** missing content and repetition on Arabic, and left‑to‑right reading of two‑column Arabic (MDPBench).

## 3. Qwen3‑VL‑32B‑Instruct (AWQ 4‑bit)

Sources: the [Qwen3‑VL‑32B card](https://huggingface.co/Qwen/Qwen3-VL-32B-Instruct), the [AWQ card](https://huggingface.co/QuantTrio/Qwen3-VL-32B-Instruct-AWQ) ("vLLM >= 0.11.0"; it does not say what is left unquantised), the [vLLM Qwen3‑VL recipe](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3-VL.html), and the Qwen3‑VL cookbooks [document_parsing.ipynb](https://github.com/QwenLM/Qwen3-VL/blob/main/cookbooks/document_parsing.ipynb) and [ocr.ipynb](https://github.com/QwenLM/Qwen3-VL/blob/main/cookbooks/ocr.ipynb).

**Serve:**

```bash
/opt/vllm/bin/vllm serve QuantTrio/Qwen3-VL-32B-Instruct-AWQ --revision c2d44b1376c73fa120fdb4e216c2ef61c1945498 \
  --served-model-name qwen --max-model-len 16384 --max-num-seqs 6 --gpu-memory-utilization 0.92 \
  --limit-mm-per-prompt.video 0 --mm-processor-cache-gb 0 --kv-cache-dtype fp8 --async-scheduling --trust-remote-code
# fallback: Qwen/Qwen3-VL-8B-Instruct --revision 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b, drop --kv-cache-dtype, --max-num-seqs 16
```

**Memory budget:**
- KV per token (bf16) = 2 × 64 layers × 8 KV heads × 128 × 2 B = **256 KB**. With fp8 KV it is 128 KB.
- At 0.92 utilisation, after 20.5 GB of weights and ~3 GB of activations and graphs, ~7 GB is left: ~28k tokens in bf16 or ~56k in fp8.
- A page is ≤ 2,048 visual tokens plus ≤ ~8k output, so 3 pages run concurrently in bf16 KV and ~6 in fp8.
- If fp8 KV hurts quality on the smoke pages, drop it and use `--max-num-seqs 3`.

**Resolution.**
- The processor's default `longest_edge` is **16,777,216 px**, i.e. no practical cap. Resize on the client the way the cookbook does: `qwen_vl_utils.smart_resize(h, w, factor=32, min_pixels=512*32*32, max_pixels=2048*32*32)`, which is ≤ 2.1 MP and ≤ 2,048 visual tokens.
- The cookbook allows `max_pixels=4608*32*32` for "qwenvl markdown". Try that only if the 2,048 setting loses small print such as footnotes and vowel marks.

**Prompts, verbatim from the cookbooks:**
- Whole page with layout and boxes: **`qwenvl html`**. It returns `<html><body><div class="text|title|table|image|formula|..." data-bbox="x1 y1 x2 y2">…</div>…`, with **data-bbox relative 0–1000** (divide by 1000 and multiply by the width or height of the resized image) and tables as `<table>` HTML.
- Whole page Markdown: **`qwenvl markdown`** (tables come out as **LaTeX tabular** after a `<!-- Table (x1, y1, x2, y2) -->` comment; images become coordinate placeholders).
- Plain text, multilingual: `Please output only the text content from the image without any additional descriptions or formatting.`
- Lines with boxes: `Spotting all the text in the image with line-level, and output in JSON format as [{'bbox_2d': [x1, y1, x2, y2], 'text_content': 'text'}, ...].` (relative 0–999/1000; the cookbook divides by 999).
- Use `qwenvl html` for the bake‑off: it is the only Qwen mode that gives tables as HTML and boxes per block. Formulas appear inside `formula` divs, so check on the smoke pages that they are LaTeX.

**Sampling.**
- The card's VL setting: `greedy=false, top_p=0.8, top_k=20, temperature=0.7, repetition_penalty=1.0, presence_penalty=1.5, out_seq_length=16384`. `generation_config.json` has the same values (`do_sample: true`).
- **For OCR use greedy** (`temperature=0`, `presence_penalty=0`), with `max_tokens=8192`:
  - presence_penalty 1.5 penalises every repeated token, and Arabic body text repeats من / في / على constantly;
  - the Inria and Clouda studies both ran VLMs greedy;
  - the Arabic manuscript study warns that a 512‑token cap made Qwen look 10× worse.
- If there is time, run the card's sampled setting on 10 pages as a check.

**Output → lines.**
- Parse with BeautifulSoup: every element with `data-bbox` is a block, in document order (= reading order).
- Lines come from our line finder by box overlap, or from the spotting prompt (a second pass; its boxes are approximate, per experiment 32).

**Throughput (estimate, not reported).**
- 32B AWQ on a 5090: ~40–60 tokens/s per stream, ~150–250 aggregate at 4–6 streams, so **~15–30 s per page** (0.03–0.07 pages/s).
- 8B bf16 is ~3× faster.

## 4. amad‑vlm6 (optional, text only)

Source: the [HF card](https://huggingface.co/amad-iq/amad-vlm6). The architecture is `Qwen2_5_VLForConditionalGeneration` and the config was written with transformers 4.56.1, so it is native in vLLM 0.13 and needs no remote code.

```bash
/opt/vllm/bin/vllm serve amad-iq/amad-vlm6 --revision 7daf90cd5e5706173e159c88ca4e6dc2475a485e \
  --served-model-name amad --max-model-len 20480 --limit-mm-per-prompt.video 0 --gpu-memory-utilization 0.9
```

- Prompt (card, verbatim): `Extract the text in the image. Give me the final text, nothing else.`
- Settings (card): greedy (`do_sample=False`), `max_new_tokens=4096` (the card warns that 500 truncates dense pages), `repetition_penalty=1.05`.
- Resolution: processor default `max_pixels=12845056`, factor 28. Send the same ~200 dpi page as for dots.
- Output: plain text. "On dense pages the model may first emit a `<think>…</think>` block": keep only the text after the last `</think>`.
- No boxes, tables or reading‑order structure. Score characters and hallucinated words only.

## What to record for every page and model

- The raw response;
- output tokens, and whether the output hit the cap (a loop);
- seconds;
- the exact prompt and sampling settings;
- the model revision.

Then score against Azure and the gold pages the same way experiment 33 did: word bags, judged words, and the two gold pages. Add **reading order on multi‑column pages** and **Arabic left‑to‑right reversals**, because both papers name these as the failures of dots and Paddle on Arabic.

## Rough cost

For ~100 pages per model on one 5090 at ~$0.5–1/h:
- dots and dots.ocr: ~10 min;
- Paddle 1.5 and 1.6: ~5 min;
- Qwen 32B: ~40 min;
- amad: ~10 min;
- downloads and venvs: ~30 min.

About 1.5–2 GPU‑hours in all, **≈ $1–2**. These are my estimates; check them against the per‑page seconds after the smoke test.

## Sources (beyond those linked inline)

- MDPBench paper [arXiv 2603.28130](https://arxiv.org/abs/2603.28130); the PaddleOCR‑VL‑1.5 MDPBench yaml [`.eval_results/mdpbench.yaml`](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5/blob/main/.eval_results/mdpbench.yaml)
- dots.mocr licence agreement: [`dots.mocr LICENSE AGREEMENT`](https://huggingface.co/rednote-hilab/dots.mocr/tree/main)
- HunyuanOCR [LICENSE](https://huggingface.co/tencent/HunyuanOCR/blob/main/LICENSE) and [repo](https://github.com/Tencent-Hunyuan/HunyuanOCR) (needs vLLM ≥ 0.25.1, CUDA 13)
- vLLM PyPI metadata (torch, transformers and flashinfer pins per version): https://pypi.org/project/vllm/#history; Docker tags: https://hub.docker.com/r/vllm/vllm-openai/tags
- vLLM GPU install (CUDA 12.9 default wheels, `--extra-index-url https://download.pytorch.org/whl/cu129`): https://docs.vllm.ai/en/v0.13.0/getting_started/installation/gpu/
- PaddleX `genai-vllm-server` extra (pins vllm 0.10.2, torch 2.8.0, transformers<5): https://pypi.org/project/paddlex/3.7.2/
- Qwen3.6‑27B card (vLLM ≥ 0.19; thinking is on by default): https://huggingface.co/Qwen/Qwen3.6-27B
- Arabic manuscript VLM study (truncation and loop traps): https://arxiv.org/html/2608.22366v1
