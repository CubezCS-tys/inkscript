"""Experiment 43: prompt v2 (derived from experiment 41's prompt, structure.PROMPT, which stays as it was).

What changed from v1 (each change is marked "v2:" in the text below; README "Prompt v2" lists them):
  1. other_article   a block type for the end or start of a different article printed on a shared page
  2. list vs body    when lines are a list, and when they are paragraphs that merely open with a number
  3. endnotes        a block type of its own, linked like footnotes; footnote = foot of the calling page only
  4. noise           only marks with no words; text is never noise (also enforced in code: rules43.never_noise)
  5. verse cut       one Azure line holding both halves: "cut" by word index instead of "splits"; ornaments listed
                     by word index and left out of the text (kept in the ALTO)
  6. misprints (D30) text stays as printed; a printer's error is a "sic" flag only, never a fix; three contrasting
                     examples from experiments 40/41
  7. small gaps      table column headers / units belong to the table; author names without role phrases; no
                     "missed" for running heads or page numbers Azure did not read

Inputs (page lines, images, chunking, chunk context) are experiment 41's, imported from its structure.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E41 = HERE.parent / "41_azure_structure"
sys.path.insert(0, str(E41))
sys.path.insert(0, str(HERE))
import structure as ST  # noqa: E402
import render43  # noqa: E402
render43.install(ST)                  # a page blank where Azure has text is re-rendered with its fonts (fix round 3)

PROMPT_VERSION = "v2"          # the default; run43.py --prompt v3 calls use("v3")

PROMPT_V2 = """You are restructuring a scanned Arabic journal article (it may contain French or English) into a clean,
faithful digital edition. A trusted OCR engine (Azure) has already read every page; its lines are listed below, page
by page. Each row: line id "P:N" (P = page number in the article, N = Azure's line number on that page), the line's
box [x0,y0,x1,y1] in 0-1000 coordinates of its page (x from the LEFT edge, y from the top), then the text exactly as
Azure read it. Azure's order is not always the reading order.
{images_note}
{context}
AZURE'S LINES:
{lines}

YOUR JOB: give the structure of pages {first}-{last}, built ONLY from these line ids. Azure's text IS the text of the
edition; you never retype it. Return one JSON object:

{{
 "metadata": {metadata_spec},
 "pages": [ {{"page": {first}, "blocks": [ ... in true reading order ... ]}}, ... one entry per page {first}..{last} ],
 "splits": [ {{"line": "3:12", "parts": ["first part", "second part"]}} ],
 "noise": ["3:40"],
 "ornaments": [ {{"line": "3:4", "word": 6, "text": "٥"}} ],
 "fixes": [ {{"line": "3:7", "from": "exact substring of Azure's text", "to": "what the ink shows", "why": "short"}} ],
 "sic": [ {{"line": "3:9", "text": "exact printed substring", "corr": "the intended word", "why": "short"}} ],
 "math": [ {{"line": "3:9", "from": "exact substring of Azure's text", "latex": "LaTeX of that formula"}} ],
 "missed": [ {{"after": "3:15", "type": "paragraph", "text": "printed text that no Azure line covers"}} ]
}}

BLOCKS. Each block: {{"type": T, "lines": ["3:1", "3:2", ...]}} with its lines in reading order. Reading order is the
right-hand column before the left-hand column for Arabic, top to bottom; page furniture first or last as printed. T:
  title                 the article's main title (once in the article)
  heading               a section heading; add "level": 2 for main sections, 3 for sub-sections, 4 below that.
                        Headings that look the same in print get the same level throughout the article.
  byline                author names, affiliations, dates and places under the title or signed at the end
  abstract, keywords    an abstract paragraph / a keywords line (any language)
  paragraph             body text; one block per printed paragraph (a new block where a paragraph starts)
  list_item             one item of a numbered or bulleted list; add "list": "ol" or "ul" (see LISTS below)
  reference             one entry of a bibliography / reference list (sources, without call numbers in the text)
  footnote              one note printed at the FOOT OF THE PAGE that calls it, under the page's text (often below
                        a short rule, in smaller type); add "marker": the marker as printed (e.g. "(1)", "*") and
                        "id": "fn-P-M" (P = the page the footnote is printed on, M = the marker's digits or symbol)
  endnote               v2: one note of a run of notes GATHERED AT THE END of the article (or of a section), under
                        a heading such as هوامش، الهوامش، الحواشي، الإحالات، الهوامش والمراجع، المراجع والهوامش،
                        Notes, Références; numbered to match calls in the text. Add "marker" as printed and
                        "id": "en-M" (M = its number; if the numbering restarts per section: "en-S-M", S = the
                        section's number). The heading above the run is a heading block. A run of sources with no
                        call numbers in the text is reference entries, not endnotes.
  verse                 one line of poetry: instead of "lines" give "hemistichs": [["3:10"], ["3:11"]], the right
                        half-line first. Free verse: one verse block per printed line with a single hemistich.
                        v2: when ONE Azure line holds both halves (two groups of words with a wide gap between
                        them, often with an ornament such as ٥ ه * « » = between), do NOT use "splits": add
                        "cut": {{"3:4": K}} to the verse block, meaning the first K words of Azure's text of that line
                        (words = the text split at spaces, counted from 1, in the order Azure wrote them) are the
                        right half and the rest the left half; then write "hemistichs": [["3:4a"], ["3:4b"]].
  quote                 a Quran verse or quotation set apart from the paragraph
  table                 instead of "lines" give "rows": [[{{"lines": ["3:20"], "th": true, "colspan": 1, "rowspan": 1}},
                        ...], ...]; cells in printed order (right to left for an Arabic table); an empty cell is
                        {{"lines": []}}; the caption is its own "caption" block. v2: column headings and unit words
                        printed above the columns (e.g. مليم جنيه, %, km) are header cells of the table, never a
                        paragraph.
  equation              a displayed formula: "lines" (Azure's garbled text of it) plus "latex"
  caption               the caption of a table or figure
  figure                a picture, chart or drawing: "box": [x0,y0,x1,y1] on its page (0-1000), "lines": any
                        text printed inside it, "description": a few words saying what it shows
  header, footer        running head, page number, journal name, issue line: page furniture
  other_article         v2: text of a DIFFERENT article printed on a page this article shares: the end of the
                        previous article above this article's title (or above a "بقية ص ..." / "continued from"
                        jump), or the start of the next article after this one ends. Recognise the boundary by:
                        a new title, author line or heading style that starts the other piece; a closing signature
                        (an author's name, a place and date), an end mark or a rule between the two; a change of
                        topic at that point; and the position (top of the article's first page or of a page it
                        jumps to, bottom of its last page). Give it ordinary "lines" in reading order, one block per
                        printed paragraph; it is kept out of this article's text. Its running heads stay
                        header/footer. Never call it noise.
  other                 anything else that is printed text of this article
Optional on any block: "lang": "ar" | "fr" | "en".
LISTS (v2): list_item only for a run of SHORT PARALLEL items, each opening with a number, letter or bullet
(١- ، (أ) ، - ، • , 1), a)) and usually one to three lines long, often indented or with a hanging number: steps,
objectives, enumerated points, a table of contents. A block of running prose that merely OPENS with a number or an
ordinal (أولاً: ، ثانياً: ، 1- ...) and goes on for several lines in the body's indentation is a paragraph (one numbered
step of the argument); if the number and a few words stand on their own line as the title of what follows, that line
is a heading. In doubt for an item longer than three lines: paragraph. Decide once per article and keep it.
FOOTNOTE AND ENDNOTE CALLS: on EVERY block of any type (paragraph, verse, list item, table, quote, heading, even a
note) whose text holds note call markers, list each one: "calls": [{{"line": "3:5", "marker": "(1)", "fn": "fn-3-1"}}]
(marker exactly as it appears in Azure's line text, after your fix if you fixed it; "fn" = the id of the footnote or
endnote it points to: "fn-..." or "en-..."). Every footnote and endnote should be called from somewhere.
PAGE BREAKS: when a block (paragraph, list item, footnote, endnote, table, verse group, quote, other_article)
continues from the previous page, give its first block on the new page "continued": true. A table whose header row is
repeated on the new page keeps that row (it is printed).

