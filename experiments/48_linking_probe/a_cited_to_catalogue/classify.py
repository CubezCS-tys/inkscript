"""Step 2: classify every cited work by type from its parsed fields and the printed citations of all its members."""
import json, re, collections
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/a_cited_to_catalogue/"
I = re.I
R = dict(
    thesis=re.compile(r"رسال[ةه] (?:ماجست|دكتور|جامعي|لنيل|مقدم|علمي)|رسائل جامعية|أطروح|اطروح|مذكر[ةه] (?:ماست|ماجست|تخرج|لنيل|مقدم|مكمل)|"
                      r"دبلوم الدراسات|بحث (?:ماجستير|دكتوراه)|\bthes[ie]s\b|th[eè]se\b|dissertation|m[ée]moire (?:de|du|pour)|\bph\.? ?d\b|"
                      r"master'?s|doctoral|unpublished (?:master|doctor)", I),
    conference=re.compile(r"مؤتمر|ندو[ةه]|ملتقى|ملتقي|يوم دراسي|أيام دراسية|حلق[ةه] (?:نقاشية|دراسية)|\bconferen|\bcongr[eè]s|\bcongreso|"
                          r"colloque|coloquio|symposi|proceedings|actes du|\bactas\b|workshop|s[ée]minaire|seminar|paper presented|"
                          r"communication pr[ée]sent|\bposter\b|meeting of", I),
    legal=re.compile(r"(?:ال)?قانون (?:رقم|المدني|الجنائي|العقوبات|الأساسي|الاساسي|التجاري|الإجراءات|الاجراءات|الأحوال|الاحوال|العمل) |"
                     r"قانون رقم|مرسوم|(?<!جريدة )الدستور (?:ال|لسنة|المصري|الجزائري|المغربي|التونسي|الأردني)|الجريد[ةه] الرسمي|الرائد الرسمي|الوقائع المصري|ظهير|قرار (?:رقم|وزاري|مجلس|جمهوري)|"
                     r"أمر رقم|امر رقم|محكم[ةه] (?:النقض|التمييز|العدل|الاستئناف|الإدارية|العليا|الدستورية)|طعن رقم|نقض مدني|"
                     r"\blaw no|\bact,? \d{4}|d[ée]cret|\bloi n|code (?:civil|p[ée]nal)|official gazette|journal officiel|"
                     r"\baffaire\b|\barr[eê]t\b|judgment|resolution \d|اتفاقي[ةه] (?:الأمم|جنيف|فيينا|لاهاي|حقوق|الأمم)|"
                     r"نظام [^،,]{0,30}الصادر|لائح[ةه] (?:تنفيذية|رقم)", I),
    web=re.compile(r"https?://|www\.|\.(?:com|org|net|gov|edu)\b|متاح على|على الرابط|على الموقع|الموقع الإلكتروني|موقع (?:إلكتروني|الكتروني)|"
                   r"retrieved|accessed|available (?:at|from|on)|consult[ée] le|disponible sur|\bonline\b|blog|facebook|youtube|wikipedia|ويكيبيديا", I),
    report=re.compile(r"تقرير|التقرير|\breport\b|\brapport\b|informe\b|working paper|ورق[ةه] عمل|نشر[ةه] (?:إحصائي|احصائي)|إحصاءات|احصاءات|"
                      r"الكتاب الإحصائي|بيانات غير منشورة|الجهاز المركزي|statistic|annual|world bank|البنك الدولي|\bimf\b|unesco|unicef|undp|"
                      r"\bfao\b|\boecd\b|who\b|united nations|الأمم المتحدة|policy (?:brief|paper)|discussion paper|white paper|document de travail", I),
    news=re.compile(r"(?<![ء-ي])(?:جريد[ةه]|صحيف[ةه])(?![ء-ي])|newspaper|\bdaily\b|^le monde\b|le figaro|the guardian|al-?ahram|^الأهرام|^الاهرام|"
                    r"^الشرق الأوسط|الحياة اللندنية|\btimes\b|\bmonitor\b", I),
    turath_strong=re.compile(r"\(?ت\s?[\.:]?\s?\d{2,4}\s?ه|المتوفى|المتوفي|\(\s?\d{2,4}\s?هـ\s?[-–]\s?\d{2,4}\s?هـ|\d{2,4}\s?هـ\s?\)\s?[،,]|"
                             r"(?<![ء-ي])(?:تحقيق|وتحقيق|بتحقيق|تح\s?:|حققه|ضبطه|علق عليه|صححه)(?![ء-ي])", I),
    turath_title=re.compile(r"^(?:صحيح|سنن|مسند|الموطأ|موطأ|لسان العرب|تاج العروس|القاموس المحيط|مختار الصحاح|الصحاح|العين|الكتاب|"
                            r"مقاييس اللغة|معجم مقاييس|تهذيب اللغة|جمهرة|الأغاني|وفيات الأعيان|تاريخ الطبري|البداية والنهاية|"
                            r"الكامل في|المقدمة|مقدمة ابن خلدون|الخصائص|المغني|شرح ابن عقيل|أوضح المسالك|الإنصاف في|البيان والتبيين|"
                            r"الحيوان|العقد الفريد|نفح الطيب|معجم البلدان|سير أعلام|تفسير|الجامع لأحكام|فتح الباري|المستدرك|"
                            r"الإتقان|البرهان في علوم|المحرر الوجيز|الكشاف|مفاتيح الغيب|روح المعاني|جامع البيان|ديوان|المعلقات|"
                            r"الفهرست|كشف الظنون|خزانة الأدب|الإحاطة|المقامات|مقامات|الرسالة|إحياء علوم|المستصفى|الموافقات)(?![ء-ي])", I),
    journal_src=re.compile(r"مجل[ةه]|حوليات|حولية|دوري[ةه]|journal|revue|review|bulletin|annales|annals|quarterly|studies|cahiers|"
                           r"\bjr\.|\bj\. |trans(?:actions)?\.|magazine|مجلّة", I),
    vol_issue=re.compile(r"(?:مج|المجلد|مجلد|ع|العدد|عدد|vol\.?|volume|no\.?|n°|nº|issue)\s?\.?\s?\d+|\d+\s?\(\d+\)", I),
    book_pub=re.compile(r"دار |مكتب[ةه] |مطبع[ةه]|منشورات|المطبعة|الناشر|ط\s?\d|الطبعة|press\b|publish|verlag|[ée]ditions?|edition|ed\.|"
                        r"\bisbn|الهيئة المصرية العامة للكتاب|عالم الكتب|المؤسسة الجامعية|مؤسسة الرسالة", I),
)
TYPES = ["journal_article", "book", "thesis", "chapter", "conference_paper", "turath", "website", "report", "legal", "news", "other"]
CATALOGUE_TYPES = {"journal_article", "thesis", "conference_paper"}

