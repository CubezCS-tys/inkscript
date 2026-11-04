# Experiment 66 — the D30 guard: refuse Gemini's "fixes" of words the print got right

**Question (owner-approved, 2026-11-02).** D30: the text is the print as printed. Azure's misreadings are fixed
(Gemini's `fixes`); the author's own misprints stay, with the correction beside them (`sic`). Experiment 60 found
Argon sometimes "fixing" words that were printed right (first→firsf, يريد→يزيد, أستراتيجية→أستواتيجية) or
overwriting a printed misprint (للتواقع→للواقع). How often does that happen in the current runs, what separates a
good fix from a bad one, and can a deterministic rule refuse the bad ones without losing the good ones?

**Status.** Done 2026-11-02, $0 (no model calls; read-only on all data). Module, tests and the patch are ready; **the
patch is not applied** (experiment 65 is editing experiment 43/41/47 code) — the lead integrates it. Log:
[progress.md](progress.md).

## Answer

- **24,528 Gemini fixes** in the saved answers of the 780 current versions (release R20261102T155701:
  v33_300_final_lettersfix 10,136 · v33_300b_fix3_lettersfix 8,782 · j0130_final 4,621 · v2_55 989); 24,339 of them
  are in the current masters. Judge and retry patches carry no fixes.
- **Looked at on the scans: 270 fixes** (stratified, 7 strata) + **40 refusals** for a fresh check. Per stratum (bad =
  the print was right, B, or the print's misprint was overwritten, M):

  | stratum (fixes in it) | good / bad B / misprint M / unclear | B+M share, 95% |
  |---|---|---|
  | Azure sure (≥ 0.95), its word a known word, Gemini's not (53) | 35 / 6 / 2 / 2 | 19% [10, 33] |
  | Azure unsure, known → non-word (571) | 36 / 2 / 0 / 2 | 5% [1, 17] |
  | **Azure sure, known word → known word (1,102)** | 34 / 7 / 3 / 1 | **23%** [13, 37] |
  | **Azure sure, Azure's word not a known word (248)** | 17 / 0 / **15** / 3 | **47%** [31, 64] |
  | Azure unsure, known → known (6,738) | 31 / 4 / 0 / 5 | 11% [5, 26] |
  | Azure unsure, non-word (3,184) | 31 / 1 / 1 / 2 | 6% [2, 20] |
  | edit kinds typical of Azure: punctuation, digits, Persian look-alikes, vowel marks, accents, mixed script (12,243) | 28 / 0 / 0 / 2 | 0% [0, 12] |

  Weighted to all fixes: **≈ 1,080 bad fixes (4.4%) and ≈ 290 overwritten misprints (1.2%)**; ≈ 94% of fixes are
  right. (The weighted totals lean on small counts: the 6,738-fix "unsure, known → known" stratum alone carries ≈ 770
  of the 1,080, from 4 cases.)
- **What separates them.** Only two signals carry: (1) **Azure was sure of the word** — bad fixes and overwritten
  misprints sit almost all at Azure confidence ≥ 0.95 (33 of 41; 20 of 21 misprints); (2) **the edit changes
  Arabic letters** (dots, a swapped letter, a letter added or dropped) **into a known word** — Gemini "correcting"
  toward the dictionary. Gemini writing a printed misprint *as printed* (Azure's known word → Gemini's non-word:
  «هذاا»، «االتعلّم»، «Centuary»، «Enviromment») is right 35 of 43 times and must stay. Latin-letter edits are right
  in the sample (31 of 32; firsf/subsequeently of experiment 60 were at Azure 0.20 / 0.84). Hamza / ya / ta
  marbuta edits are mostly right (25 of 28) and are D30's orthographic class. Azure's confidence above 0.95 does not
  separate good from bad further, nor do page quality, Gemini's `why`, or the edit's size.
- **The rule** (`experiments/43_rehearsal/d30guard43.py`): a Gemini fix is **refused** when every word it touches was
  read by Azure with confidence **≥ 0.97**, the edit **changes Arabic letters** (dots / swap / insert / delete — not
  hamza, ya, ta marbuta, vowel marks, Persian look-alikes, digits, punctuation, Latin), it is **not** ال↔ل at a word's
  start (6 of 7 right) nor added text Azure left out, and **Gemini's word is a known word** (wordlist43). A refused fix
  is never applied: the printed (Azure) word stays and Gemini's word travels beside it as a flag
  `{"line","text","corr","why","kind":"model-suggestion"}` in the answer's `sic` list. Code fixes (`why` "code: …")
  are never touched; without Azure's word confidences or the word list it refuses nothing.
- **Measured.**

  | | refused that were bad (B+M) — precision | of all bad fixes refused — recall | good fixes refused |
  |---|---|---|---|
  | fresh check: 40 random refusals, not in the sample (26 judged) | **69%** [50, 83] (B 3, M 15, good 8) | — | — |
  | sample, weighted to all 24,528 fixes (stratified bootstrap) | 66% [40, 91] | **16%** [8, 35] (≈ 200 of ≈ 1,370) | **0.5%** [0.1, 1.0] (≈ 105) |
  | held-out half of the sample (37 articles, only 5 bad) | 2 of 4 refusals bad | 2 of 5 | 2 of 83 |

  At 0.95 the rule refused 595 instead of 408, but the 0.95–0.97 band was mostly good fixes (36% bad), so 0.97.
  Of the refusals, the largest part (≈ 58% in the fresh check) are **overwritten misprints**, which the guard turns
  into exactly what D30 asks for: the print kept, the correction beside it.
- **Effect on the current runs** (simulated, no master written; `out/simulate.json`, `out/decisions.jsonl`):

  | run | fixes | refused → model-suggestion flags | articles touched | most in one |
  |---|---|---|---|---|
  | v33_300_final_lettersfix | 10,136 | 199 (2.0%) | 100 | 15 |
  | v33_300b_fix3_lettersfix | 8,782 | 154 (1.8%) | 81 | 14 |
  | j0130_final | 4,621 | 20 (0.4%) | 18 | 2 |
  | v2_55 | 989 | 35 (3.5%) | 17 | 6 |
  | **all** | **24,528** | **408** (dots 148, swaps 126, letters added/dropped 134) | 216 | |

  By the fresh check's rates: ≈ 280 words go back to what the paper says (≈ 235 printed misprints that become `sic`
  flags, ≈ 50 right words Gemini had changed), and ≈ 125 Azure misreadings stay in the text with Gemini's reading
  flagged beside them (searchable; a person can accept it in the correction tool). Experiment 41's Store accepts every
  model-suggestion flag (`hook66.py`: 1010-001-011-014 fixes 364 → 349, flags 1 → 16, 0 rejected).
- **What it does not catch** (the other ≈ 84% of bad fixes): fixes of words Azure was unsure of (ya dots added that are
  not printed «فى»→«في», a printed hamza removed «الإسلام»→«الاسلام», «رقعة»→«رفعة» at Azure 0.78); Gemini's wrong
  "printed misprint" claims that produce non-words («ضمائر»→«ضسائر»، «تعليم»→«تعيم»، «ملحقة»→«ملحفة»); Latin
  (experiment 60's firsf). No deterministic signal in Azure's output separates these from the good fixes beside
  them; they need the ink (a dot / letter check on the word crop) or a second reader.
- **Cost, honestly:** on worn or faded prints Azure is sometimes *sure* of a wrong reading (0005-055-003-004:
  «تقيل»، «عمى»، «العاوم» for تقليل، علمى، العلوم, Gemini "faded lam"; 1080-002-010-015, a tan scan with 15
  refusals). There the guard keeps Azure's misreading in the text, flagged. That is the price of the 0.5% of good fixes
  refused.

## Examples (judged on the scan)

Refused, right to refuse:
- 1080-002-010-015 p8 «حال نحو تطبيق» → Gemini «مال» (Azure 0.988): the print says حال.
- 0130-020-079-004 p2 «بنسبة» → Gemini «بنسية», "a printer typo" (0.985): the print says بنسبة.
- 1010-006-011-015 p6 printed «ثلك» → Gemini «تلك» (0.973): the misprint stays, flagged.
- 0604-003-008-001 p3 printed «أيامم» → «أيامهم» (0.987); 0763-004-002-001 p4 printed «ترجها» → «ترجمها» (0.973);
  0775-014-001,002-008 p3 printed «هذ» → «هذا» (Gemini's own `why`: "ink shows هذ … Keep as sic").
- 0852-001-004,005-003 p8 «الأقتصاد القوي» → «القومي» (0.977): the print's reading is a sound one.

Refused, wrongly (Azure sure and wrong):
- 2408-000-010,011-012 p11 Azure «دورة» → Gemini «دورت» (0.987): the print has the open ta (a misprint Gemini wrote
  as printed). At 0.95 the guard would also have refused 0604-003-008-001 p2 «على الأرض» → «علم الأرض» (0.968), right.
- 0005-055-003-004 p5 «العاوم» → «العلوم» (faded lam).

Kept, right to keep: «هذاا الكتاب» (double alif printed), «االتعلّم», «Centuary», «Introvnersion», «ويجررن», ال↔ل
(«الطالب»→«لطالب»), every hamza / ya / ta marbuta form, «(λj)», «βi», «R_i : مجموع».

## The patch to apply (after experiment 65)

`d30guard.patch` (unified diff, two parts):

1. **The hook — `experiments/43_rehearsal/rules43.py`** (required). In `normalize`, just before the last rule:
   ```diff
        table_missed_cells(ans, lines, words, log)
   +    import d30guard43                          # experiment 66 (D30 guard): a risky fix becomes a model-suggestion flag
   +    d30guard43.guard(ans, lines, words, log)
        fixes(ans, log)
   ```
   and `fixes_refused_d30=[]` in `new_log()` so the rule shows in every summary. It runs after the letter fix
   (lettersfix43 wraps `table_missed_cells`), sees Azure's words with confidences (`masters43.azure_words`, which every
   build passes), and does nothing where `words` is None (tests, replay without words). Today's rules43 tests and the
   guard's tests pass with the patch (44 passed, on a patched copy).
2. **The distinct type — `experiments/41_azure_structure/masters.py`** (recommended, one line): the sic run writes
   `content-type = s.get("kind") or "sic"`, so a refused fix appears as
   `named-content[@content-type="model-suggestion"]` (JATS allows any content-type; it is listed with the sic flags
   in back/notes `suspected-misprints`). Without this part a refused fix shows as a `sic` — the text is right either
   way. Then `experiments/47_platform_v2/parse47.py` (lines 114, 586) must accept `model-suggestion` beside
   `reader-fix` / `sic` and load it as its own layer (applied_to_text 0) — otherwise the platform drops those flags
   when part 2 is applied.

**What the lead runs** after integrating: the four rebuilds the way `43_rehearsal/out/lettersfix/lettersfix.sh` did
(`lettersfix43.py plain` → `patches43.py build` → `lettersfix43.py validate`) into new folders (e.g.
`v33_300_final_d30`), then compare with `simulate66.py run`'s per-run counts (408 refusals; each must appear as a
flag, none as a fix), and the release loader. Check pages: 1010-001-011-014 (15 flags), 0005-055-003-004,
1080-002-010-015 (the faded-scan cost).

## Method

- `collect66.py`: every fix in each current version's saved answers (`43_rehearsal/out/<run>/raw`, chunk files as
  the masters use them), with the line's Azure text, the Azure words its `from` touches and their confidences
  (Azure JSON via `masters43.azure_words`), the edit kind (`d30guard43.edit_class`: spacing, punctuation, vowel
  marks, Persian look-alike, hamza, ya/alif maqsura, ta marbuta, digits, digit↔letter, letter→mark, dots (same
  dotless skeleton), Arabic swap / insert-delete, Latin accent / case / swap / insert-delete, mixed script, rewrite),
  script, and the word test of wordlist43 (273,016 folded words seen in ≥ 3 catalogue abstracts / titles or Azure
  texts, clitics and suffixes stripped) for the changed words on each side; joined to the release's
  `text_corrections` to mark which are in the current masters.