RULES
- Use EVERY line id of pages {first}-{last} exactly once across all blocks (a line in "noise" is not used): never drop
  a line, never repeat one.
- v2: "noise" is ONLY for marks that hold no words: ornaments and rules read as letters, stray marks, scanner specks,
  show-through from the other side of the paper. A line with words is NEVER noise: text of another article is
  other_article, running heads and page numbers are header/footer, anything else printed is a block (other if
  nothing fits). Answers that call a line with words noise are corrected by code and counted against the answer.
- "splits" only when one Azure line holds text of two different blocks (two columns run together, a heading glued to
  a paragraph, a table row read as one line). The parts must be Azure's text cut into pieces, unchanged; then use
  "3:12a", "3:12b", ... instead of "3:12". Both halves of a verse in one line: use the verse block's "cut" instead.
- v2: "ornaments": a decorative mark that Azure read as a word of a line (٥ or ه or * between the halves of a verse,
  a flower, a dash ornament, ※) is not text: list it with the line id, its word number in Azure's text of that line
  (counted from 1, as for "cut") and the word itself. It leaves the edition's text; its ink is kept. A footnote call
  marker, a verse number or punctuation that belongs to the sentence is NOT an ornament.
- FIXES ARE FOR AZURE'S MISREADINGS ONLY. This edition is a faithful transcription, not a corrected one: a fix must
  restore what the INK shows, letter by letter, where Azure's letters are not the printed letters (a dot missed or
  invented, a letter shape mistaken for another, a digit misread, a word cut short, a printed vowel mark lost, a
  footnote marker read as a symbol) and you can see it plainly. "from" must be an exact substring of that line.
  Never correct the author's or printer's spelling, typos, grammar, missing hamza, alif maqsura vs ya, ta marbuta vs
  ha, old or Quranic orthography, names, dialect, word spacing or punctuation. Most pages need no fix at all.
