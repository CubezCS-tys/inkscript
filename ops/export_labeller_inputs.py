#!/usr/bin/env python3
"""labeller_inputs_v1: per catalogue record, the non-personal fields a subject labeller can use.

Asked for by the AI-Search session on 2026-11-22 for the owner's "library map" (subject categories for the whole
catalogue). One JSON line per record of /home/appuser/data/marc/marc.db (1,558,415 records), in record order.
No names of people are written: contributor roles are reduced to counts and yes/no flags.

Before running, read the database into memory gently so the scan does not load the shared hard disk:
    nice -n 19 ionice -c3 pv -q -L 25m /home/appuser/data/marc/marc.db > /dev/null
Run:  nice -n 19 ionice -c3 python3 ops/export_labeller_inputs.py
"""
import hashlib, json, os, re, sqlite3, time
from itertools import groupby

DB = "/home/appuser/data/marc/marc.db"
OUT = "/home/appuser/data/exports/library_map_v1"
IDS = "/home/appuser/inkscript/experiments/44_bucket_map/out"
AUTHOR = re.compile(r"^(مؤلف|م\. مشارك|author|auth|co[ .\-]*auth|co[ .\-]*author|co-auteur)", re.I)
EDITOR_OF_TEXT = {"محقق"}
TRANSLATOR = re.compile(r"^(مترجم|translator|trans)$", re.I)
REVIEWER = re.compile(r"^(عارض|reviewer|rev)$", re.I)
INTERVIEWER = re.compile(r"^(محاور|dialoguer)$", re.I)
SUPERVISOR = re.compile(r"مشرف|advis|sup", re.I)


def grouped(cur):
    """rows ordered by rec -> iterator of (rec, [rows])"""
    return groupby(cur, key=lambda r: r[0])


class Side:
    """walks a rec-ordered grouped cursor beside the records cursor"""
    def __init__(self, it):
        self.it, self.cur = it, None
        self.step()

    def step(self):
        try:
            rec, rows = next(self.it)
            self.cur = (rec, list(rows))
        except StopIteration:
            self.cur = None

    def take(self, rec):
        while self.cur and self.cur[0] < rec:
            self.step()
        if self.cur and self.cur[0] == rec:
            rows = self.cur[1]
            self.step()
            return rows
        return []


