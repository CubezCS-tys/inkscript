"""Experiment 51: count real occurrences of extractable things in the 600 masters (v33_300_final + v33_300b_fix3).

Read-only; no calls. Each pattern is searched in the printed text of the masters' blocks (JATS elements whose id is
p<page>..., outermost only; parsed-citations, alt-text and the reader-fix / misprint notes left out), with the block's
context (front, body, heading, footnote/endnote, reference, table, figure, caption, abstract). Writes
out/master_counts.json: per key, articles / occurrences / up to 3 examples (stem, page, context, snippet <= 160 chars).
"""
import glob, json, re, collections
from pathlib import Path
from lxml import etree

HERE = Path(__file__).resolve().parent
R = HERE.parent / "43_rehearsal" / "out"
FILES = sorted(glob.glob(str(R / "v33_300_final/masters/*.jats.xml"))) + sorted(glob.glob(str(R / "v33_300b_fix3/masters/*.jats.xml")))
BID = re.compile(r"^p(\d+)[a-z]+\d+")
SKIP = {"alt-text", "element-citation"}

def ln(el): return etree.QName(el).localname if isinstance(el.tag, str) else ""

def text_of(el):
    out = []
    def walk(e):
        if not isinstance(e.tag, str): return
        if ln(e) in SKIP or (ln(e) == "p" and e.get("content-type") == "parsed-citations"): 
            if e.tail: out.append(e.tail)
            return
        if e.text: out.append(e.text)
        for c in e: walk(c)
        if e.tail and e is not el: out.append(e.tail)
    walk(el)
    return re.sub(r"\s+", " ", "".join(out)).strip()

def context(el):
    anc = [ln(a) for a in el.iterancestors()] + [ln(el)]
    ct = el.get("content-type") or ""
    if "fn" in anc:
        fg = [a for a in el.iterancestors() if ln(a) == "fn-group"]
        return "endnote" if fg and fg[0].get("content-type") == "endnotes" else "footnote"
    if "ref" in anc: return "reference"
    if "table-wrap" in anc: return "table"
    if "fig" in anc: return "figure"
    if ln(el) == "caption" or "caption" in anc or ct == "caption": return "caption"
    if "trans-abstract" in anc or "abstract" in anc: return "abstract"
    if "kwd-group" in anc: return "keywords"
    if "title-group" in anc: return "title"
    if "contrib" in anc or "contrib-group" in anc: return "byline"
    if "front" in anc: return "front"
    if ln(el) == "title" and "sec" in anc: return "heading"
    if "verse-group" in anc: return "verse"
    if "disp-quote" in anc: return "quote"
    if "list" in anc: return "list"
    if ct == "byline": return "byline"
    return "body"

def blocks(tree):
    for el in tree.iter():
        if not isinstance(el.tag, str): continue
        i = el.get("id") or ""
        m = BID.match(i)
        if not m: continue
        if any(BID.match(a.get("id") or "") for a in el.iterancestors()): continue
        if any(ln(a) == "notes" for a in el.iterancestors()): continue
        yield int(m.group(1)), context(el), text_of(el)

