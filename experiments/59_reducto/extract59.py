"""Experiment 59: Reducto Extract with our schemas -- references (citation pages) and metadata (page-1s).

    nice -n 10 /home/appuser/inkscript/.venv/bin/python extract59.py refs|meta std|deep [--workers 3]

Input = the page's r-1 Parse job (jobid://, so the text Extract reads is the r1 run already scored), with
  std   standard Extract, citations on (page, box, source text per value), page image included in the context
  deep  Deep Extract (agentic loop that checks its own work), citations on, page image included
Outputs: out/extract/<schema>_<mode>/<page id>.json
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor

import common59 as C

OUT = C.OUT
S = {"type": "string"}
SN = {"type": ["string", "null"]}


def d(desc, t=None):
    x = dict(t or SN)
    x["description"] = desc
    return x


PERSON = {"type": "object", "properties": {
    "name_as_printed": d("the person's name exactly as printed, including any title or honorific"),
    "surname": d("family name / laqab / nisba as printed (for Arabic names in 'X، Y' order: the part before the comma)"),
    "given_names": d("given names as printed, without titles such as د. أ.د. الدكتور Dr Prof"),
}}
REF_SCHEMA = {"type": "object", "properties": {"references": {
    "type": "array",
    "description": "Every cited work on this page: each entry of a reference list, and each work cited in a footnote "
                   "(a footnote that cites two works gives two entries; a footnote that only refers back with "
                   "'المصدر السابق' / 'نفسه' / 'op. cit.' / 'ibid.' and no title gives an entry with is_back_reference true).",
    "items": {"type": "object", "properties": {
        "raw_text": d("the text of this one citation exactly as printed, letter for letter (no translation, no normalisation)"),
        "where": d("'footnote' or 'reference_list'"),
        "note_or_list_number": d("the footnote number or list number printed before the citation, as printed"),
        "work_type": d("book, journal_article, chapter, thesis, conference, web, newspaper, law, manuscript, other"),
        "authors": {"type": "array", "items": PERSON, "description": "authors in printed order"},
        "title": d("title of the cited work itself (article, chapter or book title), as printed, without quotes"),
        "container_title": d("journal, newspaper, website, proceedings or book that contains the cited article/chapter; null for a whole book"),
        "edition": d("edition as printed, e.g. 'ط٢', 'ط. 2', '2nd ed.'"),
        "editors": {"type": "array", "items": S, "description": "editors as printed (تحقيق / تحرير / ed. / eds.)"},
        "translators": {"type": "array", "items": S, "description": "translators as printed (ترجمة / تعريب / trans.)"},
        "publisher": d("publisher as printed"),
        "place": d("place of publication as printed"),
        "year_as_printed": d("the year (or full date) as printed, with any هـ / م / AH mark, Arabic-Indic digits kept"),
        "year_gregorian": d("Gregorian year as 4 Western digits if printed or exactly derivable from the print, else null"),
        "year_hijri": d("Hijri year as Western digits if printed (هـ / AH), else null"),
        "volume": d("volume / part (ج، جـ، مج، المجلد، Vol., t.) as printed"),
        "issue": d("issue number (ع، العدد، No., nº) as printed"),
        "pages": d("pages cited or page range (ص، pp., p.) as printed"),
        "url": d("URL or DOI as printed"),
        "is_back_reference": d("true if this citation only points back to a work cited earlier", {"type": ["boolean", "null"]}),
    }}}}}
REF_PROMPT = ("This is one page of a scholarly journal article (Arabic, English or French). Extract citations exactly "
              "as printed: never translate, transliterate, correct spelling or change digits; keep Arabic-Indic digits "
              "and hamza, ى/ي and ة/ه as printed. Leave a field null when the print does not give it.")
META_SCHEMA = {"type": "object", "properties": {
    "title": d("the article's main title exactly as printed (the language it is printed in first)"),
    "title_other_language": d("a translated title printed on this page in another language, if any"),
    "authors": {"type": "array", "description": "the article's authors (and translators / reviewers if named), in printed order",
                "items": {"type": "object", "properties": {
                    "name_as_printed": d("the name exactly as printed, with any title or honorific"),
                    "name": d("the name without titles or honorifics (د. أ.د. أ.م.د. الدكتور الأستاذ الشيخ Dr Prof Pr)"),
                    "role": d("author, translator, reviewer, supervisor, editor or rapporteur, from the printed role word"),
                    "faculty_or_department": d("faculty / college / department / institute of this person as printed"),
                    "organisation": d("university or organisation of this person as printed"),
                    "city": d("city as printed"),
                    "country": d("country as printed, or null if not printed"),
                    "email": d("email as printed"),
                }}},
    "abstract": d("the abstract (ملخص / مستخلص / Abstract / Résumé) text exactly as printed on this page, null if none"),
    "abstract_other_language": d("a second abstract in another language on this page, if any"),
    "keywords": {"type": "array", "items": S, "description": "keywords as printed (الكلمات المفتاحية / Keywords / Mots-clés)"},
    "journal": d("journal name as printed on this page"),
    "volume": d("volume as printed"),
    "issue": d("issue as printed"),
    "year_as_printed": d("publication year or date as printed (with هـ / م if printed)"),
    "year_gregorian": d("Gregorian year as 4 Western digits if printed or exactly derivable from the print"),
    "year_hijri": d("Hijri year as Western digits if printed"),
    "first_page": d("the page number printed on this page"),
}}
META_PROMPT = ("This is the first page of a scholarly journal article from an Arabic-language database (it may be in "
               "Arabic, English or French). Extract the article's own metadata exactly as printed: never translate, "
               "transliterate or correct; keep Arabic-Indic digits and letters as printed. Running heads and the "
               "journal's masthead are not the article's title. Leave a field null when the page does not give it.")
SCHEMAS = {"refs": (REF_SCHEMA, REF_PROMPT, "cites"), "meta": (META_SCHEMA, META_PROMPT, "meta")}


def one(u, schema, mode):
    f = OUT / "extract" / f"{schema}_{mode}" / f"{u['id']}.json"
    if f.exists():
        return "skip"
    pj = json.loads((OUT / "reducto" / "r1" / f"{u['id']}.json").read_text())
    sch, prompt, _ = SCHEMAS[schema]
    body = {"instructions": {"schema": sch, "system_prompt": prompt},
            "settings": {"citations": {"enabled": True, "numerical_confidence": True}, "include_images": True,
                         "deep_extract": mode == "deep"}}
    st, j = C.extract(f"jobid://{pj['job_id']}", body, tag=f"extract_{schema}_{mode}", page_id=u["id"])
    if st != 200:
        return f"error {st} {json.dumps(j)[:300]}"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j, ensure_ascii=False))
    return f"ok {j.get('duration') or 0:.1f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schema", choices=list(SCHEMAS))
    ap.add_argument("mode", choices=["std", "deep"])
    ap.add_argument("--ids", default="")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    units = [u for u in json.loads((OUT / "units59.json").read_text()) if SCHEMAS[a.schema][2] in u["sets"]]
    if a.ids:
        units = [u for u in units if u["id"] in a.ids.split(",")]
    with ThreadPoolExecutor(a.workers) as ex:
        for u, r in zip(units, ex.map(lambda u: one(u, a.schema, a.mode), units)):
            print(u["id"], r, flush=True)
    print(f"list-price $ so far: {C.credits_used():.3f}")


if __name__ == "__main__":
    main()