def main():
    os.makedirs(OUT, exist_ok=True)
    path = f"{OUT}/labeller_inputs_v1.jsonl"
    if os.path.exists(path):
        raise SystemExit("labeller_inputs_v1.jsonl exists: write a v2 instead of changing it")
    t0 = time.time()
    main_ids = set(l.strip() for l in open(f"{IDS}/ids_main.txt"))
    legacy_ids = set(l.strip() for l in open(f"{IDS}/ids_legacy.txt"))
    con = lambda: sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    recs = con().execute("""select rec, c999, record_id, type, year, year_int, language, subtitle, pages, page_first,
                                   page_last, abstract_codes from records order by rec""")
    kw = Side(grouped(con().execute("select rec, seq, ar, en from keywords order by rec, seq")))
    au = Side(grouped(con().execute("select rec, seq, role from authors order by rec, seq")))
    ab = Side(grouped(con().execute("select rec, fseq, code, value from fields where tag = '520' order by rec, fseq, sseq")))
    pd = Side(grouped(con().execute("select rec, seq, stem from pdf_ids order by rec, seq")))
    n = 0
    counts = dict(subtitle=0, kw692=0, abstract=0, editor=0, translator=0, review=0, interview=0, ft_main=0, ft_legacy=0,
                  ft_none=0, pages=0)
    codes = {}
    h = hashlib.sha256()
    with open(path, "wb") as f:
        for rec, c999, rid, typ, year, yint, lang, subtitle, pages, pf, pl, acodes in recs:
            k = kw.take(rec)
            roles = [(r[2] or "").strip() for r in au.take(rec)]
            abst = {}
            for _, _, code, value in ab.take(rec):
                if value:
                    abst[code] = (abst[code] + " \\\\ " + value) if code in abst else value
            stems = [r[2] for r in pd.take(rec)]
            in_main = any(s in main_ids for s in stems)
            in_legacy = any(s in legacy_ids for s in stems)
            npages = None
            if isinstance(pf, int) and isinstance(pl, int) and 0 < pl - pf + 1 < 5000:
                npages = pl - pf + 1
            d = dict(rec=rec, c999=c999, record_id_001=rid, stems=stems, type=typ, year=year, year_int=yint, language=lang,
                     subtitle=subtitle or None,
                     keywords_692_ar=[r[2] for r in k if r[2]], keywords_692_en=[r[3] for r in k if r[3]],
                     abstract_codes=acodes or "", abstracts=abst,
                     has_editor_of_text=any(r in EDITOR_OF_TEXT for r in roles),
                     has_translator=any(TRANSLATOR.match(r) for r in roles),
                     is_review_by_role=any(REVIEWER.match(r) for r in roles),
                     has_interviewer=any(INTERVIEWER.match(r) for r in roles),
                     n_authors=sum(1 for r in roles if AUTHOR.match(r)),
                     n_supervisors=sum(1 for r in roles if SUPERVISOR.search(r)),
                     n_contributors=len(roles),
                     full_text="main" if in_main else "legacy" if in_legacy else "none",
                     full_text_in_both=in_main and in_legacy,
                     pages_raw=pages or None, page_count=npages)
            line = (json.dumps(d, ensure_ascii=False) + "\n").encode("utf-8")
            f.write(line); h.update(line); n += 1
            counts["subtitle"] += bool(subtitle); counts["kw692"] += bool(k); counts["abstract"] += bool(abst)
            counts["editor"] += d["has_editor_of_text"]; counts["translator"] += d["has_translator"]
            counts["review"] += d["is_review_by_role"]; counts["interview"] += d["has_interviewer"]
            counts["ft_" + d["full_text"]] += 1; counts["pages"] += npages is not None
            for c in abst:
                codes[c] = codes.get(c, 0) + 1
            if n % 200000 == 0:
                print(n, round(time.time() - t0), "s", flush=True)
    man = dict(file="labeller_inputs_v1.jsonl", rows=n, bytes=os.path.getsize(path), sha256=h.hexdigest(),
               built=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               source="marc.db (built 2026-10-20 from metadata_final.xml, 1,558,415 records) + the S3 listing of 2026-10-19 "
                      "(ids_main.txt 1,013,912 documents, ids_legacy.txt 308,593)",
               fields=dict(
                   subtitle="245 $b", keywords_692_ar="692 $a", keywords_692_en="692 $b",
                   abstracts="520 by subfield, as stored (paragraph breaks are ' \\\\ '): a = the article's Arabic abstract; "
                             "b = its English abstract; d = French abstract; e = an Arabic summary that reads as written by "
                             "the cataloguer ('استهدف المقال …'); f = an English summary of the same kind. The readings of "
                             "d, e and f are from looking at a few records each, not from documentation",
                   has_editor_of_text="a contributor with role «محقق»", has_translator="role «مترجم» / Translator",
                   is_review_by_role="role «عارض» / Reviewer", has_interviewer="role «محاور» / Dialoguer",
                   n_authors="contributors whose role is author or co-author (Arabic or Latin spellings)",
                   n_supervisors="roles matching «مشرف», Advisor, Super…", n_contributors="all 100/700/710 entries",
                   full_text="main = a PDF with Azure text in the archive; legacy = a PDF only, under legacy/; none = no file "
                             "of this record was in the bucket listing of 2026-10-19 (newer uploads are not seen)",
                   page_count="last page - first page + 1 where both are numbers in the pagination field"),
               no_personal_names=True, counts=counts, abstract_subfields=codes)
    json.dump(man, open(f"{OUT}/labeller_inputs_v1.manifest.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(dict(rows=n, GB=round(os.path.getsize(path) / 1e9, 2), sha=h.hexdigest()[:16], **counts, codes=codes),
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