# (key, regex, contexts or None for all)
P = [
 ("email", r"[\w.+-]+@[\w-]+(\.[\w-]+)+", None),
 ("orcid", r"(?i)orcid|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", None),
 ("doi_text", r"(?i)\b10\.\d{4,9}/\S+|doi\s*:", None),
 ("url", r"(?i)https?://|www\.", None),
 ("issn", r"(?i)\bissn\b|ردمد|الترقيم الدولي", None),
 ("isbn", r"(?i)\bisbn\b|ردمك", None),
 ("funding", r"(?i)funded by|(work|research|study|project) (was|is) (supported|funded)|grant (no|number|#)|financial support|بدعم من (عمادة|جامعة|مدينة|صندوق|وزارة|مؤسسة|مركز)|بتمويل من (عمادة|جامعة|مدينة|صندوق|وزارة|مؤسسة|مركز)|ممول من|مموّل من|منحة رقم|مشروع (بحثي )?رقم|عمادة البحث العلمي|الدعم المالي", None),
 ("acknowledgement", r"(?i)\backnowledge?ments?\b|remerciements|شكر وتقدير|الشكر والتقدير|بالشكر الجزيل|أتقدم بالشكر|نتقدم بالشكر|يتقدم الباحث(ون|ان)? بالشكر|الشكر موصول|يشكر الباحث", None),
 ("conflict_of_interest", r"(?i)conflict of interest|competing interest|تضارب المصالح|تعارض المصالح|تضارب مصالح", None),
 ("ethics", r"(?i)ethic(s|al) (committee|approval)|informed consent|لجنة أخلاقيات|الموافقة الأخلاقية|موافقة لجنة", None),
 ("copyright", r"(?i)©|copyright|حقوق الطبع|جميع الحقوق محفوظة|حقوق النشر محفوظة|creative commons|cc[ -]by", None),
 ("corresponding", r"(?i)corresponding author|auteur correspondant|الباحث المراسل|المؤلف المراسل|للمراسلة|المراسلة:", None),
 ("received_label", r"(?i)received|reçu le|تاريخ الاستلام|تاريخ الإستلام|تاريخ الاستقبال|تاريخ الإرسال|تاريخ التسليم|تاريخ الورود", None),
 ("accepted_label", r"(?i)accepted|accepté|تاريخ القبول|قبل للنشر|مقبول للنشر|تاريخ قبول", None),
 ("published_label", r"(?i)\bpublished( online)?\s*(:|on)|available online|publié le|تاريخ النشر", None),
 ("hijri_year", r"[\d٠-٩]{3,4}\s*(هـ|ﻫ|ه\b)", None),
 ("death_date", r"\(\s*(ت|المتوفى|توفي|المتوفي)\s*[.:]?\s*[\d٠-٩]{2,4}\s*(هـ|ه)?", None),
 ("gregorian_year_m", r"[\d٠-٩]{4}\s*م\b", None),
 ("quran_brackets", r"﴿[^﴾]{2,400}﴾?|(?<![a-zA-Z\\}])\{[\u0600-\u06FF\u064B-\u0652 ]{6,300}\}", None),
 ("quran_sura_aya", r"(سورة|سُورَة)\s+\S+\s*[،,:]?\s*(الآية|الآيات|آية|الاية|آ)\s*[:\s]*[\d٠-٩]+|\[\s*\S+\s*:\s*[\d٠-٩]+\s*\]", None),
 ("honorific_glyph", r"[ﷺﷻ﷽ﷲ\uFDF0-\uFDFF]|\u0610|\u0611|\u0612|\u0613", None),
 ("honorific_spelled", r"صلى الله عليه وسلم|صلى الله عليه وآله|رضي الله عنه|رضي الله عنها|رضي الله عنهم|عليه السلام|رحمه الله|رحمهم الله|عز وجل|جل جلاله|سبحانه وتعالى", None),
 ("hadith_source", r"(رواه|أخرجه|اخرجه)\s+(البخاري|مسلم|أبو داود|ابو داود|الترمذي|النسائي|ابن ماجه|ابن ماجة|أحمد|احمد|مالك|الحاكم|البيهقي|الطبراني)", None),
 ("hadith_number", r"حديث رقم|رقم الحديث|\bح\s*[:(]?\s*[\d٠-٩]+", ("footnote", "endnote", "reference")),
 ("hadith_grading", r"(حديث|إسناده|اسناده|وإسناده|سنده)\s+(صحيح|حسن|ضعيف|موضوع|مرسل)|صححه الألباني|حسنه الألباني|ضعفه الألباني|حديث حسن صحيح|متفق عليه", None),
 ("backref_ar", r"المرجع السابق|المصدر السابق|المرجع نفسه|المصدر نفسه|نفس المرجع|نفس المصدر|المرجع ذاته|المصدر ذاته|\bنفسه\b", ("footnote", "endnote", "reference")),
 ("backref_latin", r"(?i)\bibid\b|\bibidem\b|op\.\s*cit|loc\.\s*cit|\bid\.\s", ("footnote", "endnote", "reference")),
 ("editor_tahqiq", r"تحقيق|تح\s*:|\bتح\.|حققه|ضبط وتحقيق|(?i:\bed(s)?\.|edited by|\(ed\.\))", ("footnote", "endnote", "reference")),
 ("translator_ref", r"ترجمة|تعريب|نقله إلى العربية|(?i:translated by|trans\.|traduit par|trad\.)", ("footnote", "endnote", "reference")),
 ("edition", r"\bط\s*[\d٠-٩]+|\bط\s*\.\s*[\d٠-٩]+|الطبعة\s+\S+|(?i:\d+(st|nd|rd|th)\s+ed\b|\béd\.)", ("footnote", "endnote", "reference")),
 ("volume_juz", r"\bج\s*[\d٠-٩]+|\bالجزء\s+\S+|\bمج\s*[\d٠-٩]+|(?i:\bvol\.\s*\d)", ("footnote", "endnote", "reference")),
 ("page_cited", r"\bص\s*[\d٠-٩]+|\bص\s*ص|(?i:\bpp?\.\s*\d)", ("footnote", "endnote", "reference")),
 ("no_date_no_pub", r"د\.\s*ت|د\.\s*ن|د\.\s*م|بدون تاريخ|(?i:\bn\.d\.|s\.d\.)", ("footnote", "endnote", "reference")),
 ("access_date", r"(?i)تاريخ الزيارة|تاريخ الاطلاع|تاريخ الدخول|تم الاطلاع|اطلع عليه|retrieved|accessed|consulté le|visited", None),
 ("manuscript_cited", r"مخطوط|مخطوطة|(?i:\bms\.|manuscrit)|ورقة\s*[\d٠-٩]+|لوحة\s*[\d٠-٩]+", ("footnote", "endnote", "reference")),
 ("archive_cited", r"دار الوثائق|الأرشيف|أرشيف|محفظة|ملف رقم|وثيقة رقم|(?i:archives? nationales?|\bfile no)", ("footnote", "endnote", "reference")),
 ("thesis_cited", r"رسالة ماجستير|رسالة دكتوراه|أطروحة دكتوراه|أطروحة|رسالة جامعية|(?i:thesis|dissertation|thèse|mémoire)", ("footnote", "endnote", "reference")),
 ("law_cited", r"القانون رقم|قانون رقم|المادة\s*[\d٠-٩]+|المرسوم|الجريدة الرسمية|قرار رقم|نظام رقم", None),
 ("author_year_incite", r"\([^()]{2,50}?[،,]\s*\(?[12٠-٩][\d٠-٩]{3}[a-z]?\)?\s*(?:[،,:]\s*(ص|p\.?)\s*[\d٠-٩-]+)?\)", ("body", "list", "table", "abstract", "quote", "heading")),
 ("numeric_incite_bracket", r"\[[\d٠-٩]{1,3}(\s*[,،-]\s*[\d٠-٩]{1,3})*\]", ("body", "list")),
 ("kw_label", r"(?i)الكلمات المفتاحية|الكلمات المفتاحيّة|الكلمات الدالة|كلمات مفتاحية|key ?words|mots[- ]cl[ée]s", None),
 ("jel_code", r"(?i)\bJEL\b|تصنيف JEL|\b[A-Z][0-9]{2}\s*,\s*[A-Z][0-9]{2}\b", None),
 ("msc_or_other_class", r"(?i)\bMSC\b|\bPACS\b|\bDDC\b|تصنيف ديوي", None),
 ("abstract_label", r"(?i)^(\s*)(الملخص|ملخص|المستخلص|مستخلص|abstract|résumé|summary)", ("heading", "abstract", "body", "front")),
 ("prior_studies_heading", r"(?i)الدراسات السابقة|دراسات سابقة|الأدبيات|مراجعة الأدبيات|الإطار النظري|literature review|previous studies|related work|état de l'art", ("heading",)),
 ("method_heading", r"(?i)منهج|منهجية|إجراءات الدراسة|إجراءات البحث|عينة|مجتمع الدراسة|أدوات الدراسة|method|méthodo", ("heading",)),
 ("results_heading", r"(?i)النتائج|نتائج الدراسة|نتائج البحث|مناقشة|results|discussion|résultats", ("heading",)),
 ("conclusion_heading", r"(?i)الخاتمة|خاتمة|الخلاصة|خلاصة|الاستنتاجات|conclusion", ("heading",)),
 ("recommendations_heading", r"(?i)التوصيات|توصيات|المقترحات|مقترحات|recommendations|suggestions", ("heading",)),
 ("problem_questions_heading", r"(?i)مشكلة الدراسة|مشكلة البحث|أسئلة الدراسة|أسئلة البحث|تساؤلات|فرضيات|فروض|أهداف الدراسة|أهداف البحث|أهمية الدراسة|أهمية البحث|حدود الدراسة|problem|hypothes|objectives", ("heading",)),
 ("terms_heading", r"(?i)مصطلحات الدراسة|مصطلحات البحث|التعريفات الإجرائية|التعريفات|definitions|glossary|قائمة المصطلحات|ثبت المصطلحات", ("heading",)),
 ("intro_heading", r"(?i)المقدمة|مقدمة|تمهيد|introduction", ("heading",)),
 ("appendix_heading", r"(?i)ملحق|الملاحق|ملاحق|appendix|annexe", ("heading",)),
 ("refs_heading", r"(?i)المراجع|المصادر|قائمة المراجع|ثبت المصادر|references|bibliograph|sources", ("heading",)),
 ("notes_heading", r"(?i)الهوامش|هوامش|الحواشي|الإحالات|notes", ("heading",)),
 ("ack_heading", r"(?i)شكر|acknowledg|remerciement", ("heading",)),
 ("section_number", r"^\s*([\d٠-٩]+(\.[\d٠-٩]+)*\s*[-.)]|أولا|ثانيا|ثالثا|أولاً|ثانياً|ثالثاً|المبحث|المطلب|الفصل|الفرع|المحور|[IVX]+\s*[-.])", ("heading",)),
 ("table_source_note", r"^\s*(المصدر|المصادر|المرجع|source)\s*[:：]", None),
 ("table_note", r"^\s*(\*|ملاحظة|ملحوظة|note)\s*[:：]?", ("caption", "body", "table")),
 ("stats_terms", r"(?i)SPSS|ألفا كرونباخ|كرونباخ|cronbach|معامل الارتباط|اختبار ت|t-test|ANOVA|تحليل التباين|مستوى الدلالة|p\s*[<=>]\s*0?\.\d|α\s*=|انحراف معياري|المتوسط الحسابي", None),
 ("sample_size", r"(?i)(عينة|العينة)\s*(قوامها|مكونة من|تكونت من|بلغت|من)\s*\(?[\d٠-٩]+|\bn\s*=\s*\d+", None),
 ("verse_metre", r"(البحر|بحر)\s+(الطويل|البسيط|الكامل|الوافر|الرجز|الرمل|الخفيف|السريع|المتقارب|المنسرح|المديد|الهزج|المجتث|المضارع|المقتضب|المتدارك)|\(\s*(من\s+)?(الطويل|البسيط|الكامل|الوافر|الرجز|الرمل|الخفيف|السريع|المتقارب|المنسرح|المديد|الهزج|المجتث)\s*\)", None),
 ("basmala", r"بسم الله الرحمن الرحيم|﷽", None),
 ("dedication", r"^\s*(إهداء|الإهداء|dedicat)", None),
 ("persian_true_letters", r"\S*[پچژگ]\S*", None),
 ("persian_yeh_kaf_from_azure", r"\S*[کی]\S*", None),
 ("hebrew_syriac", r"[\u0590-\u05FF\u0700-\u074F]", None),
 ("greek", r"[\u0370-\u03FF]", ("body", "list", "quote", "footnote", "endnote", "reference")),
 ("latin_in_arabic_block", r"[\u0600-\u06FF][^\n]{0,80}\b[A-Za-z]{4,}\b|\b[A-Za-z]{4,}\b[^\n]{0,80}[\u0600-\u06FF]", ("body",)),
 ("diacritised_word", r"\S*[\u064B-\u0652]\S*[\u064B-\u0652]\S*[\u064B-\u0652]\S*", ("body", "verse", "quote")),
 ("conference", r"(?i)مؤتمر|ندوة|ملتقى|conference|colloque|symposium|proceedings|actes du", ("front", "title", "byline", "body")),
 ("thesis_extract", r"مستل من|مستلة من|مستخلص من رسالة|جزء من رسالة|(?i:extracted from|part of a (phd|master))", None),
 ("book_review", r"(?i)عرض كتاب|قراءة في كتاب|مراجعة كتاب|book review|compte rendu", ("title", "front", "heading", "body")),
 ("translated_article", r"ترجمة\s*:|ترجمه|ترجمها|نقلها إلى العربية|(?i:translated by|traduit par)", ("title", "byline", "front", "body")),
 ("deceased", r"المرحوم|الراحل|المغفور له|†", ("byline", "front", "title")),
 ("equal_contribution", r"(?i)equal(ly)? contribut|contributed equally|بالتساوي في (إعداد|هذا البحث)", None),
 ("honorific_title_byline", r"(?i)^(د\.|د/|أ\.د|ا\.د|أ\.م\.د|الدكتور|الدكتورة|الأستاذ|الأستاذة|الشيخ|الإمام|العلامة|سماحة|فضيلة|Dr\.?\s|Prof\.?\s|Pr\.?\s)", ("byline",)),
 ("position_in_aff", r"(?i)أستاذ مساعد|أستاذ مشارك|أستاذ دكتور|أستاذ\b|مدرس|محاضر|باحث|طالب دكتوراه|طالبة دكتوراه|عميد|رئيس قسم|assistant professor|associate professor|professor|lecturer|researcher|ph\.?d\.? (student|candidate)|maître de conférences", ("byline", "front", "footnote")),
 ("author_note_fn", r"(?i)أستاذ|جامعة|كلية|university|université|faculty|@", ("footnote",)),
 ("continued_jump", r"بقية\s*(ص|المنشور|الموضوع|المقال|صفحة|المنشور)|التتمة\s*(في|ص|على)|(?i:continued (on|from)|suite (page|p\.))|^\s*(يتبع|تابع)\s*[.:]?\s*$", None),
 ("photo_credit", r"(?i)^\s*(تصوير|عدسة)|photo( by)?\s*:|المصدر\s*:\s*(الإنترنت|موقع|شبكة)", ("caption", "figure")),
 ("price_ad", r"(?i)للاشتراك|الاشتراك السنوي|سعر النسخة|قسيمة اشتراك|قيمة الاشتراك|subscription rate|abonnement", None),
 ("editorial_board", r"(?i)رئيس التحرير|مدير التحرير|سكرتير التحرير|editorial board|editor[- ]in[- ]chief|rédacteur en chef", None),
 ("toc", r"(?i)^\s*(المحتويات|فهرس العدد|فهرس المحتويات|محتويات العدد|محتويات البحث|table of contents|contents|sommaire)\s*[:]?\s*$", None),
 ("numbered_footnote_marker_star", r"^\s*\*", ("footnote",)),
]

