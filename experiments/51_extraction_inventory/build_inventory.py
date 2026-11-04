"""Experiment 51: the "extract everything" inventory, built from hand-written items and the counts of the 600 masters.

Items are written below by hand (group, field, why, WoS tag, JATS slot, needs A/B, state today, note). Evidence and
examples are resolved from the three count files made by this folder's scripts (no model calls):
  out/master_counts.json   count_masters.py  (regex patterns over the masters' printed blocks + structure counts)
  out/answer_counts.json   count_answers.py  (what the 600 prompt-v3.3 answers hold)
  out/alto_counts.json     count_alto.py     (ALTO roles: furniture, other article, show-through ...)
Placeholders in evidence strings: {m:key} pattern, {s:key} JATS structure, {a:key} answers, {o:key} ALTO
  -> "A articles / N" (A of the 600 articles, N occurrences). Examples: "m:key" (first example of that pattern),
  "m:key#2" (second), "o:key", or a literal (stem, page, text).
Writes inventory.json (this folder).
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = json.load(open(HERE / "out" / "master_counts.json"))
A = json.load(open(HERE / "out" / "answer_counts.json"))
O = json.load(open(HERE / "out" / "alto_counts.json"))


def cnt(kind, key):
    if kind == "m": d = M["patterns"].get(key)
    elif kind == "s": d = M["structure"].get(key, {"articles": 0, "n": 0})
    elif kind == "a": d = A.get(key, {"articles": 0, "n": 0})
    elif kind == "o": d = O.get(key, {"articles": 0, "n": 0})
    if d is None: raise KeyError(kind + ":" + key)
    return d


def fmt(ev):
    import re
    def rep(mo):
        d = cnt(mo.group(1), mo.group(2))
        if not d["articles"]: return "none in the 600"
        return f"{d['articles']} articles / {d['n']}"
    return re.sub(r"\{([msao]):([\w.]+)\}", rep, ev)


def example(ex):
    if ex is None: return None
    if isinstance(ex, tuple):
        stem, page, text = ex
        return {"stem": stem, "page": page, "text": text[:200]}
    kind, key = ex.split(":", 1)
    i = 0
    if "#" in key: key, i = key.split("#"); i = int(i) - 1
    d = cnt(kind, key)
    if kind == "a":
        stem, text = d["example"]
        return {"stem": stem, "page": page_of(stem, text), "text": text[:200]}
    e = d["examples"][i]
    if kind == "o":
        return {"stem": e[0], "page": int(e[1]) if str(e[1]).isdigit() else e[1], "text": e[2][:200]}
    return {"stem": e[0], "page": e[1], "text": e[3][:200], "context": e[2]}


_PAGES = {}


def page_of(stem, text):
    """The page of the first block of the stem's master that holds `text` (an answer's value), else None."""
    import re
    from lxml import etree
    import count_masters as CM
    if stem not in _PAGES:
        f = [x for x in CM.FILES if x.endswith("/" + stem + ".jats.xml")]
        _PAGES[stem] = list(CM.blocks(etree.parse(f[0]))) if f else []
    probe = re.sub(r"\s+", " ", text).strip()[:25]
    for page, ctx, t in _PAGES[stem]:
        if probe and probe in t: return page
    # metadata values live in the front, not in page blocks: look in the ALTO lines (Persian look-alikes folded)
    fold = lambda x: x.replace("ی", "ي").replace("ک", "ك")
    alto = f[0].replace(".jats.xml", ".alto.xml") if (f := [x for x in CM.FILES if x.endswith("/" + stem + ".jats.xml")]) else None
    if alto:
        NS = "{http://www.loc.gov/standards/alto/ns-v4#}"
        words = [w for w in re.split(r"[\s\[\]{}'\":,،]+", text) if len(w) >= 4 and w not in ("lang", "title")]
        for pg in etree.parse(alto).iter(NS + "Page"):
            for tl in pg.iter(NS + "TextLine"):
                tx = fold(" ".join(x.get("CONTENT", "") for x in tl.iter(NS + "String")))
                if words and fold(words[0]) in tx:
                    p = pg.get("PHYSICAL_IMG_NR") or pg.get("ID")
                    return int(p) if str(p).isdigit() else p
    return None


ITEMS = []


def I(group, field, why, wos, jats, needs, today, evidence, ex=None, note=""):
    ITEMS.append(dict(group=group, field=field, why=why, wos_tag=wos, jats=jats, needs=needs, today=today,
                      evidence=evidence, example=ex, note=note))


W, RAG, RD, COR, EXP = "Web-of-Science index", "RAG", "reader", "corrections", "exports"
def why(*xs): return ", ".join(xs)

# ============================================================================================ metadata
g = "metadata"
I(g, "article title as printed (lines, ink)", why(W, RD, EXP), "TI", "article-meta/title-group/article-title", "A", "extracted-well",
  "title block in 594 of 600 answers (blk.title {a:blk.title}); article-title in 600/600 masters", ("1900-003-003,004-006", 1, "في نقد بنائية بياجي"))
I(g, "title corrected (D33) beside the printed form", why(W, COR), "TI", "article-title + alt-title[@alt-title-type=printed]", "B", "extracted-well",
  "meta43.title: cut-off titles from the catalogue, misprint flags; metadata-change log {s:metadata_change}", None,
  "only 3 articles needed a printed alt-title; most changes are page ranges")
I(g, "subtitle", why(W, RD), "TI (part)", "title-group/subtitle", "A", "extracted-partly",
  "answers give a subtitle in {a:meta.subtitle}, masters keep {s:subtitle}; some 'subtitles' are a conference's place and date", "a:meta.subtitle",
  "a conference line printed under the title goes into subtitle: needs its own field (see document-level: conference)")
I(g, "translated title(s) as printed (en, fr)", why(W, RD, EXP), "TI (alt) / Z9", "trans-title-group[@xml:lang]/trans-title", "A", "extracted-well",
  "v3 title block 'translated' {a:bk.translated}; masters trans-title-group {s:trans_title_printed}", ("0069-000-026-005", 3, "The Grammarian's Fallacy about the six nouns"))
I(g, "running title (short title in the running head)", why(RD, EXP), None, "title-group/alt-title[@alt-title-type=running-head]", "B", "kept-as-text-only",
  "page headers are ALTO role.pageHeader {o:role.pageHeader}; no field", "o:role.pageHeader",
  "code can match a header to the title; the rest of the head is journal/issue (see page-furniture)")
I(g, "journal title as printed", why(W, COR), "SO", "journal-meta/journal-title + custom-meta printed-journal", "A", "extracted-well",
  "printed-journal custom-meta {s:printed_journal}; answers meta.journal {a:meta.journal}", "a:meta.journal",
  "experiment 48: generic names (مجلة كلية التربية) need the catalogue's journal code to link")
I(g, "volume", why(W, EXP), "VL", "article-meta/volume", "A", "extracted-well",
  "answers meta.volume {a:meta.volume}; else catalogue 773", "a:meta.volume")
I(g, "issue (incl. joint / special issue)", why(W, EXP), "IS / SI", "article-meta/issue (+ issue-part, @content-type special)", "A", "extracted-partly",
  "answers meta.issue {a:meta.issue}; joint issues kept as printed («3,4»), special issue (عدد خاص) not marked", "a:meta.issue",
  "platform v2 has issues.is_special / is_joint; code can derive from the printed string")
I(g, "year as printed (Gregorian and/or Hijri)", why(W, EXP), "PY", "pub-date/year (+ @calendar)", "A", "extracted-well",
  "answers meta.year {a:meta.year}; printed-date custom-meta {s:printed_date}", "a:meta.year", "the Hijri twin is converted by code (B)")
I(g, "issue date: month / season as printed", why(W, EXP), "PD", "pub-date/month, season, string-date", "A", "extracted-partly",
  "printed-date {s:printed_date} kept as a string; pub-date with day/month only from the history dates", ("0013-002-001-005", 1, "دراسات نفسية ( يناير ١٩٩٢ ك ٢ جـ ١ ص ص ٧٥ - ١٠١ ) [running head; printed date «يناير ١٩٩٢»]"),
  "month names (كانون الثاني, آب, Juillet) are parsed by code: B once the string is kept")
I(g, "page range as printed", why(W, EXP), "BP / EP", "fpage, lpage", "A", "extracted-well",
  "answers pages_printed {a:meta.pages_printed}; checked against the scan's page count (metadata-change)", ("0005-012-004-007", 1, "- ٤١ -  [first page's folio; the answer's pages_printed: ٤١-٤٦]"))
I(g, "article DOI printed on the page", why(W, EXP), "DI", "article-meta/article-id[@pub-id-type=doi]", "B", "kept-as-text-only",
  "DOI text in {m:doi_text}; article-id doi in 0 masters (the catalogue gives 297k DOIs)", "m:doi_text",
  "regex on the first page's text; the printed one should be checked against the catalogue's")
I(g, "ISSN / e-ISSN printed", why(W, EXP), "SN / EI", "journal-meta/issn[@publication-format]", "B", "kept-as-text-only",
  "ISSN text in {m:issn}; journal-meta/issn in 0 masters (catalogue has 906k)", "m:issn", "often inside the journal's banner picture (a figure's text)")
I(g, "ISBN (book-format issues, proceedings)", why(W, EXP), "BN", "isbn", "B", "not-extracted", "ISBN/ردمك in {m:isbn}", None,
  "none in the 600; keep the regex for proceedings and books")
I(g, "publisher as printed (university, society)", why(W, EXP), "PU / PA / PI", "journal-meta/publisher/publisher-name, publisher-loc", "A", "not-extracted",
  "not asked in v3.3; masters journal-meta/publisher {s:publisher_meta}; the catalogue's 260 is used instead",
  ("0168-029-002-020", 1, "© 2020, College of Education for Pure Science, University of Mosul."),
  "deciding that a printed body is the publisher (not the author's employer) is judgment")
I(g, "'how to cite this article' box", why(W, COR), None, "custom-meta (or a kept boxed-text)", "B", "kept-as-text-only",
  "printed in 4 articles (snip «To cite this article|للاستشهاد»)",
  ("0117-043-170-003", 1, "الإشارة المرجعية للبحث/ To cite this article الحنوش، أنوار: \"الحجاج: بين الأسس الأرسطية والمنطلقات الغربية\"، المجلة العربية للعلوم الإنسانية"),
  "the journal's own citation of the article: a free cross-check of title, journal, issue and pages")
I(g, "article language", why(W, RAG, EXP), "LA", "article/@xml:lang", "A", "extracted-well", "answers meta.language {a:meta.language}", None)
I(g, "e-locator / article number", why(W, EXP), "AR", "elocation-id", "B", "not-extracted", "not met in the 600", None,
  "modern online journals print one; regex on the first page")
I(g, "page count", why(W, EXP), None, "counts/page-count", "B", "extracted-well", "600/600 masters", None)
I(g, "printed in which year vs which scan year (reprint, facsimile)", why(W), None, "pub-date[@date-type=reprint]", "A", "not-extracted",
  "not asked; not counted", None, "rare; a reprinted classic article carries two dates")

# ============================================================================================ authors
g = "authors-and-affiliations"
I(g, "author names as printed (string-name, kept whole)", why(W, RD, COR), "AU / AF", "contrib/string-name", "A", "extracted-well",
  "answers authors {a:au.name}; contrib {s:contrib_2plus} articles with 2+ authors", "a:au.name")
I(g, "honorifics and titles kept (د. / أ.د. / الشيخ / Prof.)", why(W, RD), None, "contrib/string-name/prefix (or degrees)", "B", "extracted-partly",
  "kept inside the printed name; meta43.strip_honorific separates them (D35); {m:honorific_title_byline}", "m:honorific_title_byline",
  "platform v2 byline_mentions.titles keeps them; JATS prefix not filled")
I(g, "name parts (ism, nasab, nisba, laqab, kunya; surname / given for Latin)", why(W, COR), "AU (Surname, Initials)", "contrib/name/surname, given-names", "B", "extracted-partly",
  "masters keep string-name only; platform v2 person_names has the parts", None,
  "WoS AU needs 'surname, initials'; code from the authority heading or the printed string")
I(g, "Latin form of an Arabic author's name printed on the page", why(W, COR), "AF", "name-alternatives/name[@xml:lang=en]", "A", "extracted-partly",
  "name-alternatives {s:name_alternatives} (catalogue Latin forms); experiment 48: Latin byline twins doubled as extra authors in 11 articles", ("0069-000-026-005", 3, "Prof. Ibrahim Khalil"),
  "Gemini lists the English byline as another author; one field 'same_as: author N' would stop the doubling")
I(g, "contributor role phrase (بقلم، ترجمة، إشراف، مراجعة، تحقيق)", why(W, RD), None, "contrib/role + @contrib-type", "A", "extracted-partly",
  "answers role {a:au.role}; masters contrib-type translator {s:translator_contrib}, supervisor {s:supervisor_contrib}, reviewer {s:reviewer_contrib}, role {s:role}",
  ("0180-001-002-010", 1, "د. محسن السيد الغرينى ترجمة وتلخيص مدرس بقسم المكتبات والوثائق والمعلومات"),
  "the phrase is captured; mapping to a controlled role is code. محقق (editor-of-text) of a classical text: no example in the 600")
I(g, "corresponding author mark", why(W, EXP), "RP", "contrib/@corresp + author-notes/corresp", "A", "not-extracted",
  "printed in {m:corresponding} (pattern), author-notes / corresp in 0 masters; not asked", "m:corresponding",
  "which of several authors the * or 'Corresponding author' points at is judgment")
I(g, "e-mail per author", why(W, EXP), "EM", "contrib/email", "A", "extracted-well",
  "answers email {a:au.email}; masters contrib/email {s:email_el}; e-mails printed anywhere {m:email}", "a:au.email",
  "the owner's rule: never sent outside; public pages to decide (platform question 10)")
I(g, "ORCID", why(W, EXP), "OI", "contrib/contrib-id[@contrib-id-type=orcid]", "A", "not-extracted",
  "ORCID printed in {m:orcid} (a bare id in a bio note); contrib-id in 0 masters", "m:orcid",
  "rare in this archive's years, common after 2020; finding the id is code, assigning it to one author is judgment")
I(g, "other researcher ids (ResearcherID, Scopus id, Google Scholar)", why(W), "RI", "contrib/contrib-id", "A", "not-extracted", "none seen in the 600", None)
I(g, "authority id (Mandumah catalogue)", why(W, COR), None, "contrib/contrib-id[@contrib-id-type=mandumah-authority]", "B", "extracted-partly",
  "experiment 48 C: 91% of byline authors carry an authority id via the record; in the 600 masters contrib-id 0 (catalogue merge is a separate step)", None)
I(g, "affiliation string as printed", why(W, RD), "C1", "contrib/aff (or aff + xref)", "A", "extracted-well",
  "answers affiliation {a:au.affiliation}; masters aff {s:aff}", "a:au.affiliation")
I(g, "position / academic rank (أستاذ مساعد، مدرس، طالب دكتوراه)", why(W, COR), None, "aff/role or contrib/role[@content-type=position]", "B", "extracted-partly",
  "inside the aff string; v3 aff_parts has no position key; pattern in bylines/notes {m:position_in_aff}", "m:position_in_aff",
  "platform affiliation_mentions.position_title exists; code splits it with a lexicon")
I(g, "department", why(W), "C1 (part)", "aff/institution[@content-type=dept]", "A", "extracted-well",
  "answers aff_parts.department {a:aff.department}; masters dept {s:dept}", "a:aff.department",
  "faculty and department share one key: «كلية التربية» is a faculty, «قسم علم النفس» a department")
I(g, "faculty / college (separate from department)", why(W), "C1 (part)", "aff/institution[@content-type=faculty]", "A", "extracted-partly",
  "no faculty key in aff_parts: faculties land in 'department'", "a:aff.department")
I(g, "institution / university", why(W, COR), "C1", "aff/institution[@content-type=orgname]", "A", "extracted-well",
  "answers {a:aff.institution}; masters orgname {s:orgname}", "a:aff.institution")
I(g, "city", why(W), "C1 (part)", "aff/addr-line[@content-type=city]", "A", "extracted-well", "answers {a:aff.city}; masters {s:city}", "a:aff.city")
I(g, "country", why(W), "C1 (part) / CU", "aff/country[@country]", "A", "extracted-well", "answers {a:aff.country}; masters {s:country}", "a:aff.country",
  "ISO code from the name is code (B)")
I(g, "institution id (ROR, OpenAlex, Mandumah)", why(W), None, "aff/institution-wrap/institution-id", "B", "not-extracted",
  "experiment 48 C: OpenAlex knows 33 of 48 Arab universities; affiliations 39/50 right", None)
I(g, "author-affiliation mapping (superscripts 1,2,*), several affiliations per author", why(W), "C1 [author] address", "contrib/xref[@ref-type=aff] + aff[@id]", "A", "extracted-partly",
  "one affiliation and one aff_parts per author in v3.3; xref aff in 0 masters", None,
  "a second affiliation of one author has nowhere to go")
I(g, "author note in a starred footnote (affiliation, position under *)", why(W, RD), None, "author-notes/fn or contrib/aff", "A", "extracted-partly",
  "starred footnotes on page 1: {m:numbered_footnote_marker_star}; footnotes naming a post or university {m:author_note_fn}; author-notes in 0 masters", "m:numbered_footnote_marker_star",
  "Gemini often copies the affiliation into the author's fields, but the note itself stays a footnote")
I(g, "equal contribution", why(W), None, "contrib/@equal-contrib", "A", "not-extracted", "pattern {m:equal_contribution}", None)
I(g, "deceased mark († / المرحوم)", why(W, RD), None, "contrib/@deceased", "A", "not-extracted", "pattern in bylines {m:deceased}", None)
I(g, "author biography / photo", why(RD, W), None, "contrib/bio; fig[@fig-type=portrait]", "A", "not-extracted",
  "no bio element; portraits are figures with only a description", None, "magazine pieces print a photo and a short bio of the writer")
I(g, "corporate / committee author", why(W), "CA (group author)", "contrib/collab", "A", "extracted-partly",
  "printed as a byline name; platform authorships.inst_id for corporate bylines", None)
I(g, "author-signed closing (name, place, date at the end)", why(RD, W), None, "back/sig-block or sig", "A", "kept-as-text-only",
  "a closing signature stays a paragraph content-type=byline (jats_coverage.md); sig-block in 0 masters", None)

# ============================================================================================ dates / history
g = "metadata"
I(g, "received date", why(W, EXP), None, "history/date[@date-type=received]", "A", "extracted-well",
  "answers {a:hist.received}; masters received {s:history} with history", "a:hist.received")
I(g, "revised date", why(W, EXP), None, "history/date[@date-type=rev-recd]", "A", "extracted-well", "answers {a:hist.revised}", "a:hist.revised")
I(g, "accepted date", why(W, EXP), "(EA)", "history/date[@date-type=accepted]", "A", "extracted-well", "answers {a:hist.accepted}", "a:hist.accepted")
I(g, "published / online date", why(W, EXP), "EA / PD", "pub-date[@date-type=pub|epub]", "A", "extracted-well",
  "answers published {a:hist.published}, online {a:hist.online}", "a:hist.online")
I(g, "date conversion Hijri <-> Gregorian, ISO date", why(W, EXP), "PY", "@calendar, @iso-8601-date", "B", "extracted-partly",
  "jats43.parse_date gives iso-8601 for Gregorian; Hijri pub years converted in platform v2 (publication_dates)", None)

# ============================================================================================ rights / funding
g = "rights-and-funding"
I(g, "copyright statement", why(EXP, W), None, "permissions/copyright-statement, copyright-year, copyright-holder", "B", "kept-as-text-only",
  "© / حقوق in {m:copyright}; permissions in 0 masters", "m:copyright", "regex on first and last page; holder is a name to keep as printed")
I(g, "licence (CC BY ...)", why(EXP, W), None, "permissions/license[@xlink:href] + ali:license_ref", "B", "kept-as-text-only",
  "inside the copyright lines above; not counted separately", None, "the archive's own rights need Mandumah's source (jats_coverage.md)")
I(g, "open-access mark", why(W, EXP), "OA", "permissions/license", "B", "not-extracted", "not counted", None)
I(g, "funding: funder name", why(W), "FU", "funding-group/award-group/funding-source", "B", "kept-as-text-only",
  "real funding sentences: almost none in the 600 (pattern {m:funding}, mostly false hits); funding-group 0", None,
  "rare in this corpus; when present it is a plain sentence code can read")
I(g, "funding: grant number", why(W), "FU", "award-group/award-id", "B", "kept-as-text-only", "as above", None)
I(g, "funding text", why(W), "FX", "funding-group/funding-statement", "B", "kept-as-text-only", "as above", None)
I(g, "acknowledgements", why(W, RD), "FX (part)", "back/ack", "A", "extracted-well",
  "ack {s:ack} (moved by jats43 from a شكر وتقدير / Acknowledgements section)", ("2094-000-013-008", 8, "شكر وتقدير: نتقدم بالشكر والعرفان للأستاذة فتحية المحيشي مهندسة معمل الأنسجة بمركز الأورام مصراتة على المساعدة"),
  "an un-headed thank-you paragraph is not found (needs judgment if wanted)")
I(g, "conflicts of interest statement", why(W, RD), None, "author-notes/fn[@fn-type=coi-statement]", "B", "kept-as-text-only",
  "real statements: none found in the 600 (pattern {m:conflict_of_interest}: all in titles of cited works)", None)
I(g, "ethics approval statement", why(W, RAG), None, "sec[@sec-type=ethics-statement]", "B", "kept-as-text-only",
  "pattern {m:ethics}", "m:ethics")
I(g, "data availability / author contributions", why(W), None, "sec[@sec-type=data-availability]; fn[@fn-type=con]", "B", "not-extracted", "none in the 600", None)

# ============================================================================================ document-level
g = "document-level"
I(g, "document type (research, review, editorial, book review, report, interview, news, translation, thesis summary, obituary, poem)",
  why(W, RAG, RD), "DT", "article/@article-type", "A", "not-extracted",
  "every master says article-type=research-article (600/600); not asked; catalogue 336 gives a coarse kind",
  ("0881-031-355-002", 3, "مؤكدا أن المملكة تتلقى بعد انتهاء موسم الحج دائما الشكر والتقدير من مسؤولي بعثات الحج"),
  "the page shows it at once (a news page, a review, an editorial); one enum in the metadata costs a few tokens")
I(g, "review / systematic review flag", why(RAG, W), "DT=Review", "article/@article-type=review-article", "A", "not-extracted",
  "not asked", None, "a literature-review article cites many works and summarises them: the RAG should know")
I(g, "conference paper: conference name, place, dates", why(W), "CT / CY / CL", "conference/conf-name, conf-loc, conf-date", "A", "not-extracted",
  "conference words on front/title/body {m:conference}; a conference line lands in 'subtitle'", "a:meta.subtitle")
I(g, "thesis summary / thesis part: degree, university, year, supervisor", why(W), None, "custom-meta or product", "A", "extracted-partly",
  "printed as a table in thesis summaries; supervisor contribs {s:supervisor_contrib}", ("0011-005-014-013", 1, "درجة الرسالة : الماجستير سنة الحصول عليها : ١٤٠٤هـ - ١٩٨٤ م عدد الصفحات : ١٨٠ صفحة"))
I(g, "article extracted from a thesis (مستل من رسالة)", why(W), None, "related-article[@related-article-type=derived-from]", "B", "kept-as-text-only",
  "pattern {m:thesis_extract}", None, "usually a starred note on the title")
I(g, "book review: the reviewed book (author, title, publisher, year)", why(W, RD), None, "product (+ source, person-group...)", "A", "not-extracted",
  "product in 0 masters; book-review wording {m:book_review}", "m:book_review")
I(g, "translated article: original title, author, source", why(W), None, "related-article[@related-article-type=translation-of]", "A", "not-extracted",
  "translator contribs {s:translator_contrib}; the original's details not asked", None)
I(g, "part of a series of articles («(٤)», «الحلقة الثانية», «يتبع»)", why(W, RD), None, "related-article[@related-article-type=continues]", "A", "not-extracted",
  "not asked", ("0005-012-004-007", 1, "المدارس النموذجية فى الميزان (٤)"),
  "the part number sits in the title; linking parts needs the series title")
I(g, "article starts or ends outside the scan (incomplete article)", why(COR, RD), None, "custom-meta", "A", "extracted-partly",
  "page-range check against the scan in meta43 (metadata-change {s:metadata_change}); 'continued' on the first block", None)
I(g, "issue front matter (editorial board, contents, instructions to authors) as its own item", why(W), None, "article-type=editorial / table-of-contents", "A", "not-extracted",
  "editorial-board words {m:editorial_board}; contents headings {m:toc}", None)
I(g, "subject category (WoS SC / WC)", why(W, RAG), "SC / WC", "article-categories/subj-group", "B", "not-extracted",
  "subj-group in 0 of the 600 masters (catalogue 336/773 has field of study, used in experiment 29)", None,
  "a classifier on title + abstract + keywords, later")
I(g, "number of references", why(W), "NR", "counts/ref-count", "B", "extracted-partly",
  "ref {s:ref}, parsed works in notes {s:parsed_citations_in_notes}; ref-count not written", None)
I(g, "OCR confidence / reading quality per document", why(COR), None, "custom-meta", "B", "extracted-well", "ALTO WC per word; flags43", None)

# ============================================================================================ abstracts, keywords, classification
g = "metadata"
I(g, "abstract in the article's language", why(W, RAG, RD), "AB", "article-meta/abstract", "A", "extracted-well",
  "abstract {s:abstract_printed}; answers abstract ar {a:abs.ar}", None)
I(g, "abstract in other languages (en, fr)", why(W, RAG), "AB", "trans-abstract[@xml:lang]", "A", "extracted-well",
  "articles with abstracts in 2+ languages {s:abstracts_2plus_langs}", ("0069-000-026-005", 3, "Abstract: This research deals with the opinions and ideas of Arabic grammarians about nouns which called Al- Asma'a Al- sitta"))
I(g, "structured abstract parts (objectives, method, results)", why(RAG), None, "abstract/sec", "B", "kept-as-text-only", "not counted; abstract kept as paragraphs", None)
I(g, "author keywords per language", why(W, RAG), "DE", "kwd-group[@kwd-group-type=author-printed][@xml:lang]/kwd", "A", "extracted-well",
  "kwd-group {s:kwd_printed}; 2+ languages {s:kwd_2plus_langs}", "a:kw.ar")
I(g, "keywords plus (index terms)", why(W), "ID", "kwd-group[@kwd-group-type=index]", "B", "not-extracted", "WoS computes them from titles of references; catalogue 653/692 hold subject terms", None)
I(g, "JEL and other classification codes", why(W), None, "kwd-group[@vocab=JEL]", "B", "kept-as-text-only",
  "JEL pattern {m:jel_code}; MSC/Dewey {m:msc_or_other_class}", "m:jel_code")
I(g, "abstract heading label as printed (الملخص / Résumé)", why(RD), None, "abstract/title", "A", "extracted-well", "label pattern {m:abstract_label}", None)

# ============================================================================================ body structure
g = "body-structure"
I(g, "sections and headings with levels", why(RD, RAG, EXP), None, "sec/title (nested, @disp-level)", "A", "extracted-well",
  "heading blocks {a:blk.heading}; sec {s:sec_with_number_in_title}", ("1900-003-003,004-006", 2, "لمحة ترجمية إلى حياة جان بياجي (١٨٩٦ - ١٩٨٠م)"))
I(g, "section numbering label (أولاً، 1.2، المبحث الأول)", why(RD, EXP), None, "sec/label", "B", "kept-as-text-only",
  "numbered headings {m:section_number}; sec/label not written", "m:section_number")
I(g, "introduction", why(RAG), None, "sec[@sec-type=intro]", "B", "kept-as-text-only", "heading {m:intro_heading}", "m:intro_heading")
I(g, "problem, questions, hypotheses, aims, importance, limits", why(RAG), None, "sec[@sec-type=...]", "B", "kept-as-text-only",
  "heading {m:problem_questions_heading}", "m:problem_questions_heading")
I(g, "previous studies / literature review section", why(RAG, W), None, "sec[@sec-type=literature-review]", "B", "kept-as-text-only",
  "heading {m:prior_studies_heading}", "m:prior_studies_heading", "an un-headed review passage needs judgment; headings cover the common case")
I(g, "terms and definitions section", why(RAG), None, "sec[@sec-type=definitions] / def-list", "B", "kept-as-text-only", "heading {m:terms_heading}", "m:terms_heading")
I(g, "method (sample, tools, procedure)", why(RAG), None, "sec[@sec-type=methods]", "B", "kept-as-text-only", "heading {m:method_heading}", "m:method_heading")
I(g, "results and discussion", why(RAG), None, "sec[@sec-type=results|discussion]", "B", "kept-as-text-only", "heading {m:results_heading}", "m:results_heading")
I(g, "conclusion", why(RAG), None, "sec[@sec-type=conclusions]", "B", "kept-as-text-only", "heading {m:conclusion_heading}", "m:conclusion_heading")
I(g, "recommendations / suggestions", why(RAG), None, "sec[@sec-type=recommendations]", "B", "kept-as-text-only", "heading {m:recommendations_heading}", "m:recommendations_heading")
I(g, "appendices", why(RD, RAG), None, "back/app-group/app", "A", "extracted-well", "app {s:app}; headings {m:appendix_heading}", "m:appendix_heading")
I(g, "glossary / list of abbreviations", why(RD, RAG), None, "back/glossary/def-list", "A", "not-extracted",
  "glossary / def-list in 0 masters; such lists become list items or tables", None)
I(g, "paragraphs", why(RD, RAG), None, "p", "A", "extracted-well", "paragraph blocks {a:blk.paragraph}", None)
I(g, "lists: ordered / unordered, items", why(RD, RAG), None, "list[@list-type]/list-item", "A", "extracted-well",
  "list_item blocks {a:blk.list_item}; masters list {s:list}", ("0011-005-014-013", 1, "١ - التعرف على واقع تدريس مادة الجغرافيا في المرحلة الثانوية للبنين والبنات بمدارس دولة البحرين"))
I(g, "set-apart quotations (block quotes)", why(RD, RAG), None, "disp-quote", "A", "extracted-well", "quote blocks {a:blk.quote}; disp-quote {s:disp_quote}", None)
I(g, "source of a quotation (who is quoted)", why(RAG, W), None, "disp-quote/attrib", "B", "not-extracted", "attrib in 0 masters", None,
  "often the next note; code can attach the note call")
I(g, "inline quotations «...» and their speaker", why(RAG), None, "named-content[@content-type=quote]", "B", "kept-as-text-only", "not counted", None)
I(g, "boxed text (pull-quotes, sidebars)", why(RD), None, "boxed-text", "A", "extracted-well", "boxed blocks {a:blk.boxed}; masters {s:boxed}", None,
  "a pull-quote repeats body text: a 'repeats' flag (B) keeps it out of search counts")
I(g, "reading order across columns and pages", why(RD, RAG), None, "document order", "A", "extracted-well", "blocks in reading order; continued {a:bk.continued}", None)
I(g, "paragraph continued across a page break", why(RD, RAG), None, "one p spanning targets", "A", "extracted-well", "continued {a:bk.continued}", None)
I(g, "jump to a non-adjacent page («بقية ص ٤٥»)", why(RD), None, "one sec spanning pages", "A", "extracted-partly",
  "jump phrases {m:continued_jump}; other_article handles the shared page", None)
I(g, "epigraph / opening quotation, basmala", why(RD), None, "disp-quote[@content-type=epigraph]", "A", "extracted-partly",
  "basmala {m:basmala}; kept as quote or paragraph, no epigraph role", "m:basmala")
I(g, "interview turns (speaker, question / answer)", why(RD, RAG), None, "sec / speech/speaker", "A", "not-extracted", "no block type; not counted", None)
I(g, "text Azure missed (added by the model, no ink box)", why(COR, RD), None, "@content-type=added", "A", "extracted-well",
  "missed {a:top.missed}; masters added {s:added_text}", None)
I(g, "code listings", why(RD), None, "code", "A", "not-extracted", "no block type; none met in the 600", None)

# ============================================================================================ notes
g = "notes"
I(g, "footnotes (foot of the calling page)", why(RD, RAG, W), None, "fn-group[@content-type=footnotes]/fn", "A", "extracted-well",
  "footnote blocks {a:blk.footnote}; masters fn {s:fn}", None)
I(g, "endnotes (gathered at the end)", why(RD, RAG, W), None, "fn-group[@content-type=endnotes]/fn", "A", "extracted-well",
  "endnote blocks {a:blk.endnote}; masters {s:endnotes}", "m:quran_sura_aya")
I(g, "note call markers linked to their notes", why(RD, W), None, "xref[@ref-type=fn]", "A", "extracted-well", "calls {a:bk.calls}", None)
I(g, "note marker as printed ((1), *, ١)", why(RD), None, "fn/label", "A", "extracted-well", "fn/label in 322 articles", None)
I(g, "note kind: author's / translator's / editor's (المترجم، المحقق) note", why(RD, W), None, "fn/@fn-type", "A", "not-extracted",
  "not asked; translator contribs {s:translator_contrib}", None, "a translator's note is not the author's claim")
I(g, "table notes (* p < 0.05, ملاحظة)", why(RD), None, "table-wrap-foot/fn", "A", "kept-as-text-only",
  "table-wrap-foot in 0 masters; note lines {m:table_note}; note calls inside tables {s:fn_in_table}", None,
  "lines under a table become a paragraph or caption; one block type 'table_note' with the table's number would place them")
I(g, "table / figure source line (المصدر: ...)", why(RD, W), None, "table-wrap-foot/attrib", "A", "kept-as-text-only",
  "source lines {m:table_source_note}", "m:table_source_note", "these cite works too: a citation source the index misses today")

# ============================================================================================ references
g = "references"
I(g, "reference list entries as printed", why(W, RD), "CR", "ref-list/ref/mixed-citation", "A", "extracted-well",
  "reference blocks {a:blk.reference}; masters ref {s:ref}", ("0037-000-015-006", 10, "الدجاني، أحمد صدقي، مسلمون ومسيحيون في الحضارة الإسلامية، مركز يافا للدراسات والأبحاث، القاهرة، ١٩٩٩م."))
I(g, "works cited in footnotes / endnotes (one W per work)", why(W), "CR", "fn/p[@content-type=parsed-citations]/element-citation", "A", "extracted-well",
  "cites {a:bk.cites}; parsed-citations {s:parsed_citations_in_notes}", None,
  "where Arabic scholarship does its citing (briefing)")
I(g, "reference type (book, journal, chapter, thesis, web, other)", why(W), "DT of cited", "element-citation/@publication-type", "A", "extracted-well",
  "W types: book {a:W.type.book}, journal {a:W.type.journal}, thesis {a:W.type.thesis}, web {a:W.type.web}, other {a:W.type.other}", None,
  "no 'manuscript', 'conference', 'law', 'archive', 'quran', 'hadith', 'diwan' types: they fall into 'other'")
I(g, "cited authors (surname, given)", why(W), "CR (author)", "person-group[@person-group-type=author]/name", "A", "extracted-well", "W authors {a:W.authors}", None)
I(g, "cited author's death date (ت ٧٥١هـ)", why(W, COR), None, "person-group/name + comment or date-in-citation", "A", "not-extracted",
  "death dates printed {m:death_date}; W has no field (they are dropped or land in year)", "m:death_date",
  "the best key for telling classical authors apart (ابن قدامة ...)")
I(g, "editor of the text (تحقيق / تح / ed.)", why(W), None, "person-group[@person-group-type=editor]", "A", "not-extracted",
  "تحقيق etc. in notes/refs {m:editor_tahqiq}; person-group editor in 0 masters", "m:no_date_no_pub",
  "experiment 48: missing fields are the main fault of citations; the editor is what tells two editions apart")
I(g, "translator of the cited work", why(W), None, "person-group[@person-group-type=translator]", "A", "not-extracted",
  "ترجمة/translated in notes/refs {m:translator_ref}", "m:translator_ref#2")
I(g, "edition (ط٢، الطبعة الثالثة, 2nd ed.)", why(W), None, "element-citation/edition", "A", "not-extracted",
  "edition patterns {m:edition}; edition element in 0 masters", "m:edition")
I(g, "year as printed (Hijri / Gregorian / both / د.ت)", why(W), "CR (year)", "year (+ @calendar), string-date", "A", "extracted-partly",
  "W year {a:W.year}; Hijri years printed {m:hijri_year}; «د.ت» dropped by code; calendar not marked", "m:hijri_year",
  "experiment 48: Hijri years a linking gap; mark calendar per year (B once kept)")
I(g, "title of the cited work", why(W), "CR (title)", "article-title / source (book)", "A", "extracted-well", "W title {a:W.title}", None)
I(g, "source (journal / book a chapter is in)", why(W), "CR (source)", "source", "A", "extracted-well", "W source {a:W.source}", None)
I(g, "series (كتاب الهلال، سلسلة اقرأ)", why(W), None, "series", "A", "extracted-well", "W series {a:W.series}; masters series {s:series}", "a:W.series")
I(g, "volume (ج / مج / Vol.)", why(W), "CR (volume)", "volume", "A", "extracted-well", "W volume {a:W.volume}", None)
I(g, "issue (ع / no.)", why(W), None, "issue", "A", "extracted-well", "W issue {a:W.issue}", None)
I(g, "page cited (ص ٤٥) vs the work's page range", why(W, RD), "CR (page)", "fpage/lpage vs @content-type=cited-page", "A", "extracted-partly",
  "W pages {a:W.pages}; page patterns {m:page_cited}; one 'pages' field for both", "m:page_cited",
  "WoS CR keeps the cited page; ranges and cited pages need two fields")
I(g, "publisher", why(W), None, "publisher-name", "A", "extracted-well", "W publisher {a:W.publisher}", None)
I(g, "place of publication", why(W), None, "publisher-loc", "A", "extracted-well", "W place {a:W.place}", None)
I(g, "no-date / no-publisher markers (د.ت، د.ن، د.م)", why(W, RD), None, "comment", "B", "kept-as-text-only", "{m:no_date_no_pub}", "m:no_date_no_pub")
I(g, "DOI of the cited work", why(W), "CR (DOI)", "pub-id[@pub-id-type=doi]", "A", "extracted-well", "W doi {a:W.doi}; masters {s:pub_id_doi}", "a:W.doi")
I(g, "URL", why(W), None, "ext-link / uri", "A", "extracted-partly", "W url {a:W.url}; URLs printed {m:url}", "m:url",
  "Azure breaks URLs across lines; refs43 joins some, others stay cut")
I(g, "access date (تاريخ الزيارة، retrieved)", why(W), None, "date-in-citation[@content-type=access-date]", "A", "not-extracted",
  "{m:access_date}; date-in-citation 0", "m:access_date")
I(g, "ISBN of the cited book", why(W), None, "pub-id[@pub-id-type=isbn]", "B", "not-extracted", "ISBN printed {m:isbn}", None)
I(g, "thesis: degree and university", why(W), None, "element-citation[@publication-type=thesis]/publisher-name + comment", "A", "extracted-partly",
  "thesis works {a:W.type.thesis}; thesis wording {m:thesis_cited}; degree has no field", "m:thesis_cited")
I(g, "conference paper: conference name, place, year", why(W), None, "conf-name, conf-loc, conf-date", "A", "extracted-partly",
  "lands in 'source'", ("0013-002-001-005", 22, "[cited source] مؤتمر علم النفس السادس"))
I(g, "manuscript: library, shelfmark, folio (ورقة ١٧٩/ب)", why(W), None, "element-citation[@publication-type=manuscript]", "A", "extracted-partly",
  "manuscripts cited {m:manuscript_cited}; type 'other', no fields for repository and folio", "m:manuscript_cited")
I(g, "archival document (file, box, date)", why(W), None, "element-citation[@publication-type=archive]", "A", "not-extracted", "{m:archive_cited}", "m:archive_cited")
I(g, "laws and legal texts (القانون رقم، المادة)", why(W, RAG), None, "element-citation[@publication-type=law]", "B", "kept-as-text-only", "{m:law_cited}", "m:law_cited")
I(g, "back references («المرجع السابق»، «نفسه»، ibid., op. cit.)", why(W), "CR (counts)", "xref to the first full citation", "B", "extracted-partly",
  "Arabic {m:backref_ar}; Latin {m:backref_latin}; platform v2 resolves them (13 of 15 right)", "m:backref_latin")
I(g, "short form of an earlier citation (author + short title)", why(W), None, "xref", "B", "extracted-partly", "joined by the platform's card merge (experiment 48 B)", None)
I(g, "in-text author-year citations → reference list", why(W, RD), None, "xref[@ref-type=bibr]", "B", "not-extracted",
  "author-year patterns (Arabic and Latin) {m:author_year_incite}; xref bibr in 0 masters", ("0201-000-092-013", 5, "starch) for four weeks to induce obesity in rats (Min et al., 2004)."),
  "free later: author surname + year against the parsed list")
I(g, "numbered in-text citations [12] → reference list", why(W, RD), None, "xref[@ref-type=bibr]", "B", "not-extracted", "{m:numeric_incite_bracket}", "m:numeric_incite_bracket")
I(g, "Quran cited as a source in notes (سورة الرعد، الآية ٦)", why(W), None, "element-citation[@publication-type=quran]", "B", "kept-as-text-only",
  "{m:quran_sura_aya}; platform quran_citations designed, not filled", "m:quran_sura_aya")
I(g, "hadith cited (collection, book, number)", why(W), None, "element-citation[@publication-type=hadith]", "B", "kept-as-text-only",
  "رواه/أخرجه + collection {m:hadith_source}; 'حديث رقم' {m:hadith_number}", "m:hadith_number")
I(g, "'see also' / 'انظر' qualifier of a citation", why(W), None, "element-citation/comment", "B", "kept-as-text-only", "printed in the note text", None,
  "WoS counts it; useful to weight a citation (argued with vs referred to)")
I(g, "citation context (the sentence that calls the note)", why(W, RAG), None, "xref position", "B", "extracted-well", "note calls keep their place in the text", None)

# ============================================================================================ tables, figures, math
g = "tables-figures-math"
I(g, "tables: cells, rows, header cells", why(RD, RAG, EXP), None, "table-wrap/table (XHTML)", "A", "extracted-well",
  "table blocks {a:blk.table}; masters tables {s:table}", None)
I(g, "table spans (colspan / rowspan)", why(RD), None, "th/td @colspan @rowspan", "A", "extracted-well", "spans in table answers", None)
I(g, "table caption and number", why(RD, RAG), None, "table-wrap/caption, label", "A", "extracted-partly",
  "table captions {s:caption_table}; the number stays inside the caption (label not split)", ("0013-002-001-005", 15, "جدول رقم (١) مقاييس الصفحة النفسية لعينة المدمنين مقارنة بمجتمع العينة"))
I(g, "table continued on the next page (repeated header)", why(RD), None, "one table-wrap", "A", "extracted-partly", "continued tables keep the printed header row", None)
I(g, "cells Azure did not read (D35)", why(RD, COR), None, "td[@content-type=added]", "A", "extracted-well", "added cells, flagged", None)
I(g, "rotated / landscape table", why(RD), None, "table-wrap[@orientation=landscape]", "A", "not-extracted", "not counted", None)
I(g, "table printed as a picture", why(RD), None, "table-wrap/graphic", "A", "extracted-partly", "becomes a figure with its text-in-figure", None)
I(g, "figures: box and crop", why(RD), None, "fig/graphic", "A", "extracted-well", "figure blocks {a:blk.figure}; masters fig {s:fig}", None)
I(g, "figure caption and number", why(RD, RAG), None, "fig/caption, label", "A", "extracted-partly", "figure captions {s:caption_fig}; label not split", None)
I(g, "figure description in Arabic and English", why(RD, RAG), None, "fig/alt-text (×2, @xml:lang)", "A", "extracted-well",
  "descriptions {a:bk.description}", ("1900-003-003,004-006", 1, "صورة فوتوغرافية قديمة على الشاطئ / Vintage photograph on the beach"))
I(g, "figure kind (chart, photo, map, diagram, manuscript scan, logo, stamp, portrait, cartoon)", why(RD, RAG, W), None, "fig/@fig-type", "A", "extracted-partly",
  "only free-text descriptions; no enum; ink-only figures {s:fig_ink_only}", None,
  "one enum key per figure: cheap, and needed to find every manuscript facsimile or map in the archive")
I(g, "words printed inside a figure", why(RAG), None, "fig/p[@content-type=text-in-figure]", "A", "extracted-well", "{s:text_in_figure}", "o:role.pictureText")
I(g, "chart data (axes, series, values)", why(RAG, EXP), None, "fig/alternatives/table or supplementary data", "A", "not-extracted",
  "not asked", None, "expensive in output tokens; perhaps only axis titles and series names")
I(g, "sub-figures (a, b, c)", why(RD), None, "fig-group/fig", "A", "not-extracted", "not counted", None)
I(g, "mentions of tables/figures in the text (انظر شكل ٢)", why(RD, RAG), None, "xref[@ref-type=fig|table]", "B", "not-extracted", "xref fig/table in 0 masters", None)
I(g, "display equations (LaTeX + MathML)", why(RD, EXP), None, "disp-formula/alternatives", "A", "extracted-well", "equation blocks {a:blk.equation}; disp-formula {s:disp_formula}", None)
I(g, "inline formulas inside a sentence", why(RD), None, "inline-formula", "A", "extracted-partly",
  "inline formulas {s:inline_formula}; math fixes {a:top.math}; v3.4 (candidate) adds those inside Arabic sentences", None)
I(g, "equation numbers", why(RD), None, "disp-formula/label", "B", "kept-as-text-only", "kept in the formula's text", None)
I(g, "chemical formulas / structures", why(RD), None, "chem-struct", "A", "not-extracted", "none met", None)
I(g, "statistics reported (n, mean, SD, t, p, α)", why(RAG), None, "named-content / table cells", "B", "kept-as-text-only",
  "{m:stats_terms}; sample sizes {m:sample_size}", "m:sample_size")

# ============================================================================================ Arabic and Islamic
g = "Arabic-and-Islamic"
I(g, "verse: lines and hemistichs", why(RD, RAG), None, "verse-group/verse-line (halves)", "A", "extracted-well",
  "verse blocks {a:blk.verse}; masters {s:verse_group}", ("0069-000-026-005", 5, "بأبه اقتدى عديّ في الكرمْ ومن يشابه أبَهُ فما ظلمٌ (11)"))
I(g, "verse metre (بحر)", why(RAG, W), None, "verse-group/@content-type", "B", "kept-as-text-only",
  "printed metre labels {m:verse_metre}; prosody from vowelled text is code", "m:verse_metre")
I(g, "poet / speaker of a verse", why(RAG, W), None, "verse-group/attrib", "B", "kept-as-text-only", "in the sentence before the verse", None)
I(g, "Quran quotation set apart", why(RAG, W), None, "disp-quote[@content-type=quran]", "A", "extracted-well", "quote blocks {a:blk.quote}", None)
I(g, "Quran quotation inline (﴿ ﴾)", why(RAG, W), None, "named-content[@content-type=quran]", "B", "kept-as-text-only",
  "﴿…﴾ in {m:quran_brackets}; named-content quran 0 (jats_coverage: 'next candidate')", "m:quran_brackets")
I(g, "Quran reference: sura and aya", why(W), None, "named-content/@specific-use=sura:aya", "B", "not-extracted",
  "printed refs {m:quran_sura_aya}; platform quran_citations designed, reference text not loaded", "m:quran_sura_aya",
  "matching the quoted words to a Quran text gives sura:aya even when nothing is printed")
I(g, "hadith text and its source (رواه البخاري)", why(RAG, W), None, "named-content[@content-type=hadith]", "B", "kept-as-text-only", "{m:hadith_source}", "m:hadith_source")
I(g, "hadith grading as printed (صحيح، حسن، ضعيف)", why(RAG), None, "named-content", "B", "kept-as-text-only", "{m:hadith_grading} (pattern; some false hits)", None)
I(g, "honorific symbols as glyphs (ﷺ ﷻ)", why(RD, RAG), None, "text (Unicode ligature)", "A", "extracted-partly",
  "glyphs present in {m:honorific_glyph}; when printed as a picture-like ligature Azure may drop it or read junk; no rule asks for it", "m:honorific_glyph",
  "one prompt line: a printed honorific ligature is fixed to its Unicode glyph, never spelt out")
I(g, "honorific phrases spelt out (صلى الله عليه وسلم، رضي الله عنه)", why(RAG), None, "text", "B", "extracted-well", "{m:honorific_spelled}", "m:honorific_spelled",
  "search should fold glyph and phrase together (B)")
I(g, "diacritics (tashkeel) as printed", why(RD, RAG), None, "text", "A", "extracted-partly",
  "vowelled words {m:diacritised_word}; Azure drops letters in fully vowelled lines (v3.4 candidate; rules43.vowelled_words flags)", "m:diacritised_word")
I(g, "Persian / Ottoman / dialect letters (پ چ ژ گ)", why(RD), None, "text + @xml:lang", "B", "extracted-well", "{m:persian_true_letters}", "m:persian_true_letters")
I(g, "Azure's Persian look-alikes ی / ک for Arabic ي ى ك", why(RAG, COR), None, "text (encoding)", "B", "not-extracted",
  "words with ی or ک: {m:persian_yeh_kaf_from_azure}; src/inkscript/text.py fold_letters exists but experiments 41/43 do not call it", "m:persian_yeh_kaf_from_azure",
  "search for «الرسمي» misses «الرسمی»; folding is free code")
I(g, "foreign words in Latin inside Arabic sentences", why(RAG, RD), None, "named-content / @xml:lang on span", "B", "kept-as-text-only",
  "{m:latin_in_arabic_block}", "m:latin_in_arabic_block", "span-level language marks; direction handling in readers")
I(g, "Hijri dates in the text", why(RAG, W), None, "named-content[@content-type=date]", "B", "kept-as-text-only", "{m:hijri_year}", None)
I(g, "Gregorian dates with م", why(RAG), None, "named-content", "B", "kept-as-text-only", "{m:gregorian_year_m}", None)
I(g, "death dates of scholars in the text (ت ...هـ)", why(RAG, W), None, "named-content", "B", "kept-as-text-only", "{m:death_date}", "m:death_date")
I(g, "Arabic-Indic vs Western digits as printed", why(RD, RAG), None, "text", "B", "extracted-well", "kept as printed; fold for search", None)
I(g, "Greek, Hebrew, Syriac letters", why(RD), None, "text + @xml:lang", "B", "extracted-well", "Greek {m:greek} (mostly maths); Hebrew/Syriac {m:hebrew_syriac}", None)
I(g, "ornaments between verse halves", why(RD), None, "ALTO role.ornament", "A", "extracted-well", "ornaments {a:top.ornaments}; ALTO {o:role.ornament}", "o:role.ornament")
I(g, "kashida / tatweel and decorative stretching", why(RAG), None, "text", "B", "extracted-well", "kept as printed (meta43 respell aside); fold for search", None)
I(g, "isnad chains (narrator lists)", why(RAG, W), None, "named-content", "B", "not-extracted", "not counted", None)
I(g, "people, places, organisations named in the text", why(RAG, W), None, "named-content / NER layer", "B", "not-extracted", "not counted", None,
  "an entity layer for search; from the stored text, later")

# ============================================================================================ visual and styling
g = "visual-and-styling"
for st, tag, why_, note in [
    ("italic", "italic", "titles of works in references, foreign words, emphasis", "Azure gives no styles (briefing: weakest areas)"),
    ("bold", "bold", "headings run into paragraphs, defined terms, emphasis", "a bold run-in heading at a paragraph's start is a heading the model can see"),
    ("underline", "underline", "emphasis, headings in older print", ""),
    ("superscript", "sup", "note markers, ordinals (1st, 2e), powers", "note markers are captured as calls; other superscripts are lost"),
    ("subscript", "sub", "chemistry, indices outside formulas", ""),
    ("small caps / letter-spacing", "sc", "names in French/English references", ""),
]:
    I(g, st, why(RD, EXP, W), None, tag, "A", "not-extracted", f"<{tag}> in 0 of the 600 masters; ALTO strings carry no style (STYLE in 0); not asked", None,
      f"used for: {why_}. {note}".strip())
I(g, "text colour / highlight", why(RD), None, "styled-content", "A", "not-extracted", "not asked", None)
I(g, "type size / face per block (body, note, quotation)", why(RD), None, "ALTO TextStyle", "B", "not-extracted", "ALTO has no TextStyle; line heights give a size class (code)", None)
I(g, "heading look → level, consistent per article", why(RD), None, "@disp-level", "A", "extracted-well", "levels {a:bk.level}", None)
I(g, "columns per page", why(RD), None, "ALTO PrintSpace/blocks", "B", "extracted-partly", "from block boxes (code)", None)
I(g, "text direction per block", why(RD), None, "@dir / xml:lang", "B", "extracted-well", "text-direction custom-meta 600/600; per block from script", None)
I(g, "drop caps / decorated initial letters", why(RD, COR), None, "text", "A", "extracted-partly", "fixes repair a misread initial; not counted", None)
I(g, "rules, separators, end marks (* * *)", why(RD), None, "ALTO GraphicalElement", "B", "extracted-partly", "noise / ornament roles", None)

# ============================================================================================ page furniture
g = "page-furniture"
I(g, "running heads", why(RD, COR), None, "ALTO role.pageHeader (not in JATS body)", "A", "extracted-well", "ALTO {o:role.pageHeader}", "o:role.pageHeader")
I(g, "page footers (journal name, issue)", why(RD, COR), None, "ALTO role.pageFooter", "A", "extracted-well", "ALTO {o:role.pageFooter}", "o:role.pageFooter")
I(g, "printed page numbers", why(RD, W), None, "ALTO role.pageNumber", "A", "extracted-well", "ALTO {o:role.pageNumber}", "o:role.pageNumber")
I(g, "printed folio ↔ scan page map", why(RD, W, EXP), "BP/EP", "ALTO Page/@PRINTED_IMG_NR", "B", "extracted-partly",
  "PRINTED_IMG_NR on 0 ALTO pages; meta43 page_range reads the first and last folio", None,
  "every page's folio lets a citation «ص ٤٥» open the right scan page")
I(g, "another article on a shared page", why(RD, COR), None, "ALTO role.otherArticle (out of JATS)", "A", "extracted-well",
  "other_article blocks {a:blk.other_article}; ALTO {o:role.otherArticle}", "o:role.otherArticle")
I(g, "show-through from the other side of the paper", why(COR), None, "ALTO role.showThrough", "A", "extracted-well", "ALTO {o:role.showThrough}", "o:role.showThrough")
I(g, "noise marks (specks, rules read as letters)", why(COR), None, "ALTO role.noise", "A", "extracted-well", "noise {a:top.noise}; ALTO {o:role.noise}", None)
I(g, "journal logo / banner", why(RD), None, "fig (ink-only)", "A", "extracted-partly", "a figure with a description; no kind", ("1677-010-002-023", 1, "FAK for Sciences Journal مجلة آفاق للعلوم EISSN: 2602-5345 ISSN: 2507-7228 [words inside the banner figure]"))
I(g, "advertisements", why(RD, COR), None, "ALTO role (other)", "A", "extracted-partly", "rules43.advert_whole keeps an advert whole; no block type", None)
I(g, "library stamps, ownership marks, call numbers on the scan", why(COR, W), None, "fig[@fig-type=stamp] / ALTO", "A", "extracted-partly",
  "v3.1: stamps are figures; no kind to count them", None)
I(g, "handwriting and readers' marginalia", why(COR, RD), None, "ALTO role (handwriting)", "A", "not-extracted",
  "no type; handwriting lands in noise or text", None, "never the article's text; worth one flag")
I(g, "signatures (printed or handwritten)", why(RD), None, "fig / sig", "A", "extracted-partly", "a figure if drawn; no kind", None)
I(g, "scan defects (cut-off edge, blur, missing or duplicated page, page out of order)", why(COR), None, "custom-meta / flags", "A", "not-extracted",
  "not asked; page-range checks catch some (metadata-change {s:metadata_change})", None,
  "the model sees the page; one 'scan_problem' note per page would route pages to re-scan")
I(g, "blank pages", why(COR), None, "ALTO Page without blocks", "B", "extracted-well", "pages with no blocks", None)

# ============================================================================================ language
g = "document-level"
I(g, "language per block", why(RAG, RD, EXP), "LA", "@xml:lang on blocks", "A", "extracted-partly",
  "lang given on blocks in {a:bk.lang}; masters xml:lang on body elements {s:lang_attr_blocks}; French labelled English in places (platform)", None,
  "code can detect the language from the stored text (B); the model's tag is a hint")
I(g, "script per block", why(RAG), None, "@xml:lang with script subtag", "B", "extracted-well", "from Unicode ranges", None)

# ============================================================================================ RAG-specific
g = "RAG-specific"
I(g, "section path per passage (H2 › H3 › H4)", why(RAG), None, "sec nesting", "B", "extracted-well", "sec nesting {s:sec_with_number_in_title}", None)
I(g, "block role per passage (body, note, quote, verse, table, caption, abstract)", why(RAG), None, "element kind", "A", "extracted-well", "every block has a type", None)
I(g, "page and box per passage (ink anchor)", why(RAG, RD, COR), None, "ALTO TextBlock + JATS target", "A", "extracted-well", "ALTO boxes for every word", None)
I(g, "prior-studies flag on passages", why(RAG), None, "sec[@sec-type=literature-review]", "B", "not-extracted", "from headings {m:prior_studies_heading}", None)
I(g, "review-article flag", why(RAG), None, "article-type", "A", "not-extracted", "see document type", None)
I(g, "voice: the author's own claim vs a quotation or a cited view", why(RAG), None, "disp-quote / named-content", "A", "extracted-partly",
  "set-apart quotes are blocks; inline quotations not marked", None, "the RAG should not answer 'the author says' with a quoted opponent")
I(g, "notes attached to the passage that calls them", why(RAG), None, "xref → fn", "A", "extracted-well", "calls {a:bk.calls}", None)
I(g, "works cited by the passage", why(RAG, W), None, "xref → fn → element-citation", "B", "extracted-partly", "through note calls; author-year not linked", None)
I(g, "tables serialised as text rows", why(RAG), None, "table → text", "B", "extracted-well", "from the XHTML table", None)
I(g, "figure description as a searchable passage", why(RAG), None, "fig/alt-text", "A", "extracted-well", "{a:bk.description}", None)
I(g, "passage language", why(RAG), None, "@xml:lang", "B", "extracted-partly", "see language per block", None)
I(g, "passage trust (word confidence, fixes, flags)", why(RAG, COR), None, "ALTO WC, flags", "B", "extracted-well", "ALTO WC per word; flags43", None)
I(g, "passage is front / back matter (not body)", why(RAG), None, "front / back", "A", "extracted-well", "abstracts, keywords, notes moved out of the body", None)
I(g, "running heads, page numbers kept out of passages", why(RAG), None, "ALTO roles", "A", "extracted-well", "furniture roles", None)

# ============================================================================================ corrections
g = "document-level"
I(g, "reader fixes (Azure misreadings) with Azure's reading kept", why(COR, RD), None, "named-content[@content-type=reader-fix] + notes", "A", "extracted-well",
  "fixes {a:top.fixes}", None)
I(g, "suspected misprints with a proposed correction (D30)", why(COR, RD), None, "named-content[@content-type=sic] + notes", "A", "extracted-well",
  "sic {a:top.sic}", ("1900-003-003,004-006", 1, "Conitif [sic → Cognitif]"))


# Group-A gaps: 1 = add to the prompt before the big run (cheap keys or enums, high value); 2 = add if a paid test shows
# it is cheap and reliable; 3 = leave (rare in this archive, expensive in output, or code can do it later).
PRIORITY = {
    "document type": 1, "review / systematic review flag": 1, "corresponding author mark": 1, "ORCID": 1,
    "other researcher ids": 1, "Latin form of an Arabic author's name": 1, "author-affiliation mapping": 1,
    "faculty / college": 1, "author note in a starred footnote": 1, "contributor role phrase": 2,
    "conference paper: conference name, place, dates": 1, "thesis summary": 1, "book review": 1, "translated article": 1,
    "part of a series of articles": 1, "cited author's death date": 1, "editor of the text": 1, "translator of the cited work": 1,
    "edition (": 1, "year as printed": 1, "page cited": 1, "access date": 1, "thesis: degree": 1,
    "conference paper: conference name, place, year": 1, "manuscript:": 1, "archival document": 2, "URL": 3,
    "figure kind": 1, "note kind": 1, "table notes": 1, "table / figure source line": 1, "honorific symbols": 1,
    "diacritics": 1, "inline formulas": 1, "scan defects": 1, "handwriting": 1, "library stamps": 1,
    "italic": 2, "bold": 2, "superscript": 2, "subscript": 2, "underline": 3, "small caps": 3, "text colour": 3,
    "publisher as printed": 2, "subtitle": 1, "issue (incl.": 3, "issue date": 3, "printed in which year": 3,
    "equal contribution": 2, "deceased mark": 2, "author biography": 2, "corporate / committee author": 3,
    "article starts or ends outside": 2, "issue front matter": 1, "glossary": 2, "jump to a non-adjacent page": 2,
    "epigraph": 3, "interview turns": 2, "code listings": 3, "table caption and number": 3,
    "table continued": 3, "rotated / landscape table": 3, "table printed as a picture": 3, "figure caption and number": 3,
    "chart data": 3, "sub-figures": 3, "chemical formulas": 3, "drop caps": 3, "journal logo": 3, "advertisements": 2,
    "signatures": 3, "language per block": 3, "review-article flag": 1, "voice:": 2, "author-signed closing": 2,
}


def priority(it):
    if it["needs"] != "A" or it["today"] == "extracted-well": return None
    for k, v in PRIORITY.items():
        if it["field"].startswith(k): return v
    raise KeyError(it["field"])


def main():
    out = []
    for i, it in enumerate(ITEMS, 1):
        it = dict(it)
        it["id"] = f"x{i:03d}"
        it["evidence"] = fmt(it["evidence"])
        it["example"] = example(it["example"])
        if not it["wos_tag"]: it["wos_tag"] = None
        if not it["note"]: it["note"] = None
        it["prompt_priority"] = priority(it)
        out.append(it)
    json.dump({"made": "2026-10-22", "experiment": "51_extraction_inventory", "articles": 600,
               "masters": ["experiments/43_rehearsal/out/v33_300_final/masters", "experiments/43_rehearsal/out/v33_300b_fix3/masters"],
               "prompt": "v3.3", "items": out}, open(HERE / "inventory.json", "w"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(len(out), Counter(i["today"] for i in out), Counter(i["needs"] for i in out))
    print(Counter(i["group"] for i in out))


if __name__ == "__main__":
    main()
