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
                         metadata_spec=PROMPTS[PROMPT_VERSION][1] if want_meta else ST.META_NONE,
                         enrich_spec=enrich_spec(want_meta))
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
                            metadata_spec=PROMPTS[PROMPT_VERSION][1] if ci == 0 else ST.META_NONE,
                            enrich_spec=enrich_spec(ci == 0))


def enrich_spec(first: bool) -> str:
    """v3.5's "enrich" outline for this chunk ("" for versions without it: their text has no {enrich_spec}, and
    str.format ignores the unused value, so their prompts are unchanged)."""
    e = ENRICH.get(PROMPT_VERSION)
    return (e[0] if first else e[1]) if e else ""


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

# ------------------------------------------------------------------------------------------------ prompt v3.5 (draft)
# 2026-10-22: DRAFT, not live, nothing sent with it (README "Prompt v3.5 (draft, 2026-10-22)"). v3.3 + the 37
# "add to the prompt first" items of experiment 51 (inventory.json prompt_priority 1; owner: "add all 37").
# Built against v3.4's two repeat losses (an advert shredded, paragraphs merged; README "Final first 300 and the exam
# config"): every structural passage of v3.3 is left word for word; the new fields go in their own top-level part of
# the answer, "enrich", described in its own section and written LAST; the only additions inside v3.3's passages
# are (a) v3.4's two content lines, verbatim (the owner's 37 include them), (b) one fix line for honorific ligatures
# and (c) new optional keys of a cited work W in the citations passage (W is not structure). v3.4's "compact JSON"
# line is NOT included. Gemini still never retypes text (D30): every new value is a line id, a word from a closed
# list, or an exact substring of Azure's text, checked in code (rules43.enrich_check, enrich43, refs43, meta43).
# The 37 items, by inventory id (each marked in the text below where it is asked):
#   document type x061 x062 x070 x224 · about the article x003 x063 x064 x066 x067 x068 · authors x024 x026 x028 x029
#   x034 x039 x040 · cited works x117 x118 x119 x120 x121 x127 x133 x135 x136 x137 · table / figure notes x111 x112
#   · note kinds x110 · picture kind x158 · stamps x213 · handwriting x214 · scan problems x216 · honorific glyphs
#   x176 · v3.4's content lines x164 (inline formulas) x178 (letters lost in vowelled lines)
V35_CHANGES = [
    # the answer's shape: one more top-level key, last
    (''' "missed": [ {{"after": "3:15", "type": "paragraph", "text": "printed text that no Azure line covers"}} ]
}}
''',
     ''' "missed": [ {{"after": "3:15", "type": "paragraph", "text": "printed text that no Azure line covers"}} ],
 "enrich": {enrich_spec}
}}
'''),
    # cited works: new optional keys of W (x117-x121, x127, x133, x135-x137)
    ('''leave out fields that are empty instead of writing null.
''',
     '''leave out fields that are empty instead of writing null.
v3.5: W may also hold, each only when printed and each an EXACT substring as above: "editors" and "translators"
(persons like "authors": the editor of the text after تحقيق / تح / ضبط / ed., the translator after ترجمة / tr.);
"died" inside a person (a classical author's death date printed with the name: "٧٥١هـ" from «(ت ٧٥١هـ)»);
"edition" («ط٢»، «الطبعة الثالثة»، «2nd ed.»); "cal": "hijri" when "year" is a Hijri year, and "year2" = a second year
printed for the same work in the other calendar («١٤٠٤هـ - ١٩٨٤م»: "year": "١٩٨٤م", "year2": "١٤٠٤هـ"); "cited" =
the page(s) the entry or note points the reader to («ص ٤٥»، «ص ٤٠-٤١»، «p. 12»), "pages" is then only the work's own
page range (an article's or a chapter's first-last pages); "accessed" = the date a web source was consulted (تاريخ
الزيارة، Retrieved, consulté le); type "manuscript" with "library" (the library or collection holding it), "shelf"
(its shelfmark or number) and "folio" (the leaves cited, e.g. «179/ب - 180/أ»); type "conference" with "conf" (the
conference's name; its place in "place"); a thesis adds "degree" (رسالة دكتوراه، ماجستير، PhD), its university in
"publisher".
'''),
    # v3.4's two content lines, verbatim (x164, x178)
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
  v3.5: an honorific printed as ONE ligature glyph (ﷺ ﷻ ﷲ ﷽) that Azure dropped, split or read as junk letters is
  fixed to that single character (ﷺ U+FDFA, ﷻ U+FDFB, ﷲ U+FDF2, ﷽ U+FDFD), never spelt out as words; if Azure left
  nothing, "from" is the text round the gap («الكريم ()» -> «الكريم (ﷺ)»). An honorific printed in words stays so.
"""),
    # the enrichment section, after every structural rule and before the last line
    ("""- Return only the JSON object.""",
     """ENRICHMENT (v3.5). "enrich" is a SEPARATE part of the answer, written LAST. It changes nothing above: decide every
block, type, order, split, fix and note exactly as you would without it. Every value in it is a line id, a word from
the lists below, or an EXACT substring of Azure's text (after your fixes), as "aff_parts" are; never retype, complete
or translate. Leave out every key that does not apply ("enrich": {{}} when nothing does).
  doc_type      what the piece is: research, review (a survey of earlier studies), editorial, book_review, report,
                conference_paper, thesis_summary, interview, news, letter, obituary, poem, documents (texts or
                records presented), bibliography, front_matter (an issue's contents, editorial board, instructions to
                authors), other
  conference    a paper read at a conference: its name, place and dates as printed (such a line under the title is
                this, not a subtitle)
  thesis        a thesis summary: the degree (ماجستير، دكتوراه), university, year and supervisor as printed
  reviewed      a book review: the reviewed book as one W (PARSED REFERENCES)
  original      a translated article: the original's title, author and source as printed, and its language
  part          one article of a series: "n" = the part as printed («(٤)»، «الحلقة الثانية»), "of" = the series' title
                if printed apart from it
  authors       only authors with one of these; "a" = the author's number in metadata "authors" (1 = the first).
                "corresp": true = the print marks this author as the corresponding author (Corresponding author,
                الباحث المراسل). "orcid", "ids" ({{"scopus" | "researcherid" | "scholar": "..."}}) as printed.
                "same_as": K = this entry is author K printed in another script (an English byline of an Arabic
                name; both stay in metadata "authors"). "affs" = when the author has more than one affiliation
                (often matched by superscript numbers) or a faculty / college printed apart from the department:
                every affiliation of that author, in order, its parts as in "aff_parts" plus "faculty" (كلية،
                Faculty, College). "note" = the line ids of a starred or numbered note about the author (post,
                affiliation, address) printed at the foot of the page; it stays a footnote block above
  figures       for EVERY figure block, by page, its kind, in the order of that page's figure blocks: chart, photo,
                map, diagram, drawing, manuscript (a facsimile of a manuscript or document), portrait, logo, stamp,
                cartoon, calligraphy, table_image, ornament, advert, other
  table_notes   lines printed under a table or figure that belong to it: notes (* p < 0.05، ملاحظة) and source lines
                («المصدر:»، Source:). "of" = a line id of that table (a cell) or of its caption ("f4.1" = page 4's
                first figure when it has neither), "lines" = the note's lines (they stay in their block above),
                "kind": "note" | "source"
  note_kinds    footnotes and endnotes NOT by the author, by their id: "translator" (المترجم، (م)), "editor" (المحقق،
                المحرر), "publisher" (the journal's or the editors' note)
  marks         lines that are not the print, wherever they are above: "handwriting" (readers' notes, marginalia,
                signatures in ink), "stamp" (library stamps, ownership marks, call numbers)
  scan          problems of the scan, by page, only when plain: cut_edge (text cut off at an edge), blur, faint, dark,
                skew, torn, missing_page (a page is missing before this one), duplicate_page, out_of_order
- Return only the JSON object."""),
]
PROMPT_V35 = _apply(PROMPT_V33, V35_CHANGES)

# ------------------------------------------------------------------------------------------------ prompt v3.5b (draft)
# 2026-10-22, after the v3.5 check (out/v35_check/score.md): v3.5's new fields were good, but the structure moved
# beyond v3.3's own run-to-run noise on some pages (gold 2382 31 differences vs 17; 0500 figures/captions read as
# paragraphs; 0787 footers as footnotes; 1010-006's advert split again). The only content change inside v3.3's
# structural passages was v3.4's two content lines (the cause of v3.4's losses before), so v3.5b = v3.5 WITHOUT them:
# v3.3's structural text word for word, plus the honorific-ligature line (one of the owner's 37), the new optional keys
# of a cited work, and the enrichment section. The owner chose this over a second enrichment call per article (+47% a
# page). Nothing else differs from v3.5.
_V34_MATH = V35_CHANGES[2]
_V34_VOWELS_AND_HONORIFIC = V35_CHANGES[3]
assert "v3.4: this includes a short formula" in _V34_MATH[1]
assert "FULLY VOWELLED" in _V34_VOWELS_AND_HONORIFIC[1] and "honorific printed as ONE ligature" in _V34_VOWELS_AND_HONORIFIC[1]
_HONORIFIC_ONLY = (_V34_VOWELS_AND_HONORIFIC[0], _V34_VOWELS_AND_HONORIFIC[0] + _V34_VOWELS_AND_HONORIFIC[1][
    _V34_VOWELS_AND_HONORIFIC[1].index("  v3.5: an honorific"):])
V35B_CHANGES = [c for c in V35_CHANGES if c is not _V34_MATH and c is not _V34_VOWELS_AND_HONORIFIC]
V35B_CHANGES.insert(2, _HONORIFIC_ONLY)
PROMPT_V35B = _apply(PROMPT_V33, V35B_CHANGES)
assert "v3.4:" not in PROMPT_V35B and "honorific printed as ONE ligature" in PROMPT_V35B
# the "enrich" shape shown in the answer's outline (a value, so single braces): with the metadata (first chunk) the
# article's keys too; on later chunks only the page keys
ENRICH_FULL_V35 = """{"doc_type": "research", "conference": {"name": "...", "place": "...", "date": "..."},
   "thesis": {"degree": "...", "university": "...", "year": "...", "supervisor": "..."}, "reviewed": W,
   "original": {"title": "...", "author": "...", "source": "...", "lang": "en"}, "part": {"n": "...", "of": "..."},
   "authors": [{"a": 1, "corresp": true, "orcid": "...", "ids": {"scopus": "..."}, "same_as": 2,
     "affs": [{"department": "...", "faculty": "...", "institution": "...", "city": "...", "country": "..."}],
     "note": ["1:40"]}],
   "figures": {"3": ["chart", "photo"]}, "table_notes": [{"of": "4:12", "lines": ["4:30"], "kind": "source"}],
   "note_kinds": {"fn-3-2": "translator"}, "marks": {"handwriting": ["2:40"], "stamp": ["1:2"]},
   "scan": {"3": ["cut_edge"]}}"""
ENRICH_PAGES_V35 = """{"figures": {"3": ["chart", "photo"]}, "table_notes": [{"of": "4:12", "lines": ["4:30"],
   "kind": "source"}], "note_kinds": {"fn-3-2": "translator"}, "marks": {"handwriting": ["2:40"]},
   "scan": {"3": ["cut_edge"]}}   (the article's keys are given with its first pages only)"""

# ------------------------------------------------------------------------------------------------ prompt v3.6 (draft)
# 2026-11-02, experiment 65 (experiment 61's "nothing lost" audit, P1-P3): v3.5b word for word, plus
#   P1  metadata authors[].position: the author's post / rank as its own exact substring (Gemini put it in "role" or
#       inside "affiliation"; the masters dropped it, M1);
#   P2  enrich "doi" (the article's own DOI, not one inside its references), "license" (the licence / copyright /
#       open-access lines) and "section" (the journal's section or rubric printed over the title) - code catches the
#       plain cases (leaks43); these are for what it cannot tell apart;
#   P3  enrich "printings", on ANY chunk: every other printing of an author (an English byline on the summary page at
#       the end, a byline repeated on page 2, a closing signature, an author note) with its lines, ORCID, e-mail, post
#       and the corresponding-author mark (0130-027-105-003 lost three ORCIDs on its last pages under v3.5b).
# Nothing inside v3.3's structural passages changes; the new keys go in the metadata outline and the ENRICHMENT
# section, as v3.5's did. The answer schema is v3.5b's plus these keys (enrich43.KNOWN, test_leaks43).
META_V36_CHANGES = [
    ("""{{"name": "...", "role": "...", "affiliation": "...",""",
     """{{"name": "...", "role": "...", "position": "...", "affiliation": "...","""),
    ("""   name only, a phrase printed with it such as بقلم، تأليف، ضبطها وشرحها، ترجمة، by goes in "role")""",
     """   name only, a phrase printed with it such as بقلم، تأليف، ضبطها وشرحها، ترجمة، by goes in "role"; v3.6:
   "position" = the author's post or rank as printed («أستاذ مساعد»، «طالبة باحثة في علم الاجتماع»، "PhD Student",
   "Professor of Psychology"), an exact substring, never in "role"; when the post is printed in the same line as
   the affiliation it is still "position", and "affiliation" begins after it)"""),
]
META_FULL_V36 = _apply(META_FULL_V32, META_V36_CHANGES)
V36_CHANGES = [
    ("""  figures       for EVERY figure block, by page, its kind,""",
     """  doi           the article's OWN DOI as printed (on its first page, its running head or foot, its "how to cite"
                line or its summary page; never one inside the references or notes), an exact substring
                ("10.29343/1-79-2" from «Doi: 10.29343/1-79-2»)
  license       the line ids of the licence / copyright / open-access statement (Creative Commons, ©, جميع الحقوق
                محفوظة، رخصة المشاع الإبداعي)
  section       the line id(s) of the journal's section or rubric printed over the title (المقالات، البحوث
                والدراسات، Research Papers, Book Reviews); not a running head that names the journal
  printings     on ANY pages: every OTHER printing of an author away from the first byline - an English byline on
                a summary page at the end, a byline repeated on page 2, a closing signature, a note about the
                author. One entry per author per printing: "a" = the author's number in metadata "authors" (on
                later pages: the K-th author of the article's first byline, seen in Image 1), "name" = the name
                exactly as printed THERE, "lines" = that printing's line ids, and, when printed there, "orcid",
                "email", "position" (post or rank) and "corresp": true (the corresponding-author mark). Leave out
                the first byline itself.
  figures       for EVERY figure block, by page, its kind,"""),
    ("""ENRICHMENT (v3.5). "enrich" is a SEPARATE part""", """ENRICHMENT (v3.6). "enrich" is a SEPARATE part"""),
    # (a fix-rule bullet from experiment 66 was tried here and DROPPED on 2026-11-02: experiment 69 found it changed
    # nothing measurable in Argon's fixes; the code guard d30guard43 is what catches bad fixes)
]
PROMPT_V36 = _apply(PROMPT_V35B, V36_CHANGES)
assert PROMPT_V36.count("printings") == 1 and "v3.4:" not in PROMPT_V36
_PRINTING = """[{"a": 1, "name": "...", "lines": ["25:7", "25:8"], "orcid": "...", "email": "...",
     "position": "...", "corresp": true}]"""
ENRICH_FULL_V36 = ENRICH_FULL_V35.replace(
    '"part": {"n": "...", "of": "..."},',
    '"part": {"n": "...", "of": "..."},\n   "doi": "...", "license": ["1:41", "1:42"], "section": ["1:3"],').replace(
    '   "figures": {"3": ["chart", "photo"]}, "table_notes"',
    '   "printings": ' + _PRINTING + ',\n   "figures": {"3": ["chart", "photo"]}, "table_notes"')
ENRICH_PAGES_V36 = ENRICH_PAGES_V35.replace('{"figures": {"3": ["chart", "photo"]},',
                                            '{"printings": ' + _PRINTING + ', "figures": {"3": ["chart", "photo"]},')
assert '"doi"' in ENRICH_FULL_V36 and "printings" in ENRICH_FULL_V36 and "printings" in ENRICH_PAGES_V36

PROMPTS = {"v2": (PROMPT_V2, META_FULL_V2), "v3": (PROMPT_V3, META_FULL_V3), "v3.1": (PROMPT_V31, META_FULL_V3),
           "v3.2": (PROMPT_V32, META_FULL_V32), "v3.3": (PROMPT_V33, META_FULL_V32),
           "v3.4": (PROMPT_V34, META_FULL_V32), "v3.5": (PROMPT_V35, META_FULL_V32),
           "v3.5b": (PROMPT_V35B, META_FULL_V32), "v3.6": (PROMPT_V36, META_FULL_V36)}
# v3.5's "enrich" outline (first chunk, later chunks); a version without an entry has no {enrich_spec} in its text
ENRICH = {"v3.5": (ENRICH_FULL_V35, ENRICH_PAGES_V35), "v3.5b": (ENRICH_FULL_V35, ENRICH_PAGES_V35),
          "v3.6": (ENRICH_FULL_V36, ENRICH_PAGES_V36)}
# the names the earlier README section used for the (then not live) draft of (a)-(c)
PROMPT_V3_CANDIDATE, META_FULL_V3_CANDIDATE = PROMPT_V3, META_FULL_V3


def use(version: str):
    """Make `version` the prompt make_prompt / prompt_text_only send (run43.py --prompt)."""
    global PROMPT_VERSION
    if version not in PROMPTS:
        raise SystemExit(f"unknown prompt {version}: {sorted(PROMPTS)}")
    PROMPT_VERSION = version
