"""Mandumah's library catalogue as the article's front matter (experiment 29).

    cat = open_catalogue()                 # the cached index, or None (no index: the page alone decides, as before)
    rec = cat.get("0048-002-007-009")      # the record of one document (dict), or None
    meta = structure.read_meta(stem, dirs, catalogue=cat)   # -> meta["catalogue"] = rec

The catalogue is the corpus's MARC 21 XML export (s3://mandumah-source-docs/metadata/metadata_final.xml.gz,
1.17 GB gzipped, 1,558,415 records on 2026-08-27), one record per article (theses have one record for several
PDFs). Its people made it from the article, so it is the best source of what the article is called and who wrote
it; it does not say where those words are printed. structure._front therefore asks the page for the ink: the
catalogue's title and names are aligned to Azure's words (as Gemini's title file is), the honorific printed before
a name goes into <prefix>, the affiliation printed under it into <aff>, and each element says where it came from.

What each MARC field becomes (fields read on all 1.56M records and the 204 records of experiment 28's set; the
counts are records that have the field):

  001        record number (all)                          article-id pub-id-type="custom" custom-type="mandumah-record"
  024 $3     DOI, 10.34120/<id> (297k)                    article-id pub-id-type="doi"
  041 $a     language, ara / eng / fre (all)              article @xml:lang (ar / en / fr)
  044 $b     country of publication (1.39M)               publisher-loc (with 773 $d)
  100 $a     first author "Surname، Given" (1.50M)        contrib: name (surname, given-names), xml:lang="ar"
      $g $q  the name in Latin script (574k / 132k)       contrib: a second name, xml:lang="en"
      $e     role: مؤلف author                            contrib-type, role
      $9     Mandumah's authority number (all)            contrib-id contrib-id-type="mandumah-authority"
  110 $a     a body as author ("هيئة التحرير", 68k)        contrib: collab
  700        further people (653k), same subfields; $e: م. مشارك co-author, مترجم translator, مشرف supervisor,
             عارض presenter / reviewer of a book
  242, 246   the title in English ($a, $b) (91k, 497k)    trans-title-group xml:lang="en"
  245 $a $b  title, subtitle (all; $b 388k)               article-title, subtitle
  260 $b     publisher (1.39M)                            journal-meta publisher-name
      $c     year, Gregorian (all)                        pub-date calendar="gregorian"
      $m     year, Hijri (454k)                           pub-date calendar="islamic"
      $g     month: "أكتوبر", "يونيو / جمادى الاولى", "ربيع الثاني", a season (1.08M)   month / season of each pub-date
  300 $a     printed pages "184 - 238" (all)              fpage, lpage
  336 $a $b  kind of record: بحوث ومقالات / Article, Book Review, Conference Proceedings, Literary Text, Other
                                                          article-categories subj-group subj-group-type="mandumah-type"
  500 $a     a cataloguer's note (35k)                    custom-meta catalogue-note
  502        thesis: degree $b, university $c, faculty $f, country $g (170k)   custom-meta thesis
  520        abstracts: $a Arabic (569k), $b English (474k), $d French or other (33k), $e Arabic written by Mandumah
             (156k), $f English written by Mandumah (28k)                     abstract / trans-abstract
  653 $a     subject terms (8.6M terms)                   kwd-group kwd-group-type="subject-terms" xml:lang="ar"
  692 $a $b  keywords, Arabic with English (1.66M)        kwd-group kwd-group-type="keywords", ar and en
  773        the journal: $s title, $t / $e English title, $f romanised title, $o Mandumah journal code,
             $x ISSN (906k), $v volume, $l issue, $c article's place in the issue, $m volume and issue as printed
             ("مج34, ع390", "س 33, ع 4": year of the journal), $4 / $6 field of study (ar / en), $d place, $i body
             -> journal-meta (journal-title, trans-title, issn, publisher), volume, issue, subj-group "field"
  856 $u     the PDF(s): "<id>.pdf"; theses list several with $y ("صفحة العنوان", "24 صفحة الأولى") (3.20M)
                                                          the index key: every $u points at its record
      $n     the article on the publisher's site (74k)    self-uri content-type="publisher-landing-page"
  995 $a     Mandumah's database (HumanIndex, EduSearch…) custom-meta catalogue-database
  930, 999, 555   internal flags / counters: not used.
  Affiliations: none of the records holds one (no 100 $u); they come from the page.

The index: one SQLite file (1.10 GB): the PDF's id -> (block, position); the records' fields as compact JSON,
compressed 64 records at a time (one zlib stream per record made 2.33 GB). Built once from the XML, streamed
(7-18 minutes, at most 0.5 GB of memory), then opened read-only per document: 29 ms to open, 1.1 ms a lookup,
nothing loaded into memory. Default place ~/.cache/inkscript/catalogue/catalogue.sqlite (beside the cached schemas,
D20: machine-local data derived from a source outside git); $INKSCRIPT_CATALOGUE names another file ("none": off).

    python -m inkscript.enrich.catalogue build [--source FILE.xml.gz | s3://...] [--index FILE.sqlite]
    python -m inkscript.enrich.catalogue show <id>
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zlib
from pathlib import Path

S3_SOURCE = "s3://mandumah-source-docs/metadata/metadata_final.xml.gz"
MARC = "{http://www.loc.gov/MARC21/slim}"
BLOCK = 64                                      # records compressed together in the index
NAME_LEAST = 0.75                               # a catalogue name on the page: letters at least this alike (0.6 let
#                                                 "العربى عام" pass for «عصام العياش», experiment 29)
NAME_WIDE = 0.85                                # a short form of a name, or a name looked for outside the text
LANG = {"ara": "ar", "eng": "en", "fre": "fr", "fra": "fr", "ger": "de", "deu": "de", "spa": "es", "tur": "tr",
        "per": "fa", "fas": "fa", "urd": "ur", "heb": "he", "ita": "it"}
_BIDI = re.compile("[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def cache_dir() -> Path:
    return Path.home() / ".cache" / "inkscript" / "catalogue"


def default_index() -> Path:
    env = os.environ.get("INKSCRIPT_CATALOGUE")
    return Path(env).expanduser() if env else cache_dir() / "catalogue.sqlite"


# ---------------------------------------------------------------- reading MARC XML

def _clean(s: str | None, keep_lines: bool = False) -> str:
    s = _BIDI.sub("", s or "").replace("\r", "")
    if keep_lines:
        return "\n".join(" ".join(x.split()) for x in s.split("\n") if x.strip())
    return " ".join(s.split())


def _isbd(s: str) -> str:
    """'الإهدار التعليمي :' -> 'الإهدار التعليمي' (the catalogue's punctuation before a subtitle or a name's end)."""
    return re.sub(r"[\s:;/=,،.]+$", "", s).strip()


def parse_record(fields: list[tuple[str, list[tuple[str, str]]]]) -> tuple[list[str], dict]:
    """[(tag, [(code, value)])] of one record -> (the PDF ids it covers, the compact record)."""
    r: dict = {}

    def first(tag, code):
        for t, sf in fields:
            if t == tag:
                for c, v in sf:
                    if c == code and _clean(v):
                        return _clean(v)
        return ""

    def every(tag, code, lines=False):
        return [_clean(v, lines) for t, sf in fields if t == tag for c, v in sf if c == code and _clean(v)]

    r["id"] = first("001", "")
    r["doi"] = first("024", "3")
    r["lang"] = every("041", "a")
    r["country"] = first("044", "b")
    r["title"] = _isbd(first("245", "a"))
    r["subtitle"] = _isbd(first("245", "b"))
    en = [(t, sf) for t, sf in fields if t == "242"] or \
         [(t, sf) for t, sf in fields if t == "246" and re.search(r"[A-Za-z]", "".join(v for _, v in sf))]
    if en:
        sf = dict((c, _clean(v)) for c, v in reversed(en[0][1]))
        r["title_en"], r["subtitle_en"] = _isbd(sf.get("a", "")), _isbd(sf.get("b", ""))
    names = []
    for t, sf in fields:
        if t in ("100", "700", "110", "710"):
            d = {}
            for c, v in sf:
                v = _clean(v)
                if c == "a" and v:
                    d.setdefault("name", _isbd(v))
                elif c in "gq" and v and re.search(r"[A-Za-z]", v):
                    d.setdefault("latin", _isbd(v))
                elif c == "e" and v:
                    d.setdefault("role", _isbd(v))
                elif c == "9" and v:
                    d.setdefault("auth", v)
            if d.get("name"):
                d["tag"] = t
                if t in ("110", "710"):
                    d["org"] = 1
                names.append(d)
    names.sort(key=lambda d: d["tag"] not in ("100", "110"))    # the main entry first, then 700 in their order
    r["names"] = names
    r["publisher"] = first("260", "b")
    r["place"] = first("260", "a")
    r["year"] = first("260", "c")
    r["year_hijri"] = first("260", "m")
    r["month"] = first("260", "g")
    r["pages"] = first("300", "a")
    r["type"] = first("336", "a")
    r["type_en"] = first("336", "b")
    r["notes"] = every("500", "a")
    th = {c: first("502", c) for c in "bcfg"}
    if any(th.values()):
        r["thesis"] = {k: v for k, v in th.items() if v}
    abs_ = [(t_c, v) for t, sf in fields if t == "520" for t_c, v in sf if t_c in "abdef" and _clean(v)]
    r["abstracts"] = [[c, _clean(v, True)] for c, v in abs_]
    r["keywords"] = every("653", "a")
    terms = []
    for t, sf in fields:
        if t == "692":
            a = [_clean(v) for c, v in sf if c == "a" and _clean(v)]
            b = [_clean(v) for c, v in sf if c == "b" and _clean(v)]
            terms += [[x, b[i] if i < len(b) else ""] for i, x in enumerate(a)]
            if len(b) > len(a):
                terms += [["", x] for x in b[len(a):]]
    r["terms"] = terms
    j = {}
    for code, k in (("s", "title"), ("t", "title_en"), ("e", "title_en2"), ("f", "romanised"), ("o", "code"),
                    ("x", "issn"), ("v", "volume"), ("l", "issue"), ("c", "seq"), ("m", "printed"), ("d", "place"),
                    ("i", "body")):
        v = first("773", code)
        if v:
            j[k] = v
    for code, k in (("4", "fields"), ("6", "fields_en")):
        v = list(dict.fromkeys(every("773", code)))
        if v:
            j[k] = v
    r["journal"] = j
    files, links, stems = [], every("856", "n"), []
    for t, sf in fields:
        if t == "856":
            u = y = ""
            for c, v in sf:
                if c == "u":
                    if u:
                        files.append([u, y])
                        y = ""
                    u = _clean(v)
                elif c == "y":
                    y = _clean(v)
            if u:
                files.append([u, y])
    for u, y in files:
        s = re.sub(r"\.pdf$", "", u.strip(), flags=re.I)
        if s and s not in stems:
            stems.append(s)
    if len(files) > 1 or any(y for _, y in files):
        r["files"] = files
    r["links"] = links
    r["db"] = list(dict.fromkeys(every("995", "a")))
    return stems, {k: v for k, v in r.items() if v}


def _records(source):
    """Yield [(tag, [(code, value)])] for every record of a MARC XML file (.xml or .xml.gz, or a file object)."""
    from lxml import etree
    for _, el in etree.iterparse(source, events=("end",), tag=MARC + "record", huge_tree=True):
        fields = []
        for f in el:
            tag = f.get("tag")
            if f.tag == MARC + "controlfield":
                fields.append((tag, [("", f.text or "")]))
            elif f.tag == MARC + "datafield":
                fields.append((tag, [(s.get("code") or "", s.text or "") for s in f]))
        yield fields
        el.clear()
        while el.getprevious() is not None:
            del el.getparent()[0]


def _aws() -> str:
    for c in (Path(sys.executable).parent / "aws", shutil.which("aws")):
        if c and Path(c).exists():
            return str(c)
    raise FileNotFoundError("the aws CLI (to stream the catalogue from S3)")


def build(source=None, index: Path | None = None, log=print) -> dict:
    """Build the index from the MARC XML (a local .xml/.xml.gz, or an s3:// URL streamed with the aws CLI;
    default: the cached copy if there is one, else the bucket). Returns counts and times."""
    index = Path(index) if index else default_index()
    if source is None:
        local = cache_dir() / "metadata_final.xml.gz"
        source = str(local) if local.exists() else S3_SOURCE
    source = str(source)
    index.parent.mkdir(parents=True, exist_ok=True)
    tmp = index.with_suffix(".part")
    if tmp.exists():
        tmp.unlink()
    t0 = time.time()
    proc = None
    if source.startswith("s3://"):
        proc = subprocess.Popen([_aws(), "s3", "cp", source, "-"], stdout=subprocess.PIPE)
        stream = gzip.open(proc.stdout) if source.endswith(".gz") else proc.stdout
    else:
        stream = gzip.open(source) if source.endswith(".gz") else open(source, "rb")
    db = sqlite3.connect(tmp)
    db.execute("PRAGMA journal_mode=OFF")
    db.execute("PRAGMA synchronous=OFF")
    # records are stored BLOCK at a time, compressed together (one record alone compresses poorly: the index was
    # 1.5 GB with a zlib stream per record); a lookup decompresses one block
    db.execute("CREATE TABLE blk (bid INTEGER PRIMARY KEY, data BLOB)")
    db.execute("CREATE TABLE pdf (stem TEXT PRIMARY KEY, bid INTEGER, pos INTEGER) WITHOUT ROWID")
    db.execute("CREATE TABLE info (k TEXT PRIMARY KEY, v TEXT)")
    n = nstem = dup = nb = 0
    seen = set()
    block, batch_b, batch_p = [], [], []

    def flush():
        nonlocal block, nb
        if block:
            batch_b.append((nb, zlib.compress(json.dumps(block, ensure_ascii=False, separators=(",", ":")).encode(), 9)))
            nb += 1
            block = []
    with stream:
        for fields in _records(stream):
            stems, rec = parse_record(fields)
            n += 1
            if not stems:
                continue
            for s in stems:
                if s in seen:
                    dup += 1              # the same PDF in two records: the first is kept
                    continue
                seen.add(s)
                batch_p.append((s, nb, len(block)))
                nstem += 1
            block.append(rec)
            if len(block) >= BLOCK:
                flush()
            if len(batch_b) >= 500:
                db.executemany("INSERT INTO blk VALUES (?, ?)", batch_b)
                db.executemany("INSERT INTO pdf VALUES (?, ?, ?)", batch_p)
                batch_b.clear()
                batch_p.clear()
                log(f"  {n:,} records, {time.time() - t0:.0f} s")
    flush()
    db.executemany("INSERT INTO blk VALUES (?, ?)", batch_b)
    db.executemany("INSERT INTO pdf VALUES (?, ?, ?)", batch_p)
    if proc:
        proc.wait()
    st = Path(source).stat() if not source.startswith("s3://") else None
    info = dict(source=source, source_bytes=str(st.st_size) if st else "", records=str(n), pdfs=str(nstem),
                duplicate_pdfs=str(dup), built=time.strftime("%Y-%m-%d %H:%M:%S"), seconds=f"{time.time() - t0:.0f}")
    db.executemany("INSERT INTO info VALUES (?, ?)", list(info.items()))
    db.commit()
    db.close()
    tmp.replace(index)
    info["index_bytes"] = str(index.stat().st_size)
    return info


class Catalogue:
    """The index, opened read-only; get(stem) is one indexed read."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.db = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
        self.info = dict(self.db.execute("SELECT k, v FROM info"))

    def get(self, stem: str) -> dict | None:
        row = self.db.execute("SELECT b.data, p.pos FROM pdf p JOIN blk b ON b.bid = p.bid WHERE p.stem = ?",
                              (stem,)).fetchone()
        return json.loads(zlib.decompress(row[0]))[row[1]] if row else None

    def describe(self) -> str:
        return (f"Mandumah MARC catalogue ({self.info.get('records', '?')} records, index built "
                f"{self.info.get('built', '?')} from {Path(self.info.get('source', '?')).name})")