def text_of(w):
    ms = sorted(w["members"], key=lambda m: -len(m["printed"] or ""))
    return " ‖ ".join(m["printed"] or "" for m in ms[:3])

def classify(w):
    t = text_of(w)
    p = next((m["parsed"] for m in sorted(w["members"], key=lambda m: -len(m["printed"] or "")) if m["parsed"]), {}) or {}
    pt = w["pub_type"]; src = p.get("source_title") or ""; title = w["title"] or ""
    why = []
    def hit(k, s=t):
        m = R[k].search(s or "")
        if m: why.append(f"{k}:{m.group(0)}")
        return bool(m)
    if pt == "thesis" or hit("thesis"):
        return "thesis", why or ["parsed:thesis"]
    if hit("conference"):
        return "conference_paper", why
    if hit("legal", title + " ‖ " + t[:300]):
        return "legal", why
    if w["lang"] == "ara" and (hit("turath_strong") or hit("turath_title", title.lstrip("«\"' ")) or
                              (w.get("year_calendar") == "hijri" and (w.get("year_hijri") or 9999) < 1300)):
        if not hit("journal_src", src):
            return "turath", why or ["hijri year < 1300"]
    journalish = pt == "journal" or hit("journal_src", src) or (hit("vol_issue") and pt not in ("book",))
    if (hit("news", src) or R["news"].search(t[:200]) and "جريد" in t[:200] or "صحيف" in t[:200]) and not hit("journal_src", src):
        return "news", why
    if pt == "chapter":
        return "chapter", why or ["parsed:chapter"]
    if journalish and (pt in ("journal",) or src):
        return "journal_article", why or ["parsed:journal"]
    if hit("report", title + " ‖ " + src + " ‖ " + t[:300]):
        return "report", why
    if pt == "web" or hit("web"):
        return "website", why or ["parsed:web"]
    if pt == "book" or hit("book_pub"):
        return "book", why or ["parsed:book"]
    if journalish:
        return "journal_article", why
    return "other", why or [f"parsed:{pt}"]

if __name__ == "__main__":
    W = [json.loads(l) for l in open(OUT + "works.jsonl", encoding="utf-8")]
    C = collections.Counter(); M = collections.Counter(); X = collections.Counter()
    with open(OUT + "classified.jsonl", "w", encoding="utf-8") as f:
        for w in W:
            k, why = classify(w)
            C[k] += 1; M[k] += w["n_mentions"]; X[(w["pub_type"], k)] += 1
            f.write(json.dumps(dict(cited_work_pk=w["cited_work_pk"], cited_work_id=w["cited_work_id"], cls=k, why=why,
                                    lang=w["lang"], pub_type=w["pub_type"], n_mentions=w["n_mentions"]), ensure_ascii=False) + "\n")
    tot = sum(C.values())
    for k in TYPES: print(f"{k:18s} {C[k]:5d} {100*C[k]/tot:5.1f}%  mentions {M[k]}")
    print(sorted(X.items(), key=lambda x: -x[1])[:40])
