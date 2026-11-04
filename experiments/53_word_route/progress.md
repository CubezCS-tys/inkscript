# Experiment 53 progress (Word route)

- 2026-10-22: 139 stems (0130, بحوث ومقالات, 2009–2016) from marc.db; 137 in legacy/ (missing 0130-011-043-003, 0130-017-066-003).
- Word originals: all 139 found as `<stem>.doc` (flat folders; 137 in ai_data/journals/docs, rest ai_batch2/docs). All old .doc (OLE), none .docx.
- soffice 24.2 present: converted all 139 .doc -> out/docx (batches of 20, peak RSS ~490 MB).
- Legacy PDFs fetched with aws s3 cp (inkscript fetch has no legacy/ prefix): out/legacy_pdf.
- inspect53.py (out/inspect.json): styles are ~all "Normal" (no heading styles; outline levels in 4 files only);
  real footnotes 98 in 38 files, 0 endnotes; 797 real tables in 100 files; 261 drawings in 56; 178 text boxes in 10;
  6,205 auto-numbered paragraphs (labels not in the text: need numbering.xml); fonts Traditional Arabic (body),
  PT Bold Heading (headings, a strong signal); headers carry the running head + «العدد ...».
- Legacy PDFs: LibreOffice 24.2 (2026-09-03), US Letter pages (not the print's size), text layer good but justified
  lines carry stray Latin letters (kashida glyphs mapped to Z/A/V...): «معرفZة».
- Reuse plan: inkscript.enrich.catalogue (catalogue index ~/.cache) + enrich.jats.E + schemas.validate_jats (import
  only); exp 43 jats43 (regexes, dates) and refs43.citation (field writer) imported with dont_write_bytecode.
- 2026-10-22 build53.py (+docx53.py): 139/139 masters valid against the JATS 1.4 DTD. Totals in out/build.log.
  Fixes made on the way: URL guard; empty endnote group; colon headings only <=5 words and not a lead-in («الآتية:»);
  REF_HEAD anchored (a heading «مصادر القيم» opened a reference list); a table after the list -> untitled appendix;
  title in the printed spelling when the words are the catalogue's (catalogue drops hamzas); notes called from the
  front -> author-notes.
- compare53.py on the 23 scan+legacy+Word documents (out/compare.json, compare_breaks.json): Word page start ==
  catalogue fpage in 6 (text = print: 92-97% / 95-99% word overlap, one at 65%); != in 17 (16 of journal 2044 + 1):
  those Word files are another text (overlap 0.11-0.47). Page estimates weak (char share +-1 ~40-90%; Word's own
  lastRenderedPageBreak in native docx +-1 on 3 of 5).
- Word files for the 308,593 legacy stems: 302,961 have one (136k .docx, 167k .doc only). word_files_all.txt.
- refcompare53.py: refs/article 39.1 (with a list) vs v33 EduSearch scan masters 19.8.
- gate 1 raw answers (read only): $0.060 per 10-page chunk, 28.9k in / 6.2k out tokens.
- Final build (after ref parser fixes: quoted years, Hijri without هـ, comma styles, journal names): 139/139 valid;
  refs 4,613, with fields 4,465, author+year+title 4,408. Hand look of 5 articles (4 minor, 1 serious->minor after
  the name fix); 60 headings sampled: 54 real; 40 refs: 18 right / 17 minor / 5 wrong (4 fixed after).
- abscheck53.py: catalogue Arabic abstracts vs Word: 90/90 >= 0.95 overlap.
- price53.py: lean text-only call $0.028 Argon / $0.010 Flash an article now (x2 later); full $0.050 / $0.019.
- README.md written; line 53 in experiments/README.md. tests/test_docs.py fails only on 52 (no README yet; not ours).