def open_catalogue(arg=None) -> Catalogue | None:
    """arg: None -> the default index if it exists (else None); "none"/"off"/False -> None; a .sqlite index;
    a MARC .xml / .xml.gz file -> its index in the cache, built first when missing or older than the file."""
    if arg is False or (isinstance(arg, str) and arg.lower() in ("none", "off", "no", "")):
        return None
    if arg is None:
        p = default_index()
        return Catalogue(p) if p.exists() else None
    p = Path(arg).expanduser()
    if p.suffix in (".sqlite", ".db"):
        if not p.exists():
            raise FileNotFoundError(p)
        return Catalogue(p)
    if not p.exists():
        raise FileNotFoundError(p)
    idx = cache_dir() / (re.sub(r"\.xml(\.gz)?$", "", p.name) + ".sqlite")
    if not idx.exists() or idx.stat().st_mtime < p.stat().st_mtime:
        build(p, idx)
    return Catalogue(idx)


# ---------------------------------------------------------------- names, dates, pages

def split_name(name: str) -> tuple[str, str]:
    """'المحجوب، عبدالمجيد' -> ('المحجوب', 'عبدالمجيد'); a name without a comma -> ('', name)."""
    parts = [x.strip() for x in re.split(r"[،,]", name, maxsplit=1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return "", name.strip()


def display_name(name: str) -> str:
    """The name as printed under a title: given names, then the surname."""
    s, g = split_name(name)
    return f"{g} {s}".strip() if s else g


ROLES = {"مؤلف": "author", "م. مشارك": "author", "مشارك": "author", "مترجم": "translator", "مشرف": "supervisor",
         "عارض": "presenter", "محرر": "editor", "محقق": "editor", "معد": "compiler", "مراجع": "reviewer"}


def contrib_type(role: str) -> str:
    return ROLES.get((role or "").strip(" ."), "author" if not role else "contributor")


_GMONTH = [("يناير", 1), ("كانونالثاني", 1), ("جانفي", 1), ("فبراير", 2), ("شباط", 2), ("فيفري", 2), ("مارس", 3),
           ("اذار", 3), ("ابريل", 4), ("افريل", 4), ("نيسان", 4), ("مايو", 5), ("مايس", 5), ("ايار", 5), ("ماي", 5),
           ("يونيو", 6), ("يونيه", 6), ("حزيران", 6), ("جوان", 6), ("يوليو", 7), ("يوليه", 7), ("تموز", 7),
           ("جويليه", 7), ("اغسطس", 8), ("اب", 8), ("اوت", 8), ("سبتمبر", 9), ("ايلول", 9), ("اكتوبر", 10),
           ("تشريناول", 10), ("تشرينالاول", 10), ("نوفمبر", 11), ("تشرينالثاني", 11), ("ديسمبر", 12),
           ("كانوناول", 12), ("كانونالاول", 12)]
_HMONTH = [("محرم", 1), ("صفر", 2), ("ربيعالاول", 3), ("ربيعاول", 3), ("ربيعالثاني", 4), ("ربيعالاخر", 4),
           ("ربيعثاني", 4), ("ربيعاخر", 4), ("جماديالاولي", 5), ("جماديالاول", 5), ("جمادياولي", 5),
           ("جماديالاخره", 6), ("جماديالثانيه", 6), ("جماديالثاني", 6), ("جماديثاني", 6), ("جماديالاخر", 6),
           ("رجب", 7), ("شعبان", 8), ("رمضان", 9), ("شوال", 10), ("ذوالقعده", 11), ("ذيالقعده", 11),
           ("ذوالحجه", 12), ("ذيالحجه", 12)]
_SEASON = {"ربيع": "Spring", "صيف": "Summer", "خريف": "Autumn", "شتاء": "Winter", "شتاء": "Winter"}


def months(g: str) -> dict:
    """'يونيو / جمادى الاولى' -> {'gregorian': 6, 'hijri': 5}; 'ربيع' (spring) -> {'season': 'ربيع'}."""
    from .quran import norm
    out = {}
    for part in re.split(r"[/\-–،,]| و ", g or ""):
        k = norm(part).replace(" ", "")
        if not k:
            continue
        h = next((m for name, m in sorted(_HMONTH, key=lambda x: -len(x[0])) if k.startswith(name)), None)
        if h and "hijri" not in out:
            out["hijri"] = h
            continue
        gm = next((m for name, m in sorted(_GMONTH, key=lambda x: -len(x[0])) if k == name or
                   (len(name) >= 4 and k.startswith(name))), None)
        if gm and "gregorian" not in out:
            out["gregorian"] = gm
            continue
        for name in ("ربيع", "صيف", "خريف", "شتاء"):
            if k.startswith(norm(name)) and "season" not in out:
                out["season"] = part.strip()
    return out


def page_range(pages: str) -> tuple[int, int] | None:
    """'184 - 238' -> (184, 238); '92' -> (92, 92); anything else None."""
    nums = [int(x) for x in re.findall(r"\d+", (pages or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))]
    if not nums or len(nums) > 2:
        return None
    a, b = nums[0], nums[-1]
    return (a, b) if b >= a else None


def num(v: str) -> str:
    """'034' -> '34'; '000' / '' -> ''; '071,072' (a double issue) -> '71-72'."""
    v = (v or "").strip()
    if "," in v and all(x.strip().isdigit() for x in v.split(",")):
        return "-".join(str(int(x)) for x in v.split(","))
    return str(int(v)) if v.isdigit() and int(v) > 0 else ("" if v.isdigit() else v)


def language(rec: dict) -> str | None:
    langs = [LANG.get(x.lower()[:3], "") for x in rec.get("lang", [])]
    langs = [x for x in langs if x]
    return langs[0] if langs else None


# ---------------------------------------------------------------- the front matter: catalogue + ink

def _name_variants(name: str) -> list[tuple[str, float]]:
    """The forms a catalogue name may be printed in, each with the letter similarity it needs on the page: given
    names then surname, the catalogue's order, and the first given name with the surname (the father's name left
    out; short, so it must match closely: "في ليالي" came within 0.8 of «فيصل بالي»)."""
    s, g = split_name(name)
    v = [(display_name(name), NAME_LEAST)]
    if s:
        v += [(f"{s} {g}", NAME_LEAST)]
        if len(g.split()) >= 2:
            v += [(f"{g.split()[0]} {s}", NAME_WIDE)]
    return list(dict.fromkeys(v))


AFF_OPEN = ("جامعه", "كليه", "قسم", "معهد", "مركز", "وزاره", "استاذ", "الاستاذ", "استاذه", "مدرس", "المدرس", "مدرسه",
            "باحث", "الباحث", "باحثه", "عضو", "رئيس", "محاضر", "عميد", "وكيل", "خبير", "مستشار", "university",
            "faculty", "department", "college")


def _aff_below(W, name_words, taken) -> list[int]:
    """The affiliation printed under a name: the next one or two lines of the same page that open with an
    institution or a post (جامعة، كلية، قسم، أستاذ، مدرس…), each at most 14 words."""
    from .quran import norm
    last = W[max(name_words)]
    pg, ln = last["page"], last["line"]
    lines = {}
    for w in W:
        if w["page"] == pg and ln < w["line"] <= ln + 2:
            lines.setdefault(w["line"], []).append(w)
    out = []
    for li in sorted(lines):
        ws = [w for w in lines[li] if w["idx"] not in taken]
        if not ws or len(ws) > 14 or len(ws) != len(lines[li]):
            break
        first = norm(ws[0]["out"].strip("()-–،,.:")) or ws[0]["out"].strip("()-–،,.:").lower()
        if not (first in AFF_OPEN or (out and li == W[out[-1]]["line"] + 1 and first[:2] in ("جا", "كل", "قس"))):
            break
        out += [w["idx"] for w in ws]
    return out


def front(doc, early, meta, page_front, align_authors) -> dict:
    """The front matter with the catalogue first. page_front(meta) is structure's reading of the page (Gemini's title
    file, else the layout); align_authors(words, exclude, names, source) aligns names to the ink. The catalogue's
    title and names win; the page gives their ink, the honorific and the affiliation."""
    from .structure import _align, key, sim, _split_honorific
    rec = meta["catalogue"]
    W = doc["words"]
    page = page_front(meta)                      # what the page alone says (kept for the comparison)
    out = dict(page)
    title_cat = rec.get("title", "")
    sub_cat = rec.get("subtitle", "")
    check = {}
    # the title's ink: the catalogue's title (with or without its subtitle) aligned to the first pages' words; a title
    # repeated as a running head is furniture, so page 1's furniture is searched too when the text has no match
    p0 = min(doc["pages"])
    p1_all = [w for w in W if w["page"] == p0]
    run, how, best = None, "", 0.0
    page_tw = page.get("title_words") or []
    page_title = page.get("title", "")
    variants = [(f"{title_cat} {sub_cat}", "with its subtitle"), (title_cat, "")] if sub_cat else [(title_cat, "")]
    if sub_cat:
        variants.append((sub_cat, "as its subtitle"))
    head = {w["idx"] for w in [x for x in early if x["page"] == p0][:60]}
    if title_cat:
        for words, least in ((early, 0.6), (p1_all, 0.7)):
            for variant, label in variants:
                if label == "as its subtitle":
                    continue                       # the subtitle alone only confirms the page's title (below)
                r = _align(words, variant, least)
                if not r:
                    continue
                got = sim(" ".join(W[k]["out"] for k in r), variant)
                # a weak match counts only where a title is printed: among page 1's first lines, or on the page's
                # own title (experiment 29: "الأديب التي" deep in the text matched «الادب ورسالته الروحية» at 0.62)
                if got < 0.75 and not (r[0] in head or set(r) & set(page_tw)):
                    continue
                if got > best:
                    run, best, how = r, got, label
            if run:
                break
        # the page's own title (Gemini's file or the layout) elsewhere than the catalogue's match: when it reads as
        # the catalogue's title, subtitle or both, its words are the title's ink (the match was a mention in the text)
        if page_tw and not (run and set(run) & set(page_tw)):
            pv = max(((sim(page_title, v), lab) for v, lab in variants), default=(0.0, ""))
            if pv[0] >= 0.6:
                run, best, how = list(page_tw), pv[0], (pv[1] or "") + " (the page's own title, confirmed)"
        if not run:                                # how close does anything come (for the disagreement check)
            r = _align(early, title_cat, 0.0)
            best = sim(" ".join(W[k]["out"] for k in r), title_cat) if r else 0.0
    check["title_match"] = round(best, 2)
    if run and page_tw and not set(run) & set(page_tw) and page_title:
        check["page_title_differs"] = page_title       # e.g. the catalogue names the article by its rubric
        check["page_title_source"] = page.get("title_source", "")
    people = rec.get("names", [])
    # the names as the page prints them: given names then surname, or the catalogue's order, whichever the ink
    # matches best (outside the title's words)
    tw0 = set(run or page.get("title_words", []))
    names = []
    for p in people:
        if p.get("org"):
            names.append(p["name"])
            continue
        rest = [w for w in early if w["idx"] not in tw0]
        best_v, best_r = display_name(p["name"]), 0.0
        for v, least in _name_variants(p["name"]):
            r = _align(rest, v, least)
            if r:
                s = sim(" ".join(W[k]["out"] for k in r), v)
                if s >= least and s > best_r:
                    best_v, best_r = v, s
        names.append(best_v)
    found = None
    if title_cat:
        if run:
            # the page read again with the catalogue in Gemini's place: the title's words given, the names aligned
            # after it, the rubric (short lines above the title) found against the right title
            cf = page_front(dict(meta, gemini=dict(title=title_cat, title_words=run, authors=names,
                                                   source="catalogue", least=NAME_LEAST)))
            out = dict(cf)
            found = cf.get("authors")
            out["title_words"] = run
            out["title_source"] = "catalogue (MARC 245), found on the page" + (f" {how}" if how else "")
            check["title"] = "found on the page"
        elif page.get("title_words") and max(sim(page_title, title_cat), sim(page_title, f"{title_cat} {sub_cat}")) >= 0.5:
            out["title_source"] = (f"catalogue (MARC 245); its ink from {page.get('title_source', 'the page')}, "
                                   f"which reads it close to the catalogue")
            check["title"] = "close to the page's"
        else:
            out.pop("title_words", None)
            out["title_source"] = "catalogue (MARC 245); not found on the page"
            check["title"] = "not found on the page"
            if page_title:
                check["page_title"] = page_title
        out["title"] = title_cat
        if sub_cat:
            out["subtitle"] = sub_cat
    # the people: the catalogue's names, each aligned to the ink, the honorific printed before it as the prefix,
    # the affiliation from the page's reading of the byline
    if people:
        tw = set(out.get("title_words", []))
        if found is None or len(found) != len(people):
            found = align_authors(early, tw, names, "catalogue", NAME_LEAST)
        # a name not in the first pages' text may be printed in what was set aside: a byline at the foot of the page
        # ("ترجمة: د. حمدي الزيات"), a footnote on the author, the title line ("الحقيقة والسياسة حنة آرندت"); looked for
        # there too, closely (NAME_WIDE), without a prefix
        found = [dict(a) for a in found]
        taken = tw | {k for a in found for k in a["words"] + a.get("prefix_words", [])}
        wide = [w for w in W if w["page"] <= p0 + 2][:700]
        tkey = key(f"{title_cat} {sub_cat}")
        for p, a in zip(people, found):
            if a["words"] or p.get("org"):
                continue
            # the title's ink may have taken a name printed on its line, when the catalogue's title has no name in it
            own = key(display_name(p["name"])) not in tkey and key(p["name"]) not in tkey
            pool = [w for w in wide if w["idx"] not in taken or (own and w["idx"] in tw and w["idx"] not in
                                                                  {k for b in found for k in b["words"]})]
            for v, _ in _name_variants(p["name"]):
                r = _align(pool, v, NAME_WIDE)
                if r and sim(" ".join(W[k]["out"] for k in r), v) >= NAME_WIDE:
                    t_ = out.get("title_words", [])
                    if set(r) & set(t_):
                        if len(r) >= len(t_) or not (t_[-len(r):] == r or t_[:len(r)] == r):
                            continue                   # inside the title: part of it, not a byline
                        out["title_words"] = [k for k in t_ if k not in set(r)]
                        tw = set(out["title_words"])
                    a.update(words=r, prefix_words=[], set_aside=True)
                    taken |= set(r)
                    break
        authors = []
        used = set()
        for p, a in zip(people, found):
            a = dict(a)
            a["catalogue"] = p
            a["name"] = display_name(p["name"]) if not p.get("org") else p["name"]
            if a["words"]:
                printed = " ".join(W[k]["out"] for k in a.get("prefix_words", []) + a["words"])
                a["prefix"] = _split_honorific(printed)[0] if a.get("prefix_words") else ""
                a["printed"] = printed
                a["source"] = f"catalogue (MARC {p['tag']}), found on the page" + (" (in a line set aside from the text: a byline at the foot, a note, the title's line)" if a.get("set_aside") else "")
            else:
                a["prefix"] = ""
                a["source"] = f"catalogue (MARC {p['tag']}); not found on the page"
            # the affiliation: the page's author whose words overlap this name's, or whose name is this one
            for pa in page.get("authors", []):
                if id(pa) in used:
                    continue
                same = (set(pa.get("words", [])) & set(a["words"])) or \
                       max(sim(pa.get("name", ""), v) for v, _ in _name_variants(p["name"])) >= 0.6
                if same:
                    used.add(id(pa))
                    other_name = any(sim(pa.get("aff", ""), v) >= 0.6 for q in people for v, _ in _name_variants(q["name"]))
                    letters = len(re.sub(r"[\W\d_]", "", pa.get("aff", "")))     # "(*)": a note marker, not a place
                    if pa.get("aff") and not set(pa.get("aff_words", [])) & set(a["words"]) and not other_name \
                            and letters >= 3:
                        a["aff"], a["aff_words"] = pa["aff"], pa.get("aff_words", [])
                        a["aff_source"] = pa.get("source", "the page")
                    if not a.get("prefix") and pa.get("prefix") and set(pa.get("words", [])) & set(a["words"]):
                        a["prefix"], a["prefix_words"] = pa["prefix"], pa.get("prefix_words", [])
                    break
            if a["words"] and not a.get("aff"):
                aff = _aff_below(W, a["words"], taken | {k for b in authors for k in b.get("aff_words", [])})
                if aff:
                    a["aff_words"], a["aff"] = aff, " ".join(W[k]["out"] for k in aff)
                    a["aff_source"] = "the page: the line(s) under the name, opening with an institution or a post"
            authors.append(a)
        persons = [a for a in authors if not a["catalogue"].get("org")]
        check["authors"] = f"{sum(1 for a in persons if a['words'])}/{len(persons)}"
        others = [pa.get("name", "") for pa in page.get("authors", []) if id(pa) not in used and pa.get("name")]
        if others:
            check["page_names_not_in_catalogue"] = others
        out["authors"] = authors
    # pages: the catalogue's range against the PDF
    rng = page_range(rec.get("pages", ""))
    n = len(doc["pages"])
    if rng:
        check["pages"] = f"{rng[1] - rng[0] + 1} in the catalogue, {n} in the PDF"
    # a wrong record? Calibrated by giving each of the 205 documents its neighbour's record (experiment 29,
    # wrong_record.py): a title found weakly (a phrase of the text, a table of contents) is believed only when the names
    # or the page count back it. Right records 200/204 "agrees", neighbours' records 0/204.
    persons = [p for p in people if not p.get("org")]
    names_found = sum(1 for a in out.get("authors", []) if a.get("words") and not a["catalogue"].get("org"))
    pages_fit = not rng or abs((rng[1] - rng[0] + 1) - n) <= max(2, 0.15 * (rng[1] - rng[0] + 1))
    found = check.get("title") in ("found on the page", "close to the page's")
    m = best
    if not title_cat:
        verdict = "no title in the record"
    elif found and (pages_fit and (m >= 0.75 or names_found and m >= 0.65 or not persons and m >= 0.7)
                    or m >= 0.9 and names_found or m >= 0.75 and names_found >= 2):
        verdict = "agrees"
        if check.get("page_title_differs") and check.get("page_title_source", "").startswith("gemini"):
            verdict = "agrees on the ink; Gemini's title file names another title (the catalogue may use the rubric)"
    elif found:
        verdict = "doubtful: the title matches only weakly and the names or the page count do not back it (wrong record?)"
    elif names_found or pages_fit and m >= 0.45:
        verdict = "partly: the title is not printed as catalogued"
    elif m < 0.45 and not names_found and persons and not pages_fit:
        verdict = "disagrees: the title, the names and the page count do not match this PDF (wrong record?)"
    else:
        verdict = "doubtful: the title is not found on the page"
    check["verdict"] = verdict
    out["catalogue"] = rec
    out["catalogue_check"] = check
    out["catalogue_desc"] = meta.get("catalogue_desc", "")
    out["page_front"] = dict(title=page_title, title_source=page.get("title_source", ""),
                             authors=[a.get("name", "") for a in page.get("authors", [])])
    return out


# ---------------------------------------------------------------- JATS pieces (jats.write's front matter)

def jats_journal_meta(E, jm, rec):
    """journal-title (+ English), ISSN, publisher, after journal-id."""
    j = rec.get("journal", {})
    if j.get("title"):
        jtg = E(jm, "journal-title-group")
        E(jtg, "journal-title", j["title"], specific_use="catalogue")
        en = j.get("title_en") or j.get("title_en2")
        if en:
            ttg = E(jtg, "trans-title-group", xml_lang="en")
            E(ttg, "trans-title", en)
        if j.get("romanised"):
            E(jtg, "abbrev-journal-title", j["romanised"], abbrev_type="romanised")
    if j.get("issn"):
        E(jm, "issn", j["issn"])
    if rec.get("publisher"):
        pub = E(jm, "publisher")
        E(pub, "publisher-name", rec["publisher"])
        loc = "، ".join(x for x in (j.get("place") or rec.get("place"), rec.get("country")) if x)
        if loc:
            E(pub, "publisher-loc", loc)


def jats_article_ids(E, am, rec):
    if rec.get("doi"):
        E(am, "article-id", rec["doi"], pub_id_type="doi")
    if rec.get("id"):
        E(am, "article-id", rec["id"], pub_id_type="custom", custom_type="mandumah-record",
          assigning_authority="Mandumah", specific_use="catalogue")


def jats_categories(E, ac, rec):
    j = rec.get("journal", {})
    if j.get("fields"):
        sg = E(ac, "subj-group", subj_group_type="field", specific_use="catalogue")
        for f in j["fields"]:
            E(sg, "subject", f)
    if j.get("fields_en"):
        sg = E(ac, "subj-group", subj_group_type="field", specific_use="catalogue",
               xml_lang="en")
        for f in j["fields_en"]:
            E(sg, "subject", f.replace("&amp;", "&"))
    if rec.get("type") or rec.get("type_en"):
        sg = E(ac, "subj-group", subj_group_type="mandumah-type", specific_use="catalogue")
        for f in (rec.get("type"), rec.get("type_en")):
            if f:
                E(sg, "subject", f)


def jats_trans_title(E, tg, rec):
    if rec.get("title_en"):
        ttg = E(tg, "trans-title-group", xml_lang="en")
        E(ttg, "trans-title", rec["title_en"])
        if rec.get("subtitle_en"):
            E(ttg, "trans-subtitle", rec["subtitle_en"])


def jats_contrib(E, cg, a, n, cid, append):
    """One contrib from a catalogue name (+ the page's prefix, printed form, affiliation)."""
    p = a["catalogue"]
    c = E(cg, "contrib", contrib_type=contrib_type(p.get("role", "")), id=cid, specific_use="catalogue")
    if p.get("auth"):
        E(c, "contrib-id", p["auth"], contrib_id_type="mandumah-authority")
    if p.get("org"):
        E(c, "collab", p["name"])
    else:
        s, g = split_name(p["name"])
        alts = p.get("latin") or a.get("printed")
        holder = E(c, "name-alternatives") if alts else c
        nm = E(holder, "name", name_style="western", xml_lang="ar")
        if s:
            E(nm, "surname", s)
            E(nm, "given-names", g)
        else:
            E(nm, "given-names", g)
        if a.get("prefix"):
            E(nm, "prefix", a["prefix"])
        if p.get("latin"):
            ls, lg = split_name(p["latin"])
            ln = E(holder, "name", name_style="western", xml_lang="en")
            if ls:
                E(ln, "surname", ls)
                E(ln, "given-names", lg)
            else:
                E(ln, "given-names", lg)
        if a.get("printed"):
            E(holder, "string-name", a["printed"], specific_use="printed-on-the-page")
    if p.get("role"):
        E(c, "role", p["role"].strip(), specific_use="catalogue")
    if a.get("aff"):
        E(c, "aff", a["aff"], specific_use="page")
    return c


def jats_dates(E, am, rec) -> bool:
    m = months(rec.get("month", ""))
    wrote = False
    for cal, y in (("gregorian", rec.get("year", "")), ("islamic", rec.get("year_hijri", ""))):
        ys = re.findall(r"\d{4}", y.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")))
        if not ys:
            continue
        pd = E(am, "pub-date", publication_format="print", date_type="pub", calendar=cal)
        mm = m.get("gregorian" if cal == "gregorian" else "hijri")
        if mm:
            E(pd, "month", str(mm))
        elif m.get("season") and cal == "gregorian":
            E(pd, "season", m["season"])
        E(pd, "year", ys[0])
        if cal == "gregorian" and (len(ys) > 1 or rec.get("month")):
            E(pd, "string-date", " ".join(x for x in (rec.get("month") if cal == "gregorian" else "", y) if x))
        wrote = True
    return wrote


def jats_after_pages(E, am, rec):
    """self-uri, abstracts, keywords (after fpage/lpage, before counts)."""
    for u in rec.get("links", []):
        E(am, "self-uri", u, content_type="publisher-landing-page", xlink_href=u)
    lang = language(rec) or "ar"
    title_k = re.sub(r"\W", "", rec.get("title", ""))
    abs_lang = {"a": "ar", "e": "ar", "b": "en", "f": "en", "d": None}
    items = []
    for code, text in rec.get("abstracts", []):
        if re.sub(r"\W", "", text) == title_k:
            continue                                   # the title repeated as an abstract
        lg = abs_lang.get(code)
        if lg is None:
            from .jats import _lang
            lg = _lang(text) or "ar"
            lg = "fr" if lg == "und" else lg
        items.append((lg, "mandumah" if code in "ef" else "author", text))
    # one <abstract> in the article's language (the author's before Mandumah's), then the others as <trans-abstract>
    items.sort(key=lambda x: (x[0] != lang, x[1] != "author"))
    for i, (lg, kind, text) in enumerate(items):
        el = E(am, "abstract" if i == 0 else "trans-abstract", abstract_type=kind, specific_use="catalogue",
               xml_lang=None if lg == "ar" else lg)
        for para in text.split("\n"):
            E(el, "p", para)
    if rec.get("keywords"):
        kg = E(am, "kwd-group", kwd_group_type="subject-terms", specific_use="catalogue",
               xml_lang="ar")
        for k in dict.fromkeys(rec["keywords"]):
            E(kg, "kwd", k)
    terms = rec.get("terms", [])
    for i, lg in ((0, "ar"), (1, "en")):
        ks = [t[i] for t in terms if t[i]]
        if ks:
            kg = E(am, "kwd-group", kwd_group_type="keywords", specific_use="catalogue",
                   xml_lang=lg)
            for k in dict.fromkeys(ks):
                E(kg, "kwd", k)


def jats_custom(rec, check, catalogue_desc=""):
    """(name, value) pairs for custom-meta."""
    out = []
    if catalogue_desc:
        out.append(("catalogue", catalogue_desc + f"; record {rec.get('id', '?')}"))
    if rec.get("lang"):
        out.append(("catalogue-language", ", ".join(rec["lang"]) + " (MARC 041; the article element keeps "
                    "xml:lang=\"ar\", Latin-script paragraphs carry their own)"))
    if check:
        parts = [f"verdict: {check.get('verdict', '')}", f"title {check.get('title', '-')} (match {check.get('title_match', 0)})"]
        if check.get("authors"):
            parts.append(f"names found on the page {check['authors']}")
        if check.get("pages"):
            parts.append("pages " + check["pages"])
        if check.get("page_title"):
            parts.append(f"the page's own title guess: «{check['page_title']}»")
        if check.get("page_title_differs"):
            parts.append(f"the page's own title ({check.get('page_title_source', '')}): «{check['page_title_differs']}»")
        if check.get("page_names_not_in_catalogue"):
            parts.append("names on the page not in the catalogue: " + "; ".join(check["page_names_not_in_catalogue"]))
        out.append(("catalogue-check", "; ".join(parts)))
    j = rec.get("journal", {})
    if j.get("printed"):
        out.append(("catalogue-volume-issue-as-printed", j["printed"]))
    if j.get("seq"):
        out.append(("catalogue-article-sequence", num(j["seq"]) or j["seq"]))
    for n in rec.get("notes", []):
        out.append(("catalogue-note", n))
    if rec.get("thesis"):
        t = rec["thesis"]
        out.append(("thesis", "، ".join(t[k] for k in "bcfg" if t.get(k))))
    if rec.get("db"):
        out.append(("catalogue-database", ", ".join(rec["db"])))
    if rec.get("files"):
        out.append(("catalogue-files", "; ".join(f"{u} ({y})" if y else u for u, y in rec["files"])))
    return out


# ---------------------------------------------------------------- command line

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m inkscript.enrich.catalogue")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the index from the MARC XML (local file or s3://)")
    b.add_argument("--source", default=None)
    b.add_argument("--index", default=None)
    s = sub.add_parser("show", help="print one document's record")
    s.add_argument("stem")
    s.add_argument("--index", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        info = build(a.source, Path(a.index) if a.index else None)
        print(json.dumps(info, indent=1))
        return 0
    cat = open_catalogue(a.index) if a.index else open_catalogue()
    if not cat:
        print("no catalogue index; build one with: python -m inkscript.enrich.catalogue build", file=sys.stderr)
        return 2
    rec = cat.get(a.stem)
    print(json.dumps(rec, ensure_ascii=False, indent=1) if rec else f"{a.stem}: not in the catalogue")
    return 0 if rec else 1


if __name__ == "__main__":
    sys.exit(main())
