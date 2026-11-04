# Experiment 58 progress notes

- 2026-10-30: cloned github.com/datalab-to/indra (HEAD e203553, package 1.1.2, tags v1.1.0 3d4eb01 / v1.1.2 0e96b93) to
  out/indra_src; venv out/venv (Python 3.12.3, onnxruntime 1.31.1, opencv 5.0, pypdfium2 5.14 — the repo's own pin is
  not touched); models from huggingface.co/datalab-to/indra-ocr (rev bd02167f) to out/models (98 MB incl. math).
- Licence read: code Apache-2.0; weights "AI Pubs OpenRAIL-M (modified)": commercial use barred for >$20M revenue or
  >$20M funding, or if the user offers a product competing with Datalab's; share-alike on Output (s.8); attribution
  with any Output (s.7).
- Memory guard: guard.sh (kills this experiment's python if MemAvailable < 8 GB).
- Truth: 20 owner gold pages (34_yardstick/out/gold, status done) + born-digital truth (36_vlm_bakeoff/out/ref/bdtruth);
  scored like exp 41 (score41.py words()).
- lay300: 3,404 pages, 8 workers nice 19, 508 s (6.7 p/s), 1.17 core-s/page (user+sys), max RSS/worker 820 MB, 0 errors. Text variants (dpi 200/300/400, scale, otsu/clahe/sharpen, Azure crops) all within ±0.5 pt; best ~10.1% words wrong vs Azure 1.80%.
- Text (34 truth pages, exp 41's measure): Azure 1.80% (gold 1.36, bd 2.36) reproduced; Indra img300 10.37% (gold 15.57,
  bd 3.78); best variant pdf400 10.08%. Ordered folded CER on bd: Indra 2.28% vs Azure 3.21% (order better).
- Layout (3,404 pages vs Gemini v33_300b_fix3): coarse role agreement 85.2%; body recall 95.7%; headings 53.6%;
  footnote P 98% R 41%; furniture P 98% R 77%; table lines R 97.7%; order pair concordance 97.8%, exact 67.6% of pages
  (two-column 41.9%); tables TEDS-struct 0.61, same grid 77/387. My footnote/furniture rules made it worse (dropped).
- Triage: Indra-plain pages after p1 = 46.9%; Gemini also plain on 56%; all lines agree on 40%.
- Cost: Gemini v3.3 per page 3,363 in (prompt 801, image 1,295, Azure lines 1,268) + 892 out; input 43% / output 57% of $.
- By script: Latin pages Indra vs Azure words 1.8%, roles 88%; Arabic 10.9%, 84.5%. 2020s 3.0%, pre-1960 19.4%.
- side page out/side/index.html (looked at: 0422 ok, 0692 two-col glossary read as one table row by row = wrong order; 1136 English footnotes right).
- Surya 2.5 (llama.cpp b12017 CPU, 8 threads): 6 truth pages, 38.9 min; words wrong Azure 3.35 / Indra 11.2 / Surya 8.74%.
  Chandra 2 (5.3B) skipped on CPU.
- legacy/ 137 first pages, Indra auto: 116 text layer, 14 hybrid, 7 OCR (broken font map); 9.8 p/s.
- README, experiments/README line, side page (index.html + order_check.html) done.
- plain58.py: R1 47% pages saves 42% but loses 54% of fixes, 34% of calls; R2b 7.4% pages, 6.6% saved (~$9.9k/1M docs), roles differ 3.6%.
