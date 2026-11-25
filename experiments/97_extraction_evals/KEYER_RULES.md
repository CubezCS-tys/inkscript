# Rules for writing answer keys (experiment 97)

You are writing the answer key of an exam. The pipeline under test is NOT your source: your only sources are the page
images and Azure's raw lines in the packets.

## Hard rules

1. Read only: `LOCKED_EVAL.json`, `out/packets/<stem>/packet.json`, the page images the packets point to, this file,
   and your own output folder. Do NOT open the release database, anything under `/home/appuser/data/`, the Desk, the
   Classic pages (`experiments/41_azure_structure`), other experiments' outputs, or another keyer's folder
   (`out/keys/*/A` if you are B, and the reverse). The key is worthless if it is copied from the thing it tests.
2. Look at the page image for every decision (Read tool on the JPEG; crop with PIL into your own `tmp/` folder when
   the print is small). Azure's line text helps you find lines; it is not the truth and may be misread.
3. Record what is PRINTED. Do not correct the author's spelling, do not normalise letters, digits or punctuation.
4. If you cannot decide, do not guess: write the item with `"unsure": true` and a short `"why"`.
5. Save after EVERY page or article (one JSON file each), so a stop loses nothing. Skip files that already exist when
   resumed. Keep a `progress.log` in your folder (one line per finished item).
6. Shared machine with a live database: prefix every Python or shell job with `nice -n 19`. No parallel jobs, no
   loops that poll, never `pkill -f`. No network calls, no paid APIs, no model downloads.
7. Never write outside `experiments/97_extraction_evals/out/keys/<part>/<your letter>/`. Never delete anything.
8. Final answer: counts done / unsure / skipped, and anything about the rules that was ambiguous. Keep it short.

A packet page looks like: `{page, image, width_px, height_px, azure_lines: [{line, text, x, y, w, h}]}`; boxes are
pixels of the image, origin top-left. `exam_pages` in the packet says which pages are this article's exam pages:
`front`, `body`, and where present `table`, `refs`, `notes`.

## Part PAGE (parts P1, P2, P3, P6, R2): one file per exam page

For every exam page of every article (all kinds: front, body, table, refs, notes), write
`<stem>_p<page:03d>.json`:

```
{"stem": "...", "page": 7, "columns": 1 | 2 | "mixed",
 "pieces": [                       # in READING ORDER (for Arabic: right column before left column)
   {"role": "...", "lines": [12, 13, 14], "continues_from_previous_page": false, "continues_on_next_page": false,
    "note_label": "1"            # footnote / endnote pieces only: the printed label
   }, ...],
 "note_calls": [{"label": "1", "in_line": 9}],        # call marks printed in the running text
 "text_not_in_any_azure_line": ["..."],               # printed text Azure has no line for (short description + where)
 "azure_lines_that_are_not_text": [3, 40],            # specks, stamps, ruling lines read as text
 "unsure": false}
```

Roles (pick exactly one): `title`, `title-translated`, `byline` (author names), `affiliation`, `abstract`,
`keywords`, `front-matter` (dates received/accepted, journal information, copyright, DOI lines), `heading`,
`paragraph`, `list-item`, `quote`, `verse`, `footnote`, `endnote`, `ref` (one entry of a reference list), `caption`,
`table` (ALL lines inside one table form ONE piece), `figure` (text inside a picture or chart), `equation`,
`running-head` (repeated header/footer line, journal name, issue line), `page-number`, `other`.

A piece is one unit a reader would call one thing: one paragraph, one heading, one list item, one footnote, one
reference entry, one whole table. Every Azure line of the page appears in exactly one piece or in
`azure_lines_that_are_not_text`. If one Azure line holds text of two pieces (a merged line across columns), put it in
the piece holding most of it and add `"split_line": true` to both pieces concerned.

## Part FRONT (part P4): one file per article, `<stem>.json`

Look at the first pages (and the last pages, where an English abstract often sits). Write what is printed:

```
{"stem": "...",
 "titles": [{"lang": "ar", "text": "..."}, {"lang": "en", "text": "..."}],     # subtitle joined with " : " as printed
 "authors": [{"printed": "...", "script": "Arab" | "Latn", "affiliation_printed": "...", "page": 1}],   # in printed order; an author printed in two scripts appears twice
 "abstracts": [{"lang": "ar", "page": 1, "first_words": "...", "last_words": "...", "n_azure_lines": 14}],  # 8 words each end
 "keywords": [{"lang": "ar", "list": ["...", "..."]}],
 "dates": {"received": "...", "accepted": "...", "published": "..."},          # as printed, null if absent
 "doi": null, "first_printed_page_number": "9", "last_printed_page_number": "28",
 "article_language": "ar", "unsure": false}
```

Type the titles, author names and keywords carefully from the image, letter by letter; these are compared exactly.

## Part SECT (part P5): one file per article in the 20-article subset, `<stem>.json`

The subset is the first 20 articles of `LOCKED_EVAL.json` with `n_pages` ≤ 30, in file order. Go through ALL pages.

```
{"stem": "...", "headings": [{"page": 3, "lines": [5], "text": "...", "level": 1, "numbered_as": "2-1" | null}], "unsure": false}
```

A heading is a line the printer set apart as a heading (own line, bold / larger / centred or a numbered title of a
part). An item of a numbered list that runs on as a sentence is NOT a heading. Level 1 = the article's main parts;
deeper levels as the print shows (size, weight, numbering). The article title, "abstract" and "keywords" labels are
not headings here; "References"/«المراجع» is a level-1 heading.

## Part REFS (part P9): one file per article that has a `refs` exam page, `<stem>_p<page:03d>.json`

```
{"stem": "...", "page": 17,
 "references": [{"lines": [4, 5], "starts_on_previous_page": false, "continues_on_next_page": false,
   "type": "journal" | "book" | "chapter" | "thesis" | "conference" | "web" | "report" | "other",
   "authors": ["as printed, one string per author"], "year": "2003", "title": "...",
   "source": "journal / book / university name as printed", "volume": "3", "issue": null, "pages": "31-73",
   "lang": "ar"}],
 "unsure": false}
```

Fields are copied as printed (no reordering of names, no translation, digits as printed). A field that is not
printed is null. For a reference cut by the page edge, fill only what is on this page.

## Part TAB (part P7 + P8): one file per article that has a `table` exam page, `<stem>_p<page:03d>.json`

```
{"stem": "...", "page": 11,
 "tables": [{"lines_first_last": [20, 96], "caption": "...", "caption_position": "above" | "below" | null,
   "number_printed": "1", "n_rows": 9, "n_cols": 6, "n_header_rows": 2,
   "is_continuation_of_previous_page": false, "continues_on_next_page": false,
   "cells": [["r0c0", "r0c1", ...], ...]}],     # FULL grid only for the FIRST table of the page; null for the others. Merged cells: text in the first position, "" in the rest.
 "figures": [{"kind": "figure" | "chart" | "equation" | "picture", "caption": "...", "number_printed": "2"}],
 "unsure": false}
```

Cells are typed exactly as printed: digits in the printed digit set, stars, minus signs, brackets. Rows are counted
top to bottom, columns right to left for an Arabic table (c0 is the rightmost column) and left to right for an
English one; say which with `"direction": "rtl" | "ltr"` on the table.

## Conventions fixed on 2026-11-10 after both TAB keyers finished (they apply to the final key and the scorer)

Both keyers chose these independently; they are now the rule.
- **Numeric cells are typed in the visual left-to-right order on the page** (`3.793-`, `**٠٫٥٦ -`, `%26`). Arabic
  text cells are typed in reading order. The scorer compares numeric cells after removing spaces and putting a
  trailing minus in front, and reports that "logical" match beside the exact one.
- **Decimal mark:** with Arabic-Indic digits a comma-shaped mark is U+066B (٫) and a dot is "."; with Western digits
  it is typed as seen. The scorer treats ٫ , ، and . between digits as the same mark in a second, "folded" score.
- **Kashida (ـ) is dropped.** Printed spaces inside a cell are kept; multi-line cells are joined with one space.
- **`n_rows` counts header rows.** A full-width note or source line inside the frame is `table_note`, not a row.
- **Merged cells:** text in the first position (top; rightmost column in an RTL table), "" in the rest.
- **A borderless list set in columns is not a table.** It is recorded under `"tabular_lists"` (lines and a one-line
  description) and scored separately.