- `sample66.py`: 7 strata (Azure sure / unsure × Azure's word known / not × Gemini's word known / not, plus the
  edit kinds typical of Azure), 30–45 each, oversampling the sure strata; tune / test halves by article (hash).
  Contact sheets: each fix's word at up to 7× beside its line in context (`out/sheets/`), Azure's words boxed.
- Judged by eye on the scans (`out/labels.tsv`, `out/vlabels.tsv`, one reason per fix): G the print shows Gemini's
  text; B the print shows Azure's text, which is a right word; M the print shows Azure's text, which is the author's
  or printer's misprint (should have been `sic`); U not decidable (faded dots, a page whose render has no text).
  Hamza / ya / ta marbuta were judged by the ink like any letter.
- `analyze66.py`: rates per stratum with Wilson intervals; rule variants (Arabic letter edit at ≥ 0.90 / 0.95 /
  0.97; with / without ال↔ل and added text; requiring Gemini's word known; Azure's word known / unknown) scored as
  weighted recall / good-blocked / precision with a stratified bootstrap. The rule's shape was chosen looking at all
  270 labels, so its clean held-out number is the **fresh 40** (`simulate66.py validate`): refusals drawn at random
  from the 555 outside the sample, judged the same way.
- `simulate66.py run`: the guard over all 24,528 fixes; `hook66.py`: the hook end to end in memory on real answers
  (rules43 + the letter fix, with and without the guard, then experiment 41's Store).

## Files

- `../43_rehearsal/d30guard43.py` — the module (edit kinds, features, `decide`, `guard`); `../43_rehearsal/test_d30guard43.py` — 7 tests.
- `d30guard.patch` — the hook (rules43) and the distinct type (masters.py).
- `common66.py`, `collect66.py`, `sample66.py`, `zoom66.py`, `analyze66.py`, `simulate66.py`, `hook66.py`.
- `out/` (gitignored): `fixes.jsonl` (24,528), `sample.jsonl` + `labels.tsv` (270), `validate.jsonl` + `vlabels.tsv`
  (40), `sheets/`, `vsheets/`, `analysis.txt` / `.json`, `decisions.jsonl`, `simulate.json`.
