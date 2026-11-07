# Experiment 88: the owner's truth with «» restored (rev2), and a locked old-print document set

**Question.**
1. The owner's 20 corrected pages (the "yardstick") write printed «» as (( )), a habit carried over from Azure's draft.
   What do Azure, v3 and v5 score on «» once the truth writes the marks as printed?
2. No pre-1980 journal is left that could be locked (experiment 84). Can a locked test of old print be made from
   **documents** instead? The owner chose option (a) on 2026-11-05: lock old documents that were never downloaded or
   used, from journals that may appear in training.

**Caps:** CPU only, niced, at most 2 cores. No GPU, no Gemini. Both tasks were approved by the owner on 2026-11-05.

## 1. rev2 of the 20-page truth («» only)

**Where the truth lives.** The original is experiment 34's `out/gold/<page>.json` (status done). `test77.py` copies it
into experiment 77's `out/test/pages.json`. Every scorer reads it from there: eval77, eval78, eval83 and quotes84.

**Method.** `rev2_88.py` writes a NEW file next to pages.json and never touches the original:
`experiments/77_scratch_reader/out/test/yardstick_truth_rev2_quotes.jsonl`. It has one row per yardstick page, and the
truth lines keep the same order and count, so `gold_pos` still holds. A note sits beside it:
`yardstick_truth_rev2_quotes.README.txt`, which reads "rev2 (lead, 2026-11-05, owner OK): printed «» restored on 18 lines;
original untouched".
- Every truth line with (( or )) was cut from experiment 77's test tar (`out/crops/<key>.jpg`), and **I looked at
  each crop**. All 18 lines print « and », and none prints parentheses.
- On those lines (( became « and )) became ». Two lines carried a half-converted mark:
  - p008 l014 had `( اليد فى العجينة))` → `« اليد فى العجينة»`;
  - p017 l002 had `(( يوميات …)»` → `« يوميات …»`.
  Spacing was left as the owner wrote it. Real parentheses, such as (٢) or (١٠), were not touched.
- Each change is recorded in `out/rev2_changes.json`: page, line key, position, old text, new text and the crop.
- In all, 18 lines on 6 pages changed (pages 0005-055-003-004 p8, 0260-000-008-013 p5, 0355-000-002-006 p17,
  0382-016-063-013 p3, 0408-002-010-007 p3, 0498-000-388-003 p6). That makes 29 marks: 28 halves of (( )), plus the
  lone `(`.

**Re-score.** `score88.py` scores the existing reads of the test tar; nothing was re-read. Azure is the line text in
pages.json. v3 is `83_reader_scale/out/pred/test_v3.jsonl` (`out/weights/v3/best.pt`), which is identical to
experiment 84's host re-read. v5 is `84_display_fonts/out/pred/test_v5.jsonl` (`out/weights/v5/last.pt`). Marks are
counted per line as in quotes84 (matched = min(reader, truth)). Punctuation is included.

| reader | truth | «» precision | «» recall | (( )) written | letters wrong, punct. incl. | letters wrong, no punct. |
|---|---|---|---|---|---|---|
| Azure | rev1 | 7/7 | 7/30 | 51 | 0.84% | 0.60% |
| v3 | rev1 | – (writes none) | 0/30 | 59 | 1.08% | 0.69% |
| v5 | rev1 | 28/57 | 28/30 | 3 | 1.10% | 0.71% |
| **Azure** | **rev2** | **7/7 (100%)** | **7/59 (12%)** | 51 | 1.01% | 0.60% |
| **v3** | **rev2** | **– (writes none)** | **0/59 (0%)** | 59 | 1.23% | 0.69% |
| **v5** | **rev2** | **56/57 (98.2%)** | **56/59 (94.9%)** | 3 | **1.03%** | 0.71% |

- On rev2 the truth holds no (( )) at all: every (( )) a reader writes is wrong.
- With punctuation counted, v5 moves from behind v3 (1.10 against 1.08) to clearly ahead (1.03 against 1.23), and
  becomes level with Azure (1.01).
- The headline (punctuation removed) cannot move, because rev2 changes only punctuation.
- This confirms experiment 84's estimate (55/58) with a truth that now writes the marks.

**How to select rev2.** The headline scorers keep their default, rev1; eval83 and eval78 were not edited. To use rev2:
- run `score88.py --truth rev2` (or `--truth both`), or
- `from score88 import yardstick_pages; pages = yardstick_pages("rev2")` returns pages.json with the 20 truths
  swapped. A scorer that loads pages.json can take this one line instead.

## 2. The LOCKED old-print documents

**Method.** `select88.py`, in two steps: `scan`, then `select`. It uses no network, reads the catalogue read-only and
opens no page. `verify88.sh` then checks the choice.
- **Eligible (as in experiment 84).** A document qualifies when it meets all of these:
  - catalogue language `ara`;
  - one of the article-like types;
  - published 1900–1979;
  - 2–40 printed pages;
  - both PDF and Azure JSON in the main bucket (experiment 44's listing).

  79,051 documents qualify.
- **Whole journals out, kept separate.** split76's 27 held-out codes (experiment 81's test, lab documents 1–3) and
  experiment 84's 20 locked journals are excluded.
