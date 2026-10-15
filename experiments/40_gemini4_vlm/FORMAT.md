# Experiment 40 — the common output format

Every approach writes **one semantic HTML file per page**, `out/<approach>/<page_id>.html`
(page ids as in `out/sample.json`, e.g. `0747-001-003-001_p006`). A whole-document approach may instead
(or as well) write `out/<approach>/docs/<stem>.html`, one `<section class="page" data-page="N">` per page;
`score.py` cuts it into pages. A page with no file counts as read empty.

Optional: `out/<approach>/<page_id>.meta.json` = `{"usd": …, "secs": …}` overrides the cost and time `score.py`
would otherwise take from `out/gemini_spend.jsonl` (tags starting with the approach's prefix and containing the
page id; a tag with only a document stem is shared evenly over that document's pages).

## Elements

The file may be a fragment or a full document; only what is inside `<body>` (if any) counts.
Reading order = document order.

| What is on the page | Write | Scored as (experiment 39's label) |
|---|---|---|
| title, section headings | `<h1>`, `<h2>`, `<h3>` | heading |
| body paragraph | `<p>` | body |
| numbered / bulleted list | `<ol>` / `<ul>` with `<li>` | list |
| bibliography / references | `<ol class="references">` (or `<section class="references">`) with `<li>` | references |
| footnote | `<aside class="footnote" id="fn3">…</aside>`, referred to in the text by `<sup><a href="#fn3">3</a></sup>` | footnote |
| verse (a line of poetry in two half-lines) | `<div class="verse"><span class="hemistich">…</span><span class="hemistich">…</span></div>` (one div per verse line) | verse |
| table | an HTML `<table>` (`<tr>`, `<th>`/`<td>`, `rowspan`/`colspan`), caption in `<caption>` | table (cells); caption |
| equation | inline `<span class="math">\(…\)</span>`; display `<div class="equation"><span class="math">\[…\]</span></div>` (LaTeX) | equation |
| figure / picture / chart | `<figure data-bbox="…">` (+ `<figcaption>`) | other; caption |
| running header, footer, page number | `<header class="furniture">…</header>`, `<footer class="furniture">…</footer>` | furniture |
| anything else | `<div class="other">` | other |

Attributes on any block:

* `dir="rtl"` / `dir="ltr"` and `lang="ar"` / `"fr"` / `"en"`;
* `data-bbox="x0,y0,x1,y1"`: the block's box in **0–1000 page coordinates** (x from the left edge, y from the top),
  as Gemini gives boxes; nested elements without one inherit their parent's.

Text: exactly what is printed, every vowel mark kept, no tatweel stretching needed (it is ignored), digits as printed
(Arabic-Indic stays Arabic-Indic). Footnote markers stay where they are printed (the `<sup>` text counts as text).

## What score.py takes from it

* **text** (for character error rate, invented / dropped words): every leaf block's text in document order, with
  math removed — LaTeX inside `span.math` or `\(…\)` / `\[…\]` / `$$…$$` is not page text (the references leave
  equations out too), except inline math with no `\ ^ _ {` (a bare number or letter), which counts as text.
  Table cells are separate text units, row by row.
* **layout**: each leaf block's label by the table above (an ancestor's class wins: anything inside
  `.furniture` is furniture, inside `.footnote` footnote, inside `.verse` verse, inside a table table), and its box.
* **figures** are reported (count, with boxes) but not scored.