- v2: BEFORE EVERY FIX ask: "does the INK show exactly the letters of 'to'?" If the printed word itself is wrong (the
  printer dropped, doubled or swapped a letter), the ink does NOT show 'to': that is not a fix, it is a "sic" flag,
  and the text keeps the printed word. Never repair the print silently. Three cases from earlier runs:
    * Azure "المتعمون", the ink shows المتعمون (the printer dropped the lam): NO fix. sic: {{"text": "المتعمون",
      "corr": "المتعلمون"}}. (An earlier answer "fixed" it to المتعلمون: wrong, the edition must show the print.)
    * Azure "أصلبا", the ink shows أصلها (Azure took the ه for a ب): a FIX {{"from": "أصلبا", "to": "أصلها"}}; no sic,
      the print is right.
    * Azure "A930", the ink shows ٨930 (the printer set an Arabic eight for the 1 of 1930): a FIX to what the ink
      shows, {{"from": "A930", "to": "٨930"}}, AND a sic flag {{"text": "٨930", "corr": "1930"}}. Writing "1930" as
      the fix would correct the printer: wrong.
- "sic" is for a MISPRINT IN THE PRINT ITSELF, where Azure read the ink correctly (or you fixed Azure's reading to
  the ink) but the printed word is plainly a printer's error (a letter dropped or doubled, two words run together by
  mistake). The text stays as printed; you only propose the intended reading in "corr". Old spelling, Quranic
  orthography, missing hamzas, ى for ي, ه for ة, names, grammar and dialect are NOT misprints. Use it rarely, only
  when certain.
- "math": formulas Azure turned into garbage inside a running line (displayed formulas are equation blocks).
- "missed": only printed text of the article that no Azure line covers; v2: never for a running head or page number.
- Return only the JSON object."""

META_FULL_V2 = """{{"title": "...", "subtitle": "...", "authors": [{{"name": "...", "role": "...", "affiliation": "...",
   "email": "..."}}],
   "abstract": {{"ar": ["1:20", "1:21"], "en": ["1:30"]}}, "keywords": {{"ar": "...", "en": "..."}},
   "journal": "...", "volume": "...", "issue": "...", "year": "...", "pages_printed": "45-62", "language": "ar"}}
   (every string copied exactly from Azure's lines, as printed; abstracts as lists of line ids; null for what is not
   printed in these pages; journal, volume, issue, year may come from a running head; v2: "name" is the person's
   name only, a phrase printed with it such as بقلم، تأليف، ضبطها وشرحها، ترجمة، by goes in "role")"""


def make_prompt(a: dict, ci: int, x: int, y: int, state: dict | None) -> tuple[str, list[bytes], int]:
    """Experiment 41's make_prompt with prompt v2 (same images, lines, chunk context)."""
    lines = []
    for p in range(x, y + 1):
        ls, _, _ = ST.page_lines(a, p)
        lines.append(f"=== PAGE {p} ===\n" + ST.line_table(ls))
    ctx_img = x > 1
    imgs = ([ST.send_jpeg(a, 1)] if ctx_img else []) + [ST.send_jpeg(a, p) for p in range(x, y + 1)]
    context = ""
    want_meta = ci == 0
    if want_meta and x > 1:
        ls, _, _ = ST.page_lines(a, 1)
        context += ST.CTX_LINES.format(lines=ST.line_table(ls))
    if state:
        context += ST.STATE.format(first=x, **state)
    p = PROMPTS[PROMPT_VERSION][0].format(images_note=(ST.IMG_CTX if ctx_img else ST.IMG_WHOLE).format(first=x), context=context,
                         lines="\n".join(lines), first=x, last=y,
                         metadata_spec=PROMPTS[PROMPT_VERSION][1] if want_meta else ST.META_NONE)
    return p, imgs, len(imgs)