- **A caption printed on the previous page:** `caption` null plus `caption_on_previous_page`; the table is not a
  continuation. A number found only in the running text: `number_printed` null plus `number_in_running_text`.
- **`lines`**: every table carries the full list of its Azure line numbers (cells only, no caption or note).

## Conventions for Part PAGE, fixed on 2026-11-10 after the keyers reported (final key and scorer)

The keyers met the same grey areas and chose differently; these are the rulings. Where a ruling says "the scorer
accepts X or Y", the print allows both names and neither is an error of the pipeline.
- **A label on its own line** («الملخص», "Abstract", «الكلمات المفتاحية», "Keywords"): its own piece, role `heading`,
  with `"label_of": "abstract" | "keywords"`. The scorer accepts `heading` or the labelled role. A label run into the
  text stays in that text's piece.
- **A note at the foot of the page that carries an author's affiliation, e-mail or a received/accepted line:** role
  `footnote` (it is printed as one), with `"carries": "affiliation" | "dates" | "contact"` and its `note_label`. The
  scorer accepts `footnote`, `affiliation` or `front-matter` for it. An affiliation printed under the name, not as a
  note, is `affiliation`.
- **Bylines:** one piece per author; a call mark on its own Azure line joins its author's piece.
- **Abstract:** one piece per printed paragraph; dash or bullet items inside an abstract are `abstract`.
- **Verse:** one `verse` piece per bayt (both half-lines, right then left).
- **A note under a table, outside its frame** (significance levels, source): role `other` with `"table_note": true`.
  The scorer accepts `other`, `caption`, `paragraph` or `footnote`. A note inside the frame belongs to the `table`.
- **Bold or numbered lead-ins:** on its own line it is a `heading`; run into the sentence it stays in that paragraph
  or list item. Where the keyers still differ after looking, the piece is `unsure` and left out of P1.
- **A reference whose continuation line carries its own printed number, bullet or dash:** grouped as the reader would
  (one reference), with `"printed_numbering_wrong": true`.
- **Note labels and calls:** as printed, without brackets, in the printed digit set; the scorer folds digit sets.
- **Reading order** is the order a reader follows, by the language of the page. Running heads and page numbers are
  left out of P3. First pages are reported apart in P3 (the pipeline stores front matter in a logical order).
- **Cover sheets** (a repository's page before the article): pieces are `front-matter`, page gets `"cover_sheet": true`.
- **`continues_*` flags** are set only when the piece itself is cut by the page edge.

## Conventions for Parts FRONT and REFS, fixed on 2026-11-10

- **Digits** are typed in the printed digit set everywhere (page numbers included); the scorer folds digit sets.
- **Author names** keep printed honorifics (د. / أ.د. / Dr.) in `printed`; byline labels (بقلم، للأستاذ، إعداد، BY) are
  dropped. The scorer reports names with and without honorifics.
- **Subtitles:** printed punctuation is kept; " : " is added only when the subtitle stands on its own line with none.
- **Number ranges in an Arabic line** are written in reading order, the first number met reading right to left
  (474-496, not the left-to-right glyph order 496-474).
- **`source`:** the journal for an article; the publisher for a book; the university for a thesis; the proceedings or
  conference name for a conference paper; the book title for a chapter (its publisher goes in `publisher`).
- **Stripped from fields:** trailing separators, "pp." / «ص», "Vol." / «مج» / «ع», and the "&" / "and" / «و» before the
  last author. Quote marks printed around a title are kept. Words broken by an end-of-line hyphen are joined.
- **Python with an image library:** use `/home/appuser/inkscript/experiments/49_correction_desk/.venv/bin/python`
  (PIL) or the repo `.venv` (cv2). Do not use any other project's environment.
- **Boxed journal section labels above the title** («البحوث والدراسات», «المقالات» in journal 0130): role `running-head`
  with `"either_ok": ["running-head", "front-matter", "other"]` (ruled 2026-11-10 after the first-half adjudication;
  the 5 pages concerned stay `unsure` in final key v1 and re-enter scoring at the next key revision).
- **A received/accepted line printed at the end of an article** (journal 0246, boxed, after the references): role
  `front-matter`, not a footnote.