- **Documents out.** 3,346 eligible documents are excluded because they appear in at least one of these:
  - experiment 76's inventory;
  - experiment 77's train, dev, old80 and test manifests, and select77;
  - experiment 80's plan, manifest, ids and on-disk list;
  - experiment 83's plan83 and on-disk list;
  - experiment 84's on-disk and mentioned lists;
  - experiment 85's judge sample;
  - a fresh scan of every file name under /home/appuser (AI-Search not walked; 10,636 stems).
- **Named in a repo file.** A full regex scan of repo contents was started, then stopped after 1h40 for time. Instead,
  `verify88.sh` searches every chosen stem as a fixed string in every repo file: text and binary (sqlite, tar, gz),
  with images, PDFs and model weights aside, since their names were already scanned. A stem found outside a
  catalogue enumeration would be dropped.
  - **Result:** all hits are enumerations: 16 all_ids, 19 listing, 28 catalogue.tsv, 43's random catalogue draw (4
    stems, never fetched), 44's listing, and 80/83's candidate pools. The rest are copies of this lock (88, 89's
    guard file, 90's test). No locked stem is named in any training, selection or data file
    (`out/grep88.txt`).
- **Choice (seed 88).**
  - Decade quotas: 1920s 40, 1930s 50, 1940s 50, 1950s 50, 1960s 45, 1970s 45. A decade's unfilled quota moves on to
    the next decade.
  - Within a decade, journals are taken round-robin in random order.
  - At most one document per issue.
  - At most 15 documents per journal before 1950 (only about 16 old journals are left), and 3 per journal from 1950.
  - Issues with no used document are preferred.
  - Re-running `select` reproduces the same 280 stems (checked).

**Result: `LOCKED_OLD_DOCS.json`**, written 2026-11-05 at 18:49. **280 documents from 114 journals, 1924–1979, 140 of
them before 1950.**

| decade | 1920s | 1930s | 1940s | 1950s | 1960s | 1970s |
|---|---|---|---|---|---|---|
| documents | 15 | 75 | 50 | 50 | 45 | 45 |
| journals | 1 | 7 | 12 | 30 | 45 | 45 |

- The pre-1950 documents come from 16 journals:
  - 0690 مجلة المجمع العلمي العربي, 0718 صحيفة دار العلوم, 0873 مجلة القانون والاقتصاد and 0924 المحاماة, 15 each;
  - 0737 الرواية, 14;
  - 0728 الثقافة, 10;
  - 1056 مجلتي, 9;
  - 0667 مجلة الأوقاف الاسلامية, 8;
  - 0738 الكتاب and 0749 مجلة كلية الآداب, 7 each;
  - 0300 الأبحاث, 6;
  - 0692 مجلة مجمع اللغة العربية, 5;
  - 0620, 0806 and 0316, 3–4 each.
- From 1950 on, each journal has 1–3 documents.
- Countries: Egypt 158, Syria 44, Iraq 13, Lebanon 12, Morocco 10, Saudi Arabia 9, and others.
- The file's note: *"locked: no download, no training, no tuning; opened once for the final claim with the owner's
  OK"*. No document was downloaded or opened.
- The pool held 63,400 documents (45,737 of them in issues nobody has touched). The old decades are the scarce ones:
  the 1920s have 137 documents, all from one journal; the 1930s 1,067 and the 1940s 1,024.

**The guard: `locked_old.py`** (experiment 84's `locked.py` is imported, not edited).
- `locked_docs()`: the 280 stems.
- `is_locked_doc(stem)`: true for a stem, line key or path of a locked document.
- `is_locked_any(s)`: true for a locked journal (84) or a locked document (88).
- `assert_not_locked(stems)`: raises on either kind; 84's journal guard runs first.
- `python3 locked_old.py FILE…` checks lists of stems or keys. For example, plan83's 7,763 documents pass.

**Every future selector, downloader, trainer, text source, tuner and test builder must call
`locked_old.assert_not_locked` (or filter with `is_locked_any`), not 84's guard alone, which knows only the journals.**
A locked document's journal is NOT locked: other documents of that journal may be used.

## What it changed

- The owner's 20 pages can now score «» faithfully (rev2). v5 writes printed guillemets at 98% precision and 95%
  recall. On rev2 it is level with Azure and ahead of v3 on letters with punctuation.
- A locked old-print test now exists at document level, with 140 pre-1950 documents. It complements 84's locked
  journals, which have no pre-1980 print.
- Experiments 89 (trainer) and 90 (the locked final test) already read `LOCKED_OLD_DOCS.json` through the guard.

## Files

- `rev2_88.py`: builds rev2 and the per-change record. `score88.py`: re-scores rev1 and rev2, and holds
  `yardstick_pages(rev)`.
- `select88.py`: eligibility, the file-name scan and the choice. `verify88.sh`: the fixed-string check of repo
  contents. `LOCKED_OLD_DOCS.json` (in git): the lock. `locked_old.py`: the guard.
- `out/` (gitignored, private): crops of the 18 lines, `rev2_changes.json`, `score88.json`, `data/` (eligible
  documents, on-disk stems, grep hits, exclusions), `grep88.txt`.