def prompt_text_only(a: dict, ci: int, x: int, y: int, state: dict | None) -> str:
    """The prompt without rendering images (for the dry run's token estimate)."""
    lines = []
    for p in range(x, y + 1):
        ls, _, _ = ST.page_lines(a, p)
        lines.append(f"=== PAGE {p} ===\n" + ST.line_table(ls))
    context = ""
    if ci == 0 and x > 1:
        ls, _, _ = ST.page_lines(a, 1)
        context += ST.CTX_LINES.format(lines=ST.line_table(ls))
    if state:
        context += ST.STATE.format(first=x, **state)
    return PROMPTS[PROMPT_VERSION][0].format(images_note=(ST.IMG_CTX if x > 1 else ST.IMG_WHOLE).format(first=x), context=context,
                            lines="\n".join(lines), first=x, last=y,
                            metadata_spec=PROMPTS[PROMPT_VERSION][1] if ci == 0 else ST.META_NONE)


# ------------------------------------------------------------------------------------------------ prompt v3
# LIVE since 2026-10-18 (owner's decisions (a)-(c) on the review of the 55, plus the JATS slots: README "Prompt v3 and
# JATS coverage"). Each change is PROMPT_V2 / META_FULL_V2 with one passage replaced, so the diff is exact.
# run43.py --prompt v3 uses it; answers record prompt "v3" and the masters' stamp hashes this text.

V3_CHANGES = [
    # (a) references vs list: owner's rule (2026-10-18)
    ("""  reference             one entry of a bibliography / reference list (sources, without call numbers in the text)
""",
     """  reference             v3: one entry of a section the article presents as ITS SOURCES: the entries under a heading
                        such as المراجع، المصادر، قائمة المراجع، مصادر البحث، Bibliographie, References, Sources (without
                        call numbers in the text), or every entry when the whole article IS a bibliography (a list
                        of works on a subject compiled for the reader). An author's list of his or her own works,
                        or works listed inside the body as part of what the article says, are list_item, not
                        reference. One decision per article.
"""),
    # (b) a printed translated title is the title in another language, not "other"
    ("""  title                 the article's main title (once in the article)
""",
     """  title                 the article's main title (once in the article). v3: the same title printed in another
                        language (often English under an Arabic title, or above an English abstract) is a title
                        block too, with "lang" and "translated": true; never other, never a heading
"""),
    # (c) figure descriptions in Arabic and English (owner: "store it in both English and Arabic if possible")
    ("""                        text printed inside it, "description": a few words saying what it shows
""",
     """                        text printed inside it, "description": a few words saying what it shows, v3: in BOTH
                        Arabic and English, {{"ar": "...", "en": "..."}} (the same description in each language)
"""),
    # boxed text: pull-quotes, highlighted facts, sidebars (JATS boxed-text)
    ("""  other                 anything else that is printed text of this article
""",
     """  boxed                 v3: text of this article printed inside a frame or a tinted box set apart from the running
                        text: a pull-quote, a highlighted fact or number, a sidebar, a boxed definition. Ordinary
                        "lines", one block per printed paragraph; the blocks of one box get the same "box": K
                        (1, 2, ... on each page). Words printed inside a picture are the figure's lines, not boxed;
                        another article's text in a frame is other_article.
  other                 anything else that is printed text of this article
"""),
    # quotations: set apart = quote, consistently
    ("""  quote                 a Quran verse or quotation set apart from the paragraph
""",
     """  quote                 a Quran verse or quotation set apart from the paragraph. v3: every Quran verse or
                        quotation printed on its own line(s) (centred, indented, in other type, or a verse between
                        ﴿ ﴾ standing alone) is a quote block, one per printed quotation; a short quotation inside a
                        running sentence stays in its paragraph
"""),
]

