# The lead's prediction for OCRia-1 on the exam (written 2026-11-24, before any model output existed)

Asked by the owner: "what is your prediction?" Written down so it can be checked against the result.

| Measure | Prediction (most likely range) | For comparison |
|---|---|---|
| Letters wrong (folded, punctuation ignored) | 2–4% | Azure 0.6%, our reader 0.7%, ocria-nano 8.9% |
| Words wrong (same basis) | 6–12% | Azure 2.3% |
| Printed lines dropped | 1–3% | pipeline 0% |
| Invented text | under 1% of output, but 1–3 pages of 214 looping or cut by the token limit | pipeline: none possible |
| Tables found | 90–95% | pipeline 100% |
| Table shape right | 70–80% | pipeline 100% |
| Table cells right (folded) | 80–90% | pipeline 98.5%, LiteParse 28.7% |
| Reading order, one column / two columns | 98%+ / 85–92% | pipeline 99.1% / 100% |
| Headings found | 85–90%, with some invented | pipeline about 98% |
| Cost on a rented RTX 5090 | $0.15–0.40 per 1,000 pages | Gemini structure step $7.80 per 1,000 pages |

Chances: letters wrong under 1%: about 10%; better than Azure (under 0.6%): about 3%; between 1.5% and 5%: about
60%; over 5%: about 25%.

Reasons: trained mostly on Latin-script pages and tagged English only; a model that writes a page makes errors a
line reader cannot (skips, repeats, tidied spelling, digits converted); earlier whole-page readers on our Arabic pages
were behind Azure (Claude Opus as reader, experiment 60; Reducto, experiment 59). Expected Arabic-specific faults:
Arabic-Indic digits written as Western digits, hamzas "corrected", right-to-left table columns mirrored, the right
column of two-column pages not always first.

What each outcome would mean: under about 1.5% letters wrong: a strong case for fine-tuning the same open base model
(Qwen3.5-4B, Apache-2.0) on our own pages; 2–5%: plausible but it needs real Arabic training data and our exam as the
reward; over 8%: Arabic is effectively unsupported and the base model would need far more than a fine-tune.
