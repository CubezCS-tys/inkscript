# Experiment 63 progress notes

- 2026-11-02 read exp 56 README, decisions (942 lines, 908 standing), packets, institutions, authority.
- sample63.py: stratified sample (seed 63), blind views out/blind63.txt (no exp 56 decision/reason/ids shown); the key in out/sample63_key.json is not read until my answers are on disk.
- blind judging of all 230 written to out/mine63.jsonl (frozen copy out/mine63_frozen.jsonl, sha256 recorded below) BEFORE opening the key. Journal country/publisher looked up from the release (out/journals63.json) as catalogue evidence.
- Exposure note: my first `head` of decisions56.jsonl printed ~11 decisions (ids listed in compare63.py EXPOSED); the README's "hard calls" also name ~25 cases. Those are reported separately.
4eadbaf33a95eb86155bf49a4cd0afacde61e208b47fc00ba8a3b61c9bf063be  mine63_frozen.jsonl
- key opened; side by side (out/sidebyside63.txt); adjudication written to out/adjudication63.json: 208 agree, 14 exp-56-conservative, 6 both acceptable (types), 2 minor errors (S107 one country for a two-country statement; S182 «جامعتى القاهرة وصنعاء» row merged into Sana'a).
- hardchecks63.py over all 908 -> out/hardchecks63.json (own gazetteer; fixed a «وجدة»→«جدة» false match).
- open review of the other 678 (openreview63.py -> out/openreview63.txt, findings out/openreview63_findings.json): 2 errors (O351 Arab News source line linked; O495 a printed society called not-an-institution), policy questions (degree-from, former posts).
- stats63.py -> out/numbers63.json: blind 208/230 agree (unexposed 168/184), strict precision 228/230 (Wilson 96.9–99.8); census 4 errors / 908 (99.6%); rule 99.7%, judgement 99.4%.
- README.md written (apply rule, 7 owner cases); line 63 added to experiments/README.md.
- tests/test_docs.py: link test passes; the index test fails only on 61_nothing_lost / 62_librarian_works having no README yet (other agents' experiments in progress, not touched).
