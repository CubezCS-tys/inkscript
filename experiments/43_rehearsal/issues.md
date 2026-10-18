# Experiment 43 — issues from the owner's marks

Written by `gold43.py` from `issues.json` (edit with `gold43.py issue ID --status ... --pattern ...`). Each "no" from a hand check or a review page, with its note, the pattern it belongs to, and what became of it: open / code rule (rules43, replayed free on saved answers) / prompt change (needs calls) / won't fix.

## open (0)

(none)

## code rule (4)

| id | date | article | run | page | lines | pattern | note | rule / change |
|---|---|---|---|---|---|---|---|---|
| i2 | 2026-10-18 | 0197-002-001-003 | v2_55 | 2 | 2:8 | exclamation_as_call | Text shows (١) where the print has (!) after «وهكذا»: the author's exclamation, not a footnote call. Same article as the missing page number. | rules43.exclamation: a fix turning Azure's «(!)» into «(١)» is refused and a call on it dropped. 41 and v2 both made the fix (41 also linked it to fn-2-1); the run report's 'regression' was wrong. Now «(!)», unlinked; the page's note «١ - المترجم» has no call. |
| i3 | 2026-10-18 | 0493-000-029-001 | v2_55 | 1 | 1:5 1:6 1:7 1:8… | text_in_figure | TV drawing whose screen holds a paragraph: Azure's text drawn over the picture; the picture drawn over the title. | rules43.text_in_figure (block wholly inside a figure box -> the figure's lines; not when the figure also holds a title/heading/byline: 0881's banner photo) + masters43 <p content-type=text-in-figure> + view 'text' button; rules43.figure_trim (figure box cut back to the title line's edge). |
| i4 | 2026-10-18 | 0493-000-029-001 | v2_55 | 4 |  | other_article_marking | 'Another article' fading and a label on every block ruins the reading. | views43: one quiet mark per contiguous region (thin rule, one label), muted text, pictures inside the region belong to it, bar toggle 'Hide other articles' (localStorage). p4 (printed 7) is truly another article: a news report on the Arab Council's debate, after the article ends on printed 6. |
| i5 | 2026-10-18 | 0493-000-029-001 | v2_55 | 4 |  | text_under_figure | A round photo sits in the text; our text runs under it (print flows round it). | views43.wrap_floats: per printed line, floats as wide as the print leaves the line short (Azure's line boxes), so the text flows round the picture. |

## prompt change (0)

(none)

## won't fix (1)

| id | date | article | run | page | lines | pattern | note | rule / change |
|---|---|---|---|---|---|---|---|---|
| i1 | 2026-10-18 | 0197-002-001-003 | v2_55 | 1 |  | page_number_missing | Page number «-٨-» missing at the foot of the first page (later pages show theirs). Same article as the (!) issue. | Azure never read it: no line or word at the foot of p1 in Azure's JSON (p2's «- ٩ -» is read and placed). Every page-number line Azure read in the 55 is already furniture (185 lines). Not invented in code. |
