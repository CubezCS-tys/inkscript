# Experiment 98 — independent audit of the "library map" labelling pilot (AI-Search project)

**Status:** done, 2026-11-23. Free and local; read-only on the other project's files.

## Question

The owner asked the AI-Search session (23 Nov): "have you asked inkscript about your work, check it and prove it?"
Until then this session had reviewed that project's plans and reported numbers but recomputed nothing. The library
map assigns one of 20 top-level subjects to each of the catalogue's 1,558,415 records with a Gemini model; its gate
result claimed 0.968 accuracy on a sealed test set. Are the numbers real, and is the test sound?

## Method

Everything under `/home/appuser/ai-search-eval-archive/2026-11-23-library-map/` was read, nothing written there.
`audit1.py` recomputes accuracy and coverage from the raw set, reference and label files with our own code;
`audit2.py` checks the dev/test split and what the labeller was shown; `audit3.py` checks the payloads actually sent,
the spend ledgers and the full-catalogue inputs. File times and sha256 hashes give the order of events. Fifty random
test records were labelled by this session from title, keywords and abstract BEFORE looking at any label
(`out/blind50_auditor.json`), then compared.

## Result

- **The headline reproduces exactly.** Test: acceptable-set accuracy 0.968, strict 0.912, coverage 0.924; no-field
  group 0.933 coverage / 0.995 accuracy; catch-all-only 0.875 / 0.985. Canary on 1,500 dev records: 0.968 and 0.843.
- **The split is clean.** No journal code, journal name or thesis university on both sides; no dev or test record in
  the 60k working sample; two generic identical titles («افتتاحية العدد») only.
- **The order of events holds.** Scorer last changed 39 minutes before any test label existed; the labeller's
  freeze file 40 seconds before the first test request; every hash in the freeze file matches; the test set was used
  by one run only.
- **No leak found.** Requests carry type, title, subtitle, keywords, author keywords and role flags only: no journal,
  field of study, e-mail or reference label. Journal names appear in 12 of 1,475 inputs, where the journal is named
  after its subject or the piece is the journal's own index.
- **Blind read of 50:** our primary equals the reference's strict primary on 46; the reference's primary is
  acceptable to us on 50 of 50; the labeller's label is acceptable to us on 45 of 46 classified (one clear error at
  confidence 0.85, which the reference also marks wrong).
- **What qualifies the headline.** The "acceptable set" includes subjects that one reference labeller gave only as a
  SECOND subject (341 of 1,475 records); 42 of the labeller's credited answers (3.1 points) match only such a second
  subject. Three honest readings: 0.912 strict; 0.937 counting either reference labeller's primary; 0.968 with
  seconds. All clear the 0.90 bar.
- **Not verifiable from here:** whether anyone opened the sealed reference before scoring (access times cannot show
  it); the provider's billing (ledgers sum to about $21–24 against the $23.47 reported); and the reference labels
  are model-made, as is this audit's blind read.

## What it changed

Verdict sent to the AI-Search session: the run may start; quote the range 0.91–0.97, not 0.968 alone.
