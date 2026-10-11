# 32 · An open-source reading stack of our own

**Question.** Can we stop relying on Azure and build our own open-source stack that reads scanned Arabic
journals as accurately as possible (text, equations and tables), and in what file format should the result
live? (Owner's change of direction, 2026-10-11; the font-faithful PDF work of experiments 16–31 is on hold.)

**Method so far.** Desk research by four agents, in `research/`:

- [research/01_models.md](research/01_models.md): open document models and OCR tools, Arabic results, licences, hardware.
- [research/02_formats.md](research/02_formats.md): file formats for text, maths and tables; recommendation: keep JATS + ALTO, add MathML formulas and XHTML tables.
- [research/03_build.md](research/03_build.md): how document VLMs are built, fine-tuning for Arabic, data, guarding against invented text, measurement, cost; a staged plan.
- [research/04_newspapers_reflow.md](research/04_newspapers_reflow.md): newspapers: cutting a page into articles (state of the art, Arabic gap), METS + ALTO per issue with JATS per article, re-typesetting Arabic (LuaLaTeX, HTML/CSS, Typst), search and AI-dataset records, what the best archives show.

**Result.** Discussion phase; nothing built or measured yet.