META_V3_CHANGES = [
    # (b) translated titles; affiliations split as printed; history dates
    ("""   "journal": "...",""",
     """   "trans_titles": [{{"lang": "en", "title": "..."}}],
   "history": [{{"type": "received", "text": "...", "line": "1:9"}}], "journal": "...","""),
    ("""   "email": "..."}}],""",
     """   "email": "...", "aff_parts": {{"department": "...", "institution": "...", "city": "...", "country": "..."}}}}],"""),
    ("""   printed in these pages; journal, volume, issue, year may come from a running head;""",
     """   printed in these pages; journal, volume, issue, year may come from a running head; v3: "trans_titles" = the
   article's title as printed in another language; "history" = dates printed about the article's own submission and
   publication (تاريخ الاستلام / الإرسال، تاريخ التعديل، تاريخ القبول، تاريخ النشر، Received, Revised, Accepted,
   Published), type one of received, revised, accepted, published, online, text = the date exactly as printed, line =
   its line id; "aff_parts" = the parts of that author's printed affiliation, each an exact substring of it, null for a
   part not printed;"""),
]


def _apply(text: str, changes) -> str:
    for old, new in changes:
        assert text.count(old) == 1, old[:60]
        text = text.replace(old, new)
    return text


PROMPT_V3 = _apply(PROMPT_V2, V3_CHANGES)
META_FULL_V3 = _apply(META_FULL_V2, META_V3_CHANGES)

# ------------------------------------------------------------------------------------------------ prompt v3.1
# 2026-10-18 (owner): v3 lost pictures v2 drew (1769 pp3-5 hieroglyph strips left as quote text, 0493 p1's cartoon).
# One passage of v3 extended: symbols, hieroglyphs, logos, stamps, cartoons and decorative pictures are figures, and
# Azure's junk reading of them is the figure's (or, inside a line of text, an ornament with "picture": true).
V31_CHANGES = [
    ("""                        Arabic and English, {{"ar": "...", "en": "..."}} (the same description in each language)
""",
     """                        Arabic and English, {{"ar": "...", "en": "..."}} (the same description in each language).
                        v3.1: symbols, hieroglyphs, logos, stamps, cartoons and decorative pictures are figures too,
                        even small ones; what Azure read from them ("FORM", "DoC", "=10", digit soup) is not text:
                        put those lines in the figure's "lines", never in body text; such junk inside a line of real
                        text goes in "ornaments" with "picture": true
"""),
]
PROMPT_V31 = _apply(PROMPT_V3, V31_CHANGES)

# ------------------------------------------------------------------------------------------------ prompt v3.2
# CANDIDATE, NOT LIVE (2026-10-18; no calls made with it). v3.1 plus three passages:
#  (i)   the fix passage: the print's dotted ي and its hamzas are fixed where Azure lost them (owner-approved after
#        1769: v2 made 12 such fixes, v3 / v3.1 none); dots or hamzas the print lacks are never added;
#  (ii)  structured references: each reference entry returns its parts ("parsed"), each an exact substring;
#  (iii) citations in footnotes / endnotes: each note that cites works returns the same parts per work ("cites").
# Masters: refs43.add_parsed (element-citation beside the printed mixed-citation; in a note, a p
# content-type="parsed-citations" after its text). run43.py --prompt v3.2 would select it; the default stays v2.
V32_CHANGES = [
    # (i) ي / hamza as printed
    ("""  ha, old or Quranic orthography, names, dialect, word spacing or punctuation. Most pages need no fix at all.
""",
     """  ha, old or Quranic orthography, names, dialect, word spacing or punctuation. Most pages need no fix at all.
  v3.2: if the ink shows ي (dotted) or a hamza and Azure read ى or no hamza, fix it to what is printed; never add
  dots or hamzas the print lacks.
"""),
    # (ii) + (iii) parsed references and the works a note cites
    ("""FOOTNOTE AND ENDNOTE CALLS: on EVERY block""",
     """PARSED REFERENCES (v3.2): every reference block adds "parsed": [W] (usually one work), and every footnote or
endnote that cites works (a book, an article, a manuscript, a web page) adds "cites": [W, W, ...], one W per work
it cites, in the order printed (a note that only comments cites nothing: no "cites"). W = {{"type": "book" |
"journal" | "chapter" | "thesis" | "web" | "other", "authors": [{{"surname": "...", "given": "..."}}], "year": "...",
"title": "...", "source": "...", "volume": "...", "issue": "...", "pages": "...", "publisher": "...", "place": "...",
"doi": "...", "url": "...", "lang": "ar" | "fr" | "en"}}: "source" = the journal, or the book a chapter is in;
"title" = the work's own title; every value an EXACT substring of that block's text as printed (after your fixes),
never translated, completed or normalised: a Hijri year, «د.ت» or «د.ن» stays as printed; an author printed as one
string («ابن خلدون») goes whole in "surname"; null (or leave out) what the entry does not print; «المرجع السابق»,
«نفسه», «op. cit.», «ibid.» cite nothing new: no W for them.
FOOTNOTE AND ENDNOTE CALLS: on EVERY block"""),
]
PROMPT_V32 = _apply(PROMPT_V31, V32_CHANGES)
META_FULL_V32 = META_FULL_V3                    # the metadata spec is unchanged

