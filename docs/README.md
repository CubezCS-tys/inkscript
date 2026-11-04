# Map of the documentation

Start with [`../CLAUDE.md`](../CLAUDE.md). Each fact lives in one place:

| You want | Read |
|---|---|
| **The system today in plain words** (2026-11-02): the two paths (extraction / reconciliation) and the gates; the parts and how they connect; the Desk's pages; evaluations; shareholders; money; what's next | [overview.md](overview.md) |
| How the parts are built and run, file by file | [architecture.md](architecture.md) |
| Step-by-step procedures (tunnel, services, running a journal, loading, the Desk, money, backups) | [runbooks.md](runbooks.md) |
| A fresh session's first read (2026-10-23 to 2026-11-02): the two paths, what happened day by day, what is running, where sources disagree, what waits on the owner, money, the tunnel and the Desk's pages | [handoff.md](handoff.md) section 000 (2026-10-21/22: section 000a) |
| What is running, done and waiting right now (live) | the Desk's `/plan` page (`experiments/49_correction_desk/desk/plan/plan.json`); the owner's dashboard `/project` |
| The briefing for the agent on the server (2026-10-21): the Web-of-Science vision, where we are, where we go | [server-agent-briefing.md](server-agent-briefing.md) |
| Codex's continuation since 2026-10-17: assessment, revived tracing question, work for the returning Claude session | [codex-handoff.md](codex-handoff.md) |
| Where we are as of 2026-10-13: the owner, the specialists, exp 39, round 2, Vast, the server move | [handoff.md](handoff.md) |
| Why the project exists, in the owner's words | [vision.md](vision.md) |
| What works today, the numbers and their dates, spend and credit, where outputs are | [STATUS.md](STATUS.md) |
| Every idea: built, tried, parked, open — and where to pick it up | [ideas.md](ideas.md) |
| What comes next, in the owner's order | [roadmap.md](roadmap.md) |
| Why a choice was made | [decisions.md](decisions.md) |
| The two halves (OCR, geometry) and the commands | [pipeline.md](pipeline.md) |
| How a joined word becomes letters; the tools for debugging it | [letters.md](letters.md) |
| Every rule for writing the text layer, with the measurement behind it | [pdf-writing-rules.md](pdf-writing-rules.md) |
| A book's letters as an installable font; restoration | [typeface.md](typeface.md) |
| Data locations, running sets, memory, the watchdog | [operations.md](operations.md) |
| Taking the project to a server: what git holds, what must be copied, sizing | [moving-to-a-server.md](moving-to-a-server.md) |
| What a word means here | [glossary.md](glossary.md) |
| The first corpus-scale night and what it taught | [night-report-2026-09-18.md](night-report-2026-09-18.md) |
| Experiments: question → result | [`../experiments/README.md`](../experiments/README.md) |
| Linking and the Web-of-Science direction (2026-10-21/22) | [48 linking probe](../experiments/48_linking_probe/README.md) · [49 the Desk](../experiments/49_correction_desk/README.md) ([design](../experiments/49_correction_desk/DESIGN.md)) · [50 mind map](../experiments/50_mindmap/README.md) · [51 extraction inventory](../experiments/51_extraction_inventory/README.md) · [52 gate 1](../experiments/52_journal_gate1/README.md) · [53 Word route](../experiments/53_word_route/README.md) · [54 gate 2 selection](../experiments/54_gate2_selection/README.md) |
| Shareholders (2026-10-23/28) | [55 pitch and deck](../experiments/55_shareholder_pitch/README.md) · [57 business and technical documents](../experiments/57_shareholder_docs/README.md) |
| Extraction since 2026-11-02: nothing lost, leak fixes, the D30 guard, go-live, gate 2 | [61 nothing-lost audit](../experiments/61_nothing_lost/README.md) · [65 leak fixes + prompt v3.6](../experiments/65_fix_leaks/README.md) · [66 D30 guard](../experiments/66_d30_guard/README.md) · [68 go live](../experiments/68_go_live/README.md) · [69 fix-rule check](../experiments/69_fix_rule_check/README.md) · 70 gate 2 pilot (running; `experiments/70_gate2_pilot/progress.md`) |
| Reconciliation: the librarian, its blind checks, applied decisions, the production model | [56 institutions](../experiments/56_librarian_institutions/README.md) · [63 blind check](../experiments/63_verify_institutions/README.md) · [64 institutions applied](../experiments/64_apply_institutions/README.md) · [62 cited works](../experiments/62_librarian_works/README.md) · [67 cited works applied](../experiments/67_apply_works/README.md) · [71 librarian model test](../experiments/71_librarian_models/README.md) |
| Other tools tried (2026-10-30/31) | [58 Indra OCR](../experiments/58_indra_ocr/README.md) · [59 Reducto](../experiments/59_reducto/README.md) · [60 Claude vs Argon](../experiments/60_claude_reader/README.md) |
| The idea as an animation; the interactive storyboard | `demo/ink_to_text.html`, `storyboard/index.html` |

History is in `git log` (the commit messages carry the measurements) and in
the dated entries of [decisions.md](decisions.md).
