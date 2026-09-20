# 10 — Can the document's own alphabet read a page?

**Question.** The owner's OCR idea: trace the letters and match them against a
database of stored letters. Without any OCR text, how well can the atlas of
experiment 09 read?

**Method.** `reader.py`: learn the atlas on pages 1–4 of the reference document
(labels from Azure); read page 5 blind — not even the number of letters —
as the best chain of atlas letters along each piece's pen path (likeness +
hard facts + usual length, under the grammar initial–medials–final or one
isolated letter); compare with Azure's reading.

**Results** (570 pieces).

| Version | Pieces read as Azure reads them |
|---|---|
| first attempt | 8.6% (everything chopped into too many letters) |
| a letter must earn its place | 27% |
| match stored examples, not only the mean picture | **41%** |

Isolated letters 67%; joined pieces ~20% (2–3 letters), 0 of 23 at five or
more. Typical error: `خير` → `تببر` — a slice of almost anything resembles a
tooth letter. You must cut before you can match, and match before you can cut.

**What it means.** Not a replacement for Azure or Gemini. The promising use is
as a *checker*: cut by the known word (which we do well), then ask whether the
ink fits a look-alike reading better. That is milestone 1 in `docs/roadmap.md`.
The switch from mean pictures to individual examples was the largest gain —
small marks are what tell letters apart, and a mean blurs them away.
