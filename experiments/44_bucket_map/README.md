# Experiment 44: the bucket map

**Question** (owner, 2026-10-19): "Give me a picture of the structure of my bucket and tell me how many documents I
have", including `legacy/` and the Qdrant backups.

**Method** (2026-10-19, read-only, $0.015). The AWS profile (`s3-uploader`, the venv's `aws`) sees three buckets.
No S3 Inventory or metrics configuration exists and CloudWatch is not allowed for this user, so every key was listed:
`list44.py` paginates ListObjectsV2 by key prefix (100 two-digit shards of the main folders, plus `legacy/`,
`legacy-test/`, `metadata/`, `qdrant/`, `mysql/`, the CloudTrail logs), 8 threads, each page appended to
`out/listing/*.tsv` with a resume token. **3,061 list requests, ~17 minutes.** Nothing was downloaded except the
three Qdrant snapshot manifests (1–2 KB, `out/qdrant_manifests/`) and two small samples to name file types
(`out/samples/`: a 22 KB `.html`, a 187-byte `.gemini.title.json`). `analyze44.py` counts (→ `out/summary44.json`,
`out/ids_main.txt`, `out/ids_legacy.txt`), compares with experiment 19's listing and with the catalogue index
(`~/.cache/inkscript/catalogue/catalogue.sqlite`), and checks experiment 43's missing draws. `render44.py` draws
`out/bucket_map.html`.

```
.venv/bin/python experiments/44_bucket_map/list44.py        # network, resumable
.venv/bin/python experiments/44_bucket_map/analyze44.py
.venv/bin/python experiments/44_bucket_map/render44.py
```

## Result

**Buckets** (5.57 TB in all):

| Bucket | Region | What | Objects | Size |
|---|---|---|---|---|
| `mandumah-source-docs` | eu-north-1 | the documents, the catalogue | 2,969,250 | 5.13 TB |
| `mandumah-qdrant-backups` | eu-west-1 | 3 Qdrant snapshots, 22 MySQL dumps | 28 | 443 GB |
| `aws-cloudtrail-logs-006127064053-14137c60` | eu-north-1 | CloudTrail access logs, 29 Sep → 19 Oct | 9,979 | 27 MB |

**`mandumah-source-docs`**

| Pattern | Files | Size | What |
|---|---|---|---|
| `<id>/<id>.pdf` | 1,013,912 | 1.53 TB | Azure's searchable PDF |
| `<id>/<id>.json` | 1,013,912 | 2.89 TB | Azure layout JSON |
| `<id>/<id>.html` | 457,628 | 510 GB | an HTML reading view (pages, toolbar) |
| `<id>/<id>.gemini.title.json` | 174,138 | tiny | Gemini's title + authors (Sep 2026) |
| `legacy/<id>/<id>.pdf` | 308,593 | 195 GB | PDF only, uploaded 2–4 Sep 2026 |
| `legacy-test/<id>/…` | 1,065 | 0.64 GB | 969 PDFs (947 also in legacy/), 48 LibreOffice lock files, 48 empty .tmp; 31 Aug |
| `metadata/metadata_final.xml.gz` | 1 | 1.17 GB | the MARC catalogue (same file our catalogue index was built from) |
| `metrics.txt` | 1 | 607 B | report of an old batch run (batch03, 10,953 documents, 18 Jun) |

Main folders were uploaded 2026-06-15 → 2026-09-25 (Intelligent-Tiering mostly). Id `JJJJ-VVV-III-AAA`; 49,533
(4.9%) carry a comma for a joint issue or volume (`0339-000-018,019-008`). Legacy uses the same scheme.

**Documents**

- **Main: 1,013,912**, every one with PDF **and** Azure JSON (0 PDF-only, 0 JSON-only); 457,628 also have the HTML.
- **legacy/: 308,593**, all PDF only (no Azure JSON); only **23** are also in the main set.
- **Union: 1,322,482** distinct documents (+70 ids found only in legacy-test).
- Experiment 19's listing (2026-10-06): 1,013,912 main folders, **the same set id for id** (0 gone, 0 new).

**Catalogue vs bucket.** The catalogue (1,558,415 records) names 3,196,204 PDF ids. **1,807,389 are dissertation
chapter PDFs** (169,644 theses, journal codes 98xx, ids like `9802-001-001-0001-1`): **none is in the bucket**
(10 98xx ids exist in it). Of the 1,388,815 article ids: **1,000,232 (72%) in the main folders, 301,187 (22%) only
in legacy/, 87,396 (6%) nowhere** (spread over 2,104 journals). The other way: 13,680 main documents and 7,383 legacy
PDFs have no catalogue entry.

**Experiment 43's missing draws**: of 214 catalogue articles drawn, 43 had no main folder; **32 are in `legacy/`**
under the same key pattern (PDF only, so no Azure JSON); **11 are nowhere** (0722-058-022-001, 1772-009-002-022,
1818-000-083-015, 1893-016-002-003, 1941-016-002-015, 2068-000-009-008, 2246-002-010-016, 2258-008-002-004,
2646-000-056-005, and two dissertations 9815-058-006-0144-4, 9818-006-001-4963-R).

**Qdrant backups** (`qdrant/<collection>/<collection>-<n>-<date>.snapshot` + `.manifest.json`, Qdrant 1.7.4, one
snapshot per collection, Glacier Instant Retrieval):

| Collection | Taken | Size | Points | Vectors | Indexed fields |
|---|---|---|---|---|---|
| `mandumah_ocr_v1` | 2026-09-30 | 121 GB | 9,732,620 | dense 1536-d + sparse | title, journal_id, year, doc_id, source, section, journal, authors |
| `documents_async_01_10_2025` | 2026-10-01 | 108 GB | 12,486,022 | one 1536-d | none |
| `mandumah_v2` | 2026-10-02 | 208 GB | 15,672,871 | dense 1536-d + sparse | journal_id, title, doc_id, section, database, category, journal, country, authors, year |

`mysql/ai_search_feedback-<timestamp>.sql.gz`: 22 nightly dumps, 2026-09-28 → 2026-10-19, 260 → 311 MB (6.3 GB).

## What it changed

- A future catalogue draw should be filtered by `out/ids_main.txt` (or, for PDF-only work, `out/ids_legacy.txt`).
- The 308,593 legacy PDFs are the documents that still need Azure (or another reader) before they join the corpus.
- Picture for the owner: `out/bucket_map.html`.
