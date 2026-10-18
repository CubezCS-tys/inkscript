# 42 - Recorded traces versus recovered paths

**Question.** How much of a useful writing representation survives replacing
recorded pen traces with a traversal inferred from the finished image?

**Status (2026-10-17/18).** Implemented and running locally, authorised by the
owner. First data source: Calliar. Its traces are human retracings of existing
calligraphy, not the original calligraphers' motion. We compare recordings of
those retracings against paths recovered from their rasterisations, not from
the original artworks. This does not establish natural handwriting,
historical stroke order, or archive OCR performance.

Outputs, downloaded data and local models live under `out/`. No paid API is
used. The original experiment-16 results and D19 remain unchanged.

## Reproduce

Run from the repo root. Preparation and the viewer need only the project's
normal dependencies. Training uses experiment 16's existing CPU PyTorch
environment; browser checks use experiment 40's existing Playwright environment.

```sh
.venv/bin/python experiments/42_stroke_recovery/fetch.py
.venv/bin/python experiments/42_stroke_recovery/dataset.py
.venv/bin/python experiments/42_stroke_recovery/assets.py
.venv/bin/python experiments/42_stroke_recovery/retrieval.py
experiments/16_feel/out/torchenv/bin/python experiments/42_stroke_recovery/train.py
experiments/16_feel/out/torchenv/bin/python experiments/42_stroke_recovery/serve.py --port 8842
```

Open `http://127.0.0.1:8842`. The server defaults to loopback; `--host` can
change it when intentionally exposing the tool. A machine running the browser
elsewhere can forward port 8842 over SSH. No external service or key is needed
after the dataset and viewer assets have been cached.

Preparation resumes from saved records. After changing rasterisation,
normalisation, recovery or features, run `dataset.py --refresh` to recompute
paths and arrays together; do not reuse a named model run across changed data.

## Data and safeguards

- 2,500 source drawings, 7,507 validated word samples: 6,027 train, 734
  validation, 746 test. Reject 30 drawings whose primitive annotation sequence
  does not match the filename transcription; reasons in `out/audit.json`.
- Follow the upstream drawing splits; all words of one drawing stay together.
  Exact normalised word-raster duplicates are checked, preferring held-out
  copies; none found. Writer/style IDs are unavailable, so this is not a
  writer- or style-disjoint evaluation. Near-duplicate drawings are not ruled out.
- Word boundaries come from upstream annotations: **oracle segmentation**.
  Character/stroke labels never enter recognition features. The reference
  sequence still benefits from the annotators' prescribed character order.
- Raw upstream download, MIT licence, revision and SHA-256 hashes in
  `out/upstream/manifest.json`. [Research and provenance](research.md).
- All three arms use the same samples, including unsuccessful recovery.
  Measured geometry coverage uses a one-pixel tolerance; it is not reading
  accuracy. Controlled rasterisation is 384 x 128 with a uniform 3 px stroke.

## Recovery and recognition

`geometry.py` uses the existing `penpath.thin`, `letters.analyse`,
`penpath.unroll` and experiment 16's `feel.walk`. A word can have several
disconnected bodies, so these run per connected component, in right-to-left
component order. Tiny components become taps; failed components are explicit.
This is an adapter for the old traversal, not a reproduction of the old trained
feeler or a new stroke-order recovery algorithm. No transcription enters it.

`retrieval.py`: one nearest training example per input under fixed Euclidean
features. The image arm uses a normalised low-resolution ink vector; trace
arms use arc-length-resampled x/y, deltas and pen boundaries. All use the same
2,000 training words and 500 test words, selected by stable sample-ID order.
No warping, learned features or language model. Distances are not confidence.

| Input | Exact word | Character error | Exact, text seen in training (330) |
|---|---|---|---|
| Rendered image | 21.6% | 81.3% | 32.7% |
| Reference retracing | 31.8% | 61.8% | 48.2% |
| Recovered path | 24.0% | 72.1% | 36.4% |

170 test words have text absent from the selected training set; every retrieval
arm is necessarily 0% exact on them. This is closed-vocabulary retrieval, not
general transcription. It suggests useful information in the reference
representation for this control, not an advantage over mature image readers.

