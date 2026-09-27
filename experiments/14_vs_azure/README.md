# 14 · Ten documents from the live upload, our layer against Azure's

**Question.** The owner is uploading Azure's searchable PDFs to the bucket and
asked whether the inkscript vector PDFs are actually better. Experiment 07
answered that on three hand-picked test documents; this is the same question on
a random sample of what is being shipped right now.

**Method.** Ten documents drawn at random (seed 22) from the 1,440 uploaded on
21–22 September 2026, fetched with `inkscript fetch`, built with
`inkscript native --vector --verify` and no `--frontpage-dir` — so **both
layers carry the same Azure reading** and the comparison is about how a layer is
READ, not who recognised the page. 106 pages, 42,843 words.

```
python compare.py out/azure out/ours
```

Read with pdfium (Chrome's engine, pinned 5.12.1 / build 7947). The reference
for both layers is what our layer placed.

## Result (2026-09-22)

| | inkscript vector | Azure searchable PDF |
|---|---|---|
| words copy out intact | **42,841 / 42,843 (100.0%)** | 41,943 / 42,843 (97.9%) |
| lines in reading order | **3,858 / 3,858 (100.0%)** | 3,061 / 3,858 (79.3%) |
| numbers intact, Chrome | **1,244 / 1,244 (100%)** | 1,229 / 1,244 (98.8%, 15 reversed) |
| letter boxes (widest ÷ narrowest char in a word) | **5.88** | **1.00** |
| median KB per page | 468 | 28 |

**The letter-box row is the structural difference.** 1.00 means every character
inside a word was given exactly the same width: the viewer is slicing the word
evenly, because Azure's layer never knew where the letters are — one positioned
string per word, letters implied. That is *equal slicing*
([glossary.md](../../docs/glossary.md)), and it cannot follow Arabic, whose
letters differ in width by about the factor our layer actually shows (5.88).

**Line order is the biggest measured gap.** Azure's worst document here returns
only 53.6% of its lines in reading order (`0367-000-030-002`); `0368-000-113-005`
68.0%. Copy a paragraph and the words arrive shuffled between lines. Ours: 3,858
of 3,858, no exceptions.

**Size is the honest cost.** Our vector page is ~17× an Azure page, because every
occurrence carries its own traced outline (D3) and nothing is reused. That is the
price of the rule, not a defect to optimise away — see experiment 13 for the
output that *is* allowed to reuse glyphs.

## Looking at it

`viewer.py` builds one self-contained page, `out/compare.html` (8.7 MB, opens
with no server):

```
python viewer.py out/azure out/ours
```

A document picker, and three views. **character boxes** draws every character's
selection box on the page — *both panes show the same scan*, so only the boxes
differ: Azure's are a uniform grid wide enough to bury the text, ours hug each
letter. **vector edition** replaces our side with the ink-as-text page, no scan
underneath. **what copy gives you** shows the text each PDF actually hands over,
with every printed line that came back out of order marked red. Arrow keys or
`j`/`k` move between documents; space toggles the boxes.

Per page, lines that did not survive the copy: Azure 0–20, ours 0 (one line on
`0367-000-011-023` p3).

## Comparing them as PDFs, by hand

`side_by_side.py` puts the two files themselves in the browser's own PDF viewer,
so a drag selects in each exactly as it would if you opened them yourself. It
symlinks the PDFs (nothing is copied) beside an index:

```
python side_by_side.py out/azure out/ours
python3 -m http.server 8733 --bind 127.0.0.1 --directory out/side_by_side
# then http://127.0.0.1:8733/
```

Chrome refuses to load a PDF into a frame from `file://`, hence the server.
Left pane is Azure's searchable PDF, right pane ours — the **same scan** with an
invisible layer over it, so they look identical until you select. A button swaps
our side to the vector edition (no scan under it at all), and there are two boxes
at the bottom to paste what you copied from each.

## An engine trap worth recording

Numbers survive Chrome fine in **both** layers. In **MuPDF** they do not: of the
same 1,253 Arabic-Indic digit runs, Azure's PDFs return 31.0% intact and reverse
68.4% (`١٩٨١` copying out as `١٨٩١`). Chrome is the target
([decisions.md](../../docs/decisions.md), D4) so this changes no rule, but any
pipeline reading these PDFs with a MuPDF-based tool will silently corrupt dates.

*(Two samples read with MuPDF first suggested "numbers are reversed" generally;
measuring both engines showed it is engine-specific. Measure, never reason.)*