def main():
    CP = [(k, re.compile(r, re.M), c) for k, r, c in P]
    C = collections.Counter(); A = collections.defaultdict(set); EX = collections.defaultdict(list)
    S = collections.Counter(); SA = collections.defaultdict(set); SEX = collections.defaultdict(list)
    for f in FILES:
        stem = Path(f).name.replace(".jats.xml", "")
        tree = etree.parse(f)
        for page, ctx, t in blocks(tree):
            if not t: continue
            for k, rx, cs in CP:
                if cs and ctx not in cs: continue
                ms = list(rx.finditer(t))
                if not ms: continue
                C[k] += len(ms); A[k].add(stem)
                if len(EX[k]) < 3 and (not EX[k] or EX[k][-1][0] != stem):
                    m = ms[0]; a = max(0, m.start() - 60); b = min(len(t), m.end() + 60)
                    EX[k].append((stem, page, ctx, t[a:b][:160]))
        # structure (XPath-style) per article
        r = tree.getroot()
        def has(x): return r.xpath(x, namespaces={"mml": "http://www.w3.org/1998/Math/MathML", "xlink": "http://www.w3.org/1999/xlink"})
        langs = set()
        for ab in has("//abstract|//trans-abstract"):
            langs.add(ab.get("{http://www.w3.org/XML/1998/namespace}lang") or "main")
        if len(langs) >= 2: S["abstracts_2plus_langs"] += 1; SA["abstracts_2plus_langs"].add(stem)
        kl = set(k.get("{http://www.w3.org/XML/1998/namespace}lang") or "main" for k in has("//kwd-group"))
        if len(kl) >= 2: S["kwd_2plus_langs"] += 1; SA["kwd_2plus_langs"].add(stem)
        for name, x in [("contrib_2plus", "//contrib-group[count(contrib)>=2]"), ("aff", "//aff"), ("email_el", "//email"),
                        ("sec_with_number_in_title", "//sec/title"), ("xref_bibr", "//xref[@ref-type='bibr']"),
                        ("bold", "//bold"), ("italic", "//italic"), ("sup", "//sup"), ("sub", "//sub"), ("underline", "//underline"),
                        ("sc", "//sc"), ("table_foot", "//table-wrap-foot"), ("label_table", "//table-wrap/label"),
                        ("caption_fig", "//fig/caption"), ("caption_table", "//table-wrap/caption"),
                        ("person_group_editor", "//person-group[@person-group-type='editor']"),
                        ("person_group_translator", "//person-group[@person-group-type='translator']"),
                        ("edition_el", "//edition"), ("date_in_citation", "//date-in-citation"),
                        ("fn_in_table", "//table-wrap//xref[@ref-type='fn']"), ("named_quran", "//named-content[@content-type='quran']"),
                        ("lang_attr_blocks", "//body//*[@xml:lang]"), ("permissions", "//permissions"), ("funding_group", "//funding-group"),
                        ("author_notes", "//author-notes"), ("corresp", "//corresp"), ("ack", "//ack"), ("app", "//app"),
                        ("glossary", "//glossary"), ("def_list", "//def-list"), ("product", "//product"),
                        ("ext_link", "//ext-link"), ("pub_id_doi", "//pub-id[@pub-id-type='doi']"), ("contrib_id", "//contrib-id"),
                        ("subj_group", "//subj-group"), ("self_uri", "//self-uri"), ("issn", "//issn"), ("publisher_meta", "//journal-meta/publisher"),
                        ("article_doi", "//article-meta/article-id[@pub-id-type='doi']"), ("role", "//contrib/role"),
                        ("verse_group", "//verse-group"), ("disp_quote", "//disp-quote"), ("boxed", "//boxed-text"),
                        ("fig", "//fig"), ("fig_ink_only", "//fig[@specific-use='ink-without-text']"), ("table", "//table-wrap"),
                        ("math", "//mml:math"), ("disp_formula", "//disp-formula"), ("inline_formula", "//inline-formula"), ("list", "//list"), ("fn", "//fn"), ("ref", "//ref"),
                        ("endnotes", "//fn-group[@content-type='endnotes']"), ("history", "//history"),
                        ("trans_title_printed", "//trans-title-group"), ("subtitle", "//subtitle"),
                        ("kwd_printed", "//kwd-group[@kwd-group-type='author-printed']"), ("abstract_printed", "//abstract"),
                        ("metadata_change", "//custom-meta[meta-name='metadata-change']"), ("printed_date", "//custom-meta[meta-name='printed-date']"),
                        ("printed_journal", "//custom-meta[meta-name='printed-journal']"), ("added_text", "//*[@content-type='added']"),
                        ("parsed_citations_in_notes", "//p[@content-type='parsed-citations']"), ("series", "//series"),
                        ("name_alternatives", "//name-alternatives"), ("country", "//country"), ("city", "//addr-line[@content-type='city']"),
                        ("dept", "//institution[@content-type='dept']"), ("orgname", "//institution[@content-type='orgname']"),
                        ("translator_contrib", "//contrib[@contrib-type='translator']"), ("supervisor_contrib", "//contrib[@contrib-type='supervisor']"),
                        ("reviewer_contrib", "//contrib[@contrib-type='reviewer']"), ("inline_graphic", "//inline-graphic"),
                        ("text_in_figure", "//p[@content-type='text-in-figure']"), ("heading_level4", "//title[@content-type='heading-level-4']")]:
            n = len(has(x))
            if n: S[name] += n; SA[name].add(stem)
    out = {"files": len(FILES), "patterns": {}, "structure": {}}
    for k, _, _ in P:
        out["patterns"][k] = {"articles": len(A[k]), "n": C[k], "examples": EX[k]}
    for k in S:
        out["structure"][k] = {"articles": len(SA[k]), "n": S[k]}
    (HERE / "out").mkdir(exist_ok=True)
    json.dump(out, open(HERE / "out" / "master_counts.json", "w"), ensure_ascii=False, indent=1)
    for k, v in out["patterns"].items():
        print(f"{k:32s} {v['articles']:4d} {v['n']:6d}  {v['examples'][0] if v['examples'] else ''}"[:330])
    print("--- structure")
    for k, v in sorted(out["structure"].items()):
        print(f"{k:32s} {v['articles']:4d} {v['n']:6d}")

if __name__ == "__main__":
    main()
