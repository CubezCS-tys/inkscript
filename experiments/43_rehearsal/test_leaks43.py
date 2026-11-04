"""Experiment 65: the identifier patterns, the role split, the twin's parts and the v3.6 schema (no calls, no data)."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "41_azure_structure"))
import leaks43 as LK  # noqa: E402
import meta43  # noqa: E402

L = "{http://www.w3.org/XML/1998/namespace}lang"


def kinds(text):
    return [(x["kind"], x["value"], x["valid"]) for x in LK.find_all(text)]


# ------------------------------------------------------------------------------------------------ patterns
def test_orcid_checksum_and_forms():
    assert LK.orcid_ok("0000-0002-1825-0097") and LK.orcid_ok("0000-0002-1694-233X")
    assert not LK.orcid_ok("0000-0002-1825-0098")
    # 0130-027-105-003 p25-26: the summary page's ORCIDs, one printed with spaces round the dashes
    assert kinds("ORCID iD: https://orcid.org/0000-0002-5805-3020") == [("orcid", "0000-0002-5805-3020", True)]
    assert kinds("ORCID iD: https://orcid.org/0000 - 0002 -5805 -3020") == [("orcid", "0000-0002-5805-3020", True)]
    # p26: its groups scrambled by the right-to-left line: found, fails its check (identifiers() then matches the
    # one order of its groups that is an ORCID printed elsewhere: 0009-0009-7054-0305)
    got = LK.find_all("ORCID iD: https://orcid.org/00090305-7054-0009-")
    assert got[0]["kind"] == "orcid" and not got[0]["valid"]
    assert LK.orcid_ok("0009-0009-7054-0305")
    # 16 digits with no ORCID word and no ORCID prefix are not an ORCID (a phone, a table's number)
    assert not [k for k in kinds("رقم 1234 5678 9012 3456") if k[0] == "orcid"]


def test_doi_article_and_spaces():
    assert kinds("Doi:10.29343/1-79-2") == [("doi", "10.29343/1-79-2", True)]
    assert kinds("Doi: 10.29343 / 1-105-3") == [("doi", "10.29343/1-105-3", True)]
    assert kinds("https://doi.org/10.34120/ajh.v43i170.3155.")[0][:2] == ("doi", "10.34120/ajh.v43i170.3155")
    # a doi.org link is a DOI, not a URL
    assert [k[0] for k in kinds("https://doi.org/10.1037/a0026645")] == ["doi"]


def test_issn_check_digit():
    assert LK.issn_ok("0378-5955") and LK.issn_ok("2049-3630") and not LK.issn_ok("0378-5956")
    got = LK.find_all("ISSN: 1110-5208  e-ISSN 2682-2709")
    assert [(x["kind"], x["value"]) for x in got] == [("issn", "1110-5208"), ("issn", "2682-2709")]
    assert got[1]["medium"] == "electronic"
    assert [x["valid"] for x in LK.find_all("ردمد ١١١٠-٥٢٠٨")] == [LK.issn_ok("1110-5208")]


def test_email_url_phone():
    assert kinds("E-mail: dr.ammar@ku.edu.kw") == [("email", "dr.ammar@ku.edu.kw", True)]
    assert kinds("البريد: a.zaouji @gmail.com")[0][:2] == ("email", "a.zaouji@gmail.com")
    assert kinds("http://www.khayma.com") == [("url", "http://www.khayma.com", True)]
    assert not [k for k in kinds("https://orcid.org/0000-0002-5805-3020") if k[0] == "url"]
    # Arabic-Indic digits in a phone (1634-000-010,011-013 p1)
    got = [k for k in kinds("تلفونات سكرتارية: ٠١٥٥٧٧١١١٨ - ٧٩٤٤٩٤ فاكس: ٨٣٧٧٨٣٨٩") if k[0] == "phone"]
    assert ("phone", "0155771118", True) in got and ("phone", "83778389", True) in got
    assert ("phone", "+96522222222", True) in kinds("Tel: +965 2222 2222")
    assert not [k for k in kinds("صفحة ١٢٣ من سنة ١٩٨٤") if k[0] == "phone"]


def test_section_cite_licence_lines():
    assert LK.SECTION.match("البحوث والدراسات") and LK.SECTION.match("المقالات")
    assert not LK.SECTION.match("البحوث والدراسات السابقة في التربية")
    assert LK.CITE.match("للاستشهاد: زوجي، أمينة (2019)") and LK.CITE.match("To cite this article: Safar, A.")
    assert LK.LICENSE.search("This is an open access article under the CC BY 4.0 license")
    assert LK.LICENSE.search("هذا البحث من نوع الوصول المفتوح مرخص بموجب رخصة المشاع الإبداعي")


# ------------------------------------------------------------------------------------------------ M1 / M6
def test_split_role():
    assert meta43.split_role("دكتور /") == ([], ["دكتور /"], "")
    assert meta43.split_role("بقلم الدكتور") == (["بقلم"], ["الدكتور"], "")
    assert meta43.split_role("أستاذ مساعد") == ([], [], "أستاذ مساعد")           # a rank, not an honorific
    assert meta43.split_role("Professor of Psychology") == ([], [], "Professor of Psychology")
    assert meta43.split_role("PhD Student in Sociology") == ([], [], "PhD Student in Sociology")
    assert meta43.split_role("أستاذ") == ([], [], "أستاذ")                      # the rank (Professor)
    assert meta43.split_role("الأستاذ") == ([], ["الأستاذ"], "")                # the title
    assert meta43.split_role("د. / أستاذ أصول تربية الطفل") == ([], ["د."], "أستاذ أصول تربية الطفل")
    assert meta43.split_role("أ. د") == ([], ["أ.", "د"], "")
    assert meta43.split_role("اسم المؤلف الرئيسي:") == (["اسم المؤلف الرئيسي"], [], "")   # a label, not a post


class _Mo:
    def __init__(self):
        self.stats = Counter()


def _contrib(xml):
    return etree.fromstring(xml)


def test_role_parts_and_prefix():
    c = _contrib('<contrib contrib-type="author" id="contrib1"><string-name>عيد الدسوقى</string-name></contrib>')
    meta43.role_parts(_Mo(), c, "دكتور /")
    pr = meta43.printed_form(c)
    assert pr.find("prefix").text == "دكتور /" and meta43.tx(pr) == "دكتور / عيد الدسوقى"
    assert meta43.tx(meta43.main_name(c)) == "عيد الدسوقى"
    c = _contrib('<contrib contrib-type="author" id="contrib1"><string-name>أمينة زوجي</string-name></contrib>')
    meta43.role_parts(_Mo(), c, "طالبة باحثة في علم الاجتماع")
    r = c.find("role")
    assert r.get("content-type") == "position" and r.text == "طالبة باحثة في علم الاجتماع"
    # the printed string is unchanged when its honorific is tagged
    c = _contrib('<contrib><name-alternatives><string-name>صلاح بخيت</string-name><string-name '
                 'specific-use="printed-on-the-page">د.صلاح بخيت</string-name></name-alternatives></contrib>')
    meta43.prefix_in_printed(c)
    pr = meta43.printed_form(c)
    assert pr.find("prefix").text == "د." and "".join(pr.itertext()) == "د.صلاح بخيت"


def test_twin_parts_kept_and_linked():
    ar = _contrib('<contrib id="contrib1"><name-alternatives><string-name>أمينة زوجي</string-name>'
                  '</name-alternatives><email>a.zaouji@gmail.com</email><aff>كلية علوم التربية</aff></contrib>')
    la = _contrib('<contrib id="contrib2"><string-name>Amina Zaouji</string-name><role content-type="position">'
                  'PhD Student in Sociology</role><aff>University of Mohamed V</aff><email>a.zaouji@gmail.com</email>'
                  '</contrib>')
    meta43.keep_twin_parts(ar, la, ar.find("name-alternatives"))
    affs = ar.findall("aff")
    assert len(affs) == 2 and affs[1].get(L) == "en" and affs[1].get("rid") == affs[0].get("id") == "contrib1-aff1"
    assert [(r.text, r.get(L)) for r in ar.findall("role")] == [("PhD Student in Sociology", "en")]
    assert len(ar.findall("email")) == 1                  # the same e-mail is not doubled


# ------------------------------------------------------------------------------------------------ prompt v3.6
def test_v36_schema_every_key_has_a_home():
    """Every key of v3.6's answer outline is read by the checker (enrich43.KNOWN / PRINTING_KEYS, metadata keys by
    masters41 / meta43) and written by leaks43 / meta43 (unknown-key drops were a leak cause, experiment 61)."""
    import enrich43
    import prompt43 as P
    full = re.sub(r":\s*W\b", ": {}", P.ENRICH_FULL_V36)
    E = json.loads(full)
    assert set(E) <= enrich43.KNOWN, set(E) - enrich43.KNOWN
    assert set(E["printings"][0]) <= set(enrich43.PRINTING_KEYS)
    pages = json.loads(P.ENRICH_PAGES_V36.split("   (the article")[0])
    assert set(pages) <= enrich43.KNOWN
    meta_keys = set(re.findall(r'"(\w+)":', P.META_FULL_V36.replace("{{", "{").replace("}}", "}")))
    homes = {"title", "subtitle", "authors", "name", "role", "position", "affiliation", "email", "aff_parts",
             "department", "institution", "city", "country", "abstract", "ar", "en", "keywords", "trans_titles",
             "lang", "history", "type", "text", "line", "journal", "volume", "issue", "year", "pages_printed",
             "language"}
    assert meta_keys <= homes, meta_keys - homes
    # the homes of the new keys exist in the code
    src = (HERE / "leaks43.py").read_text(encoding="utf-8")
    for k in ("doi", "license", "section", "printings"):
        assert f'"{k}"' in src
    assert 'au.get("position")' in (HERE / "meta43.py").read_text(encoding="utf-8")


def test_v36_check_keeps_new_keys():
    import enrich43
    lines = {"1:3": {"text": "البحوث والدراسات"}, "1:5": {"text": "Doi: 10.29343/1-79-2"},
             "1:40": {"text": "This work is licensed under CC BY 4.0"},
             "25:7": {"text": "Main Author Name: Prof. Ammar H. Safar (Corresponding Author)"},
             "25:8": {"text": "ORCID iD: https://orcid.org/0000-0002-5805-3020 E-mail: dr.ammar@ku.edu.kw"}}
    ans = {"enrich": {"doi": "10.29343/1-79-2", "license": ["1:40"], "section": ["1:3"],
                      "printings": [{"a": 1, "name": "Ammar H. Safar", "lines": ["25:7", "25:8"],
                                     "orcid": "0000-0002-5805-3020", "email": "dr.ammar@ku.edu.kw", "corresp": True,
                                     "bogus": 1}]}}
    log = {}
    enrich43.check(ans, lines, log)
    E = ans["enrich"]
    assert E["doi"] == "10.29343/1-79-2" and E["license"] == ["1:40"] and E["section"] == ["1:3"]
    p = E["printings"][0]
    assert p["orcid"] == "0000-0002-5805-3020" and p["corresp"] and p["lines"] == ["25:7", "25:8"]
    assert [d["key"] for d in log["enrich"]] == ["printings.bogus"]


def test_earlier_prompts_unchanged():
    import prompt43 as P
    assert P.PROMPTS["v3.5b"] == (P.PROMPT_V35B, P.META_FULL_V32)
    assert P.ENRICH["v3.5b"] == (P.ENRICH_FULL_V35, P.ENRICH_PAGES_V35)
    assert "position" not in P.META_FULL_V32 and "printings" not in P.PROMPT_V35B


def test_fold_keeps_arabic_letters():
    # the tashkeel class once swallowed every Arabic letter, so no Arabic name ever matched (found in the j0130 trial)
    assert LK.toks("د. يسري أحمد سيد عيسى") == ["يسري", "احمد", "سيد", "عيسي"]
    assert LK.fold("عَلِيّ") == "علي"
