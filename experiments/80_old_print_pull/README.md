# Experiment 80: an old-print pull for the from-scratch readers

**Question (2026-11-04).** The readers of experiments 77 (image reader), 78 (synthetic lines) and 79 (signal reader)
struggle most on old print: metal type, heavy or spread ink, filled counters, old spellings. Only about 3,600 of
the 40,612 pages on disk are from before 2000 (experiment 76's inventory). Can we pull a few hundred more pre-2000
documents, spread across journals and decades, without disturbing production? The owner allowed S3 pulls on
2026-11-04. Nothing here cuts lines or trains anything. The reader experiments use the pull.

## Method

- **Choice** (`select80.py`, no network). Candidates come from the catalogue (`marc.db`, read only): `year_int <
  2000`, language `ara`, type one of articles, literary texts, conference papers, book or thesis reviews, or
  editorials (no theses), 2–40 printed pages. Each candidate must be in the main bucket (experiment 44's
  `ids_main.txt`) with both `<id>.pdf` and `<id>.json` in experiment 44's listing. Two groups are excluded: the 27
  held-out journals of experiment 76 (`split76.json` "test"), and every document already on this machine (all
  5,723 `<id>.pdf|json` names found under /home/appuser, plus experiment 76's inventory). That leaves 218,517
  candidates. Each decade gets a quota, weighted towards the years before 1970 (1920s 70, 1930s 80, 1940s 85,
  1950s 85, 1960s 80, 1970s 65, 1980s 60, 1990s 55). Inside a decade, journals are taken round-robin in random
  order (seed 80), one document per journal per round, so every journal appears before any journal appears twice.
  The fetch order alternates decades, so a stop at any point would still leave a balanced set.
- **Pull.** `inkscript fetch --workers 4` ran under `nice -n 19 ionice -c3 taskset -c 0,1`, with
  `AWS_CONFIG_FILE=aws_capped.config` (regions only, no credentials: `max_concurrent_requests=4` and
  `max_bandwidth=6MB/s` per process, so at most about 25 MB/s in all). The bucket was read only. Run on
  2026-11-04, 17:03–17:24 CST (02:03–02:24 Riyadh), with the load average at 1.3–3.9. Of the 580 documents, 580
  arrived complete.
- **Manifest** (`manifest80.py`, no network, appends as it goes). For each document it records id, journal, year,
  pages (Azure and PDF), bytes, lines and lines with polygons, the Arabic share of Azure's letters, and the PDF's
  text layer. It writes `data/manifest80.jsonl` and `data/summary80.json`.

All data is in `data/` (gitignored, private): `fetch/<id>/<id>.{pdf,json}` (the `--azure-dir` layout),
`candidates80.jsonl`, `plan80.jsonl`, `ids80.txt`, `fetch80.log`, `manifest80.jsonl`, `summary80.json` (the full
by-journal table) and `ondisk80.txt`.

```
nice -n 19 .venv/bin/python experiments/80_old_print_pull/select80.py --ondisk experiments/80_old_print_pull/data/ondisk80.txt
AWS_CONFIG_FILE=$PWD/experiments/80_old_print_pull/aws_capped.config nice -n 19 ionice -c3 taskset -c 0,1 \
  .venv/bin/inkscript fetch --id-file experiments/80_old_print_pull/data/ids80.txt --out experiments/80_old_print_pull/data/fetch --workers 4
nice -n 19 .venv/bin/python experiments/80_old_print_pull/manifest80.py
```

## Result (2026-11-04)

**580 documents, 7,684 pages, 245,285 Azure lines, 261 journals, 1.45 GB** (PDFs 0.46 GB, JSON 0.99 GB), from
1924 to 1999. This roughly triples the pre-2000 pages on disk (about 3,600 → about 11,300).

| decade | documents | journals | pages | Azure lines | GB |
|---|---|---|---|---|---|
| 1920s | 70 | 3 | 621 | 25,942 | 0.12 |
| 1930s | 80 | 12 | 1,004 | 30,162 | 0.17 |
| 1940s | 85 | 20 | 957 | 27,711 | 0.18 |
| 1950s | 85 | 51 | 1,209 | 35,800 | 0.25 |
| 1960s | 80 | 80 | 1,045 | 33,138 | 0.20 |
| 1970s | 65 | 65 | 868 | 29,399 | 0.15 |
| 1980s | 60 | 60 | 1,054 | 34,052 | 0.19 |
| 1990s | 55 | 55 | 926 | 29,081 | 0.19 |

The 1920s–1940s are as wide as the catalogue allows. Outside the held-out journals and what is already on disk, it
has only 3, 12 and 20 journals in those decades. 184 journals give one document, 31 give two, 16 give three, and
30 give four or more. The largest journals (the full table is in `summary80.json`):

| code | journal | years | documents | pages |
|---|---|---|---|---|
| 0924 | المحاماة | 1924–1970 | 46 | 500 |
| 0690 | مجلة المجمع العلمي العربي | 1924–1956 | 42 | 311 |
| 0739 | مجلة الآداب | 1938–1988 | 11 | 306 |
| 0749 | مجلة كلية الآداب | 1933–1951 | 14 | 303 |
| 0873 | مجلة القانون والاقتصاد | 1932–1967 | 14 | 268 |
| 0692 | مجلة مجمع اللغة العربية بالقاهرة | 1934–1964 | 13 | 165 |
| 0763 | مجلة كلية الآداب | 1936 | 5 | 120 |
| 0300 | الأبحاث | 1948–1962 | 8 | 106 |
| 0310 | مجلة كلية الآداب | 1949–1968 | 7 | 102 |
| 0917 | مجلة القضاء الشرعي | 1926–1927 | 8 | 100 |

**Azure.** All 580 have Azure JSON (prebuilt-read, API 2024-11-30), and in every one of them every line has an
8-point polygon. Azure and PDF page counts agree for all 580.

**Odd cases.**
- No JSON is missing and no file is broken. Every PDF holds a page-scan image (median about 350 dpi, tenth to
  ninetieth percentile 260–460) under Azure's text layer, so none is image-only.
- 47 pages in 32 documents have no Azure lines (blank or picture pages).
- 8 documents are mostly Latin script although the catalogue says `ara`: Arabic share of letters below 0.5, for
  example French or English papers in Arabic journals (0673 ×2, 0951, 0373, 0749, 0700, 0416, 6279). Another 26
  are 50–90% Arabic (Latin terms, quotations, references). A reader should filter by `arabic_share` in the
  manifest.
- The catalogue's printed page count differs from the scan's page count for 62 documents. The manifest keeps both.
- Two sample pages looked at by eye, 0917-004-001-004 (1926) and 0873-022-001-002 (1952), are genuine metal-type
  print with two columns, footnotes and mixed French.

**What it changes.** Experiments 77–79 have about 7.7k more old-print pages to cut lines from and test on. None of
them come from experiment 76's held-out journals.