# ------------------------------------------------------------------------------------------------ prompt v3.3
# 2026-10-19 (owner, after the v3.2 test's hand check of 111 works): v3.2 plus one line in the citations passage — a
# book series is not the source (6 of 11 wrong fields were كتاب الهلال، اقرأ … as "source"), and empty fields are left
# out (0747's answer wrote every empty field as null: tokens for nothing). W gains "series" (JATS <series>).
V33_CHANGES = [
    ('''"publisher": "...", "place": "...",''', '''"publisher": "...", "place": "...", "series": "...",'''),
    ('''string («ابن خلدون») goes whole in "surname"; null (or leave out) what the entry does not print;''',
     '''string («ابن خلدون») goes whole in "surname"; leave out what the entry does not print;'''),
    ('''«نفسه», «op. cit.», «ibid.» cite nothing new: no W for them.
''',
     '''«نفسه», «op. cit.», «ibid.» cite nothing new: no W for them.
v3.3: a book series (e.g. كتاب الهلال، سلسلة اقرأ) is not the source/journal — put it in a "series" field if present;
leave out fields that are empty instead of writing null.
'''),
]
PROMPT_V33 = _apply(PROMPT_V32, V33_CHANGES)

# ------------------------------------------------------------------------------------------------ prompt v3.4 (candidate)
# 2026-10-20, after the 300 (README "Fixes from the 300"): CANDIDATE ONLY, not live (run43.py --prompt v3.4 would
# select it; nothing has been sent with it). (a) inline formulas inside an Arabic sentence as LaTeX (0168 p5:
# «μT = max ||x||» left as Azure's «tostST- max»); (b) letters Azure drops in fully vowelled lines (1875 p17
# «الزَّاد» -> «الْادُ»; rules43.vowelled_words flags them, it cannot restore them); (c) compact JSON (1764 pp9-15: 531
# one-line table cells pretty-printed ran into the 27,000-token output limit twice).
V34_CHANGES = [
    ("""- "math": formulas Azure turned into garbage inside a running line (displayed formulas are equation blocks).
""",
     """- "math": formulas Azure turned into garbage inside a running line (displayed formulas are equation blocks).
  v3.4: this includes a short formula inside an ARABIC sentence (e.g. «μT = max ||x|| بحيث أن»): Azure reads it as
  Latin junk («tostST- max») and may move it within the line; "from" = that junk exactly as in Azure's text, "latex" =
  the formula as printed. Never leave such junk in the text.
"""),
    ("""  dots or hamzas the print lacks.
""",
     """  dots or hamzas the print lacks.
  v3.4: in FULLY VOWELLED lines (verse, Quran, hadith) Azure often drops a letter together with its marks («الزَّاد»
  read «الْادُ», «الْكَرِيمِ» read «الْكَرِ»): check every word of such lines against the ink, letter by letter, and
  restore what is printed with a fix.
"""),
    ("""- Return only the JSON object.""",
     """- Return only the JSON object, compact (v3.4: no indentation or line breaks inside it; a long table of short cells
  must still fit)."""),
]
PROMPT_V34 = _apply(PROMPT_V33, V34_CHANGES)
PROMPTS = {"v2": (PROMPT_V2, META_FULL_V2), "v3": (PROMPT_V3, META_FULL_V3), "v3.1": (PROMPT_V31, META_FULL_V3),
           "v3.2": (PROMPT_V32, META_FULL_V32), "v3.3": (PROMPT_V33, META_FULL_V32),
           "v3.4": (PROMPT_V34, META_FULL_V32)}
# the names the earlier README section used for the (then not live) draft of (a)-(c)
PROMPT_V3_CANDIDATE, META_FULL_V3_CANDIDATE = PROMPT_V3, META_FULL_V3


def use(version: str):
    """Make `version` the prompt make_prompt / prompt_text_only send (run43.py --prompt)."""
    global PROMPT_VERSION
    if version not in PROMPTS:
        raise SystemExit(f"unknown prompt {version}: {sorted(PROMPTS)}")
    PROMPT_VERSION = version
