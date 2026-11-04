# Experiment 51 progress

- 2026-10-22: read CLAUDE.md, briefing, D30-D35, prompt43 (v3.3), jats_coverage, 48 README, glossary.
- count_answers.py -> out/answer_counts.json (what the 600 v3.3 answers hold: metadata keys, block types, W fields).
- count_masters.py -> out/master_counts.json (regex patterns over the masters' printed text + structure counts).
  First pass had noisy patterns (hadith, metre, ads, quran braces = LaTeX); refined.
- Surprise: Persian yeh/kaf (ی ک) in many articles' text: Azure's letters, not the print's.
- count_alto.py -> out/alto_counts.json (ALTO roles: furniture, other article, show-through; no PRINTED_IMG_NR, no styles).
- snip.py: helper for real examples.
- Surprise 2: src/inkscript/text.py already maps Azure's ی/ک look-alikes, yet 172 masters hold ی and 112 hold ک (exp 43
  path does not apply it).
- Next: build_inventory.py (items by hand, counts resolved from the three JSONs) -> inventory.json; then README, HTML.
- inventory.json built: 235 items
- page built, copied to Desk public/inventory; Desk (next start) returns 404 without rebuild