`train.py`: three small CTC readers trained from scratch, same 2-layer
bidirectional LSTM head (64 units per direction), 154,501 parameters for each
trace model, 160,165 for the image model with a small CNN encoder. Each sees
the same 2,000 train / 300 validation / 500 test words. Train-only vocabulary;
unseen characters remain errors. Greedy CTC decoding, no lexicon or language
prior. Select best checkpoint by validation CER. Save each epoch, refuse
configuration changes within a named run, and reuse completed outputs.

The 12-epoch pilot did not learn useful transcription: image 100.0% CER,
reference 93.8%, recovered 88.7%, exact 0 / 0 / 0.4%. It took 1m42s, peak
612 MiB RSS, CPU only. Do not rank the representations from these undertrained
models. Its files stay in `out/runs/pilot/`.

A longer exploratory run continues those checkpoints to 72 total epochs:

```sh
experiments/16_feel/out/torchenv/bin/python experiments/42_stroke_recovery/train.py \
  --name extended --epochs 72 --initial-run pilot
```

The extension was chosen after weak validation, but the original test scores
had already been inspected. Later results on that test set are exploratory,
not an untouched confirmation. A cross-input control also applies the reference
reader directly to recovered paths; its loss includes distribution shift.

**Extended run completed 2026-10-18**, 72 total epochs per reader, 10m53s
additional wall time on three CPU threads, peak 608 MiB RSS:

| Input | Exact word (500) | Character error | Exact, unseen text (170) |
|---|---|---|---|
| Rendered image | 1.8% | 78.7% | 0.0% |
| Reference retracing | 39.2% | 25.5% | 15.9% (27 words) |
| Recovered path | 12.2% | 61.8% | 0.0% |

The reference reader on recovered inputs without retraining: 2.0% exact,
82.6% CER. The reference representation is more usable by this small reader
than the inferred traversal in this setup, despite high geometric coverage.
Prescribed annotation order is a major confound. The image reader is a weak
baseline, and training curves still improve. Neither the 39.2% nor the
reference/recovery gap establishes natural calligraphy or image-OCR superiority.
Results/checkpoints: `out/runs/extended/`; `out/results.json` is the active run.

## Viewer and recording

`serve.py` and `app/`: searchable samples with split/coverage filters, rendered
ink beside reference and recovered paths, synchronised distance-based replay,
source records, a retrieval/sequence reader selector and result tables. Scheherazade New and
Lucide are cached locally with their licences. There is no fabricated physical
timing for Calliar. Playback progress is path distance.

The Record view captures freely drawn pointer input, saving x/y, event
timestamps, pressure and tilt, pointer device, writer ID, style and optional
checked transcription. Mouse and touch are not labelled pen. Raw channels
are retained before geometric normalisation and saved before optional model
inference; prediction errors cannot discard the observation. Samples remain unassigned to
training splits. Their optional model outputs come from retracing-trained
models and are not certified readings of natural writing. A missing PyTorch
installation only disables sequence-model inference; the viewer still runs.

Recording requires no letter segmentation. A finger, mouse and stylus can
record paths, but only channels actually supplied by the browser/device are
available. No claim is made to recover a historical writer's motion.

## Files and checks

`fetch.py`, `dataset.py`, `geometry.py`, `retrieval.py`, `train.py`, `assets.py`,
`serve.py`, `app/`, `browser_check.py`, `research.md`.

```sh
.venv/bin/pytest -q tests/test_stroke_recovery.py tests/test_docs.py
experiments/40_gemini4_vlm/out/venv/bin/python experiments/42_stroke_recovery/browser_check.py
```

Focused tests cover annotation alignment, taps/pen lifts, aspect preservation,
recovery, timestamp/channel validation, recording round trips, cross-origin
writes, path traversal and source grouping. Browser checks exercise desktop
and mobile views, actual changing canvas pixels, sample navigation, empty
states, recording, undo and a rejected save that preserves ink. Browser test
recordings are intercepted and never enter the research data. Screenshots
and the check report live in `out/checks/`.

Verified 2026-10-18: full repository suite **118 passed** (5m45s); latest
focused suite plus documentation checks **19 passed**; **16/16** Playwright
checks passed with no browser errors. No test recordings were persisted to
the experiment's research data.

**What it changes.** A local instrument for separating geometry preservation
from recognition and collecting real motion data. The stroke idea remains
open. No application pipeline, existing experiment, master format or D19 rule
was changed. Spend: zero paid model calls and zero GPU rental.
