# Experiment 76: fine-tuning Nuqta on our own pages (pilot)

**Question (owner, 2026-11-04).** Could we fine-tune Nuqta-Arabic-OCR-4B on our own Mandumah pages, using the
Gemini and Azure outputs we already have?

**Status: planned, nothing run ($0).** The plan, with every number measured from disk, is in [PLAN.md](PLAN.md). It
runs after experiment 75's document 3, and only once the owner says yes.

**Method so far.** Read-only measurements:
- what Argon, Azure and scan material is on disk (`inventory76.py`);
- how often two readers agree on a line, and how often an agreed line is right against the owner's 20 checked
  pages (`consensus76.py`, `pagelevel76.py`);
- a split of the journals into training and test.

**Result so far.**
- 40,612 pages with Argon output are on disk, all with their scans.
- Argon edits Azure rather than reading the page itself, so their agreement is not a check: Argon's untouched lines
  are 93.8% right.
- Azure and a blind Gemini line reading agree on 58% of lines, and those lines are right 449 times out of 450.
- The pilot therefore trains on whole pages with the loss on 2-of-3-agreed lines only, starting with 173 free
  yardstick pages (4,239 lines) for ≤ $3. The cap is $50.

**What it changed.** Nothing yet. One decision is open for the owner: the two owner corrections of document 2
disagree on spaces before punctuation, and training needs one rule.
