# Experiment 75: dependencies and licences

Checked on 2026-11-04 from the model cards at the pinned revisions (copies in `out/cards/`) and PyPI. A
downloadable weight file is not the same thing as permission for commercial deployment, so each licence is
recorded as its card states it. These notes are not legal advice.

## Models (run on the rented GPU only; weights never on this machine)

| Model | Pinned revision | Weights (sha256 checked on the host) | Licence (card) | Notes |
|---|---|---|---|---|
| `PaddlePaddle/PaddleOCR-VL-1.6` (0.9B VL recogniser) | `c5630abae1d940eafe0697512a0325494b02ab42` | model.safetensors `85a479d5…aed71db` (1.92 GB) | Apache-2.0 | Its card does not list Arabic; experiment 36 found v1.5 weak on Arabic two-column pages |
| `PaddlePaddle/PP-DocLayoutV3` (layout + reading order) | `241f8bdfc77a7c7bee915a5057aaee58c235a8d3` | inference.pdiparams `70bd316b…2b45c137` (131 MB) | Apache-2.0 | |
| `SalahALHaismawi/Nuqta-Arabic-OCR-4B` (4.75B, Qwen3.5-4B base) | `6a8cdd625f7360203bfce10ef48a41c4a5c1ad3c` | model.safetensors `486c438b…2c0f38c` (9.5 GB) | Apache-2.0 | **Benchmark caveat (card):** "234 KITAB test images (all 200 KHATT-paragraph pages, the 10 HistoricalBooks pages, 13 Muharaf and 11 KHATT-line images) also appear in public datasets we trained on. Without them the macro CER is 0.113." Its public scores do not stand in for our own pages. The ID/passport training data includes 20 images "from two projects with no open licence stated" (card). |
| Earlier, imported: `PaddlePaddle/PaddleOCR-VL-1.5` | `2a4195faa5e7914c12f2fc601d72c81caf8d2da5` | (experiment 36) | Apache-2.0 | exp 36's output for this page, unchanged |
| Ours: Azure AI Document Intelligence `prebuilt-read` 2024-11-30 | n/a | n/a | commercial service | existing output (experiment 28); no new call |

The download script (`workers/setup_gpu.sh`) fetches each repo with `hf download --revision <sha>`. The workers
load those local snapshots (`PADDLE_VL_DIR`, `PADDLE_LAYOUT_DIR`, `NUQTA_DIR`), so PaddleX never fetches a newer
copy on its own. The three hashes in the table match Hugging Face's LFS sha256 for those revisions
(`/work/setup/weights.sha256`).

## Engine environments on the GPU host (its own venvs; nothing GPU-related on this machine)

| env | packages (exact, from `pip freeze` on the host) | licence |
|---|---|---|
| base image | `pytorch/pytorch:2.9.0-cuda12.8-cudnn9-runtime` (torch 2.9.0+cu128, torchvision 0.24.0+cu128) | BSD-3 (PyTorch) |
| `/opt/paddle` | paddlepaddle-gpu 3.2.1 (cu126 wheel, the card's command; cu129 on Blackwell cards such as the RTX 5090), paddleocr 3.7.0, paddlex 3.7.2, safetensors 0.7.0 | Apache-2.0 |
| `/opt/nuqta` (system site packages) | transformers 5.8.1 (the version in Nuqta's config.json), accelerate 1.15.0, safetensors 0.8.0 | Apache-2.0 |
| `/opt/nuqta_fast` (session 2 only, by hand) | the same + flash-linear-attention 0.6.0, causal-conv1d 1.7.0 (prebuilt wheel `cu12torch2.9cxx11abiTRUE-cp311`): the card's `nuqta-ocr[fast]` kernels | MIT / BSD-3-Clause |
| `/opt/hf` | huggingface_hub ≥ 1.0 (downloads only) | Apache-2.0 |

## The core (the repo's `.venv`, this machine)

| package | version | licence | use |
|---|---|---|---|
| pydantic | 2.14.1 (already there) | MIT | schemas |
| pypdfium2 | **5.12.1** / pdfium 152.0.7947.0 (the repo's pin, checked) | Apache-2.0 / BSD-3 (PDFium) | rendering, native-text inspection |
| opencv-python-headless, numpy | already there | Apache-2.0 / BSD-3 | image encode, crops |
| lxml | already there | BSD-3 | HTML table cells |
| **rapidfuzz** | **3.14.6, added 2026-11-04** | MIT | edit operations (CER/WER counts), locating truth lines in an engine's text |
| inkscript.gold.text | in repo | repo | the `faithful` / `folded` normalisations (experiment 34) |

The Desk side (`desk/lab.py`) needs only pydantic and the standard library. Scoring runs as a subprocess in the
repo's venv.

Not added: Typer (the CLI uses argparse), FastAPI for the lab itself (the Desk's API serves `/lab`), React/Vite (the
Desk's Next.js app is reused), and `uv` with a lockfile. This is an experiment folder inside an existing repo, and it
uses the repo's venv.
