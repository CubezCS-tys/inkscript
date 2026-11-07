"""Experiment 84, step B2a: the text of the synthetic display lines (running headers, journal names, article titles).

    nice -n 19 ionice -c3 python3 experiments/84_display_fonts/text84.py [N=400000]   -> out/text/display84.jsonl.gz

TRAINING-POOL journals only: the journal codes of experiment 83's plan83 (its training documents), minus the 27
held-out codes of split76 (experiment 81's test, lab documents 1-3), minus journal 0097 (named in the brief: never
trained on), minus the LOCKED final-test journals (locked.py; asserted).  No line containing 0097's header phrase
«العربية للتربية» is written, whatever journal it comes from (three training journals' names contain it).  The text is the catalogue's own (marc.db,
read only): journal names and article titles of those journals; no page is read.

Mixture (by line):
  header  40%: a running header: the journal's name with an issue and a date, in the orders and separators printed
          headers use (« - », « / », « | », «، »), Latin or Arabic-Indic digits, Gregorian or Syriac month names,
          sometimes a page number at one end;
  name    15%: the journal's name alone (as on a cover or a masthead);
  title   35%: an article title (cut at a word boundary to 2-12 words when long);
  section 10%: a section heading of the kind set in a display face (المقدمة, الملخص, ...), sometimes numbered.
"""
from __future__ import annotations

import gzip
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
from locked import assert_not_locked, is_locked  # noqa: E402

MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
OUT = HERE / "out/text"
NEVER = {"0097"}
# journal 0097's running header «المجلة العربية للتربية» (the test's failure case): three training-pool journals have
# names that contain it (0066, 0552, 1801); any line containing the phrase is left out, so the header is never shown
HDR97 = re.compile(r"العربية\s*لل?تربية")
MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "إبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر",
          "ديسمبر", "جانفي", "فيفري", "أفريل", "ماي", "جوان", "جويلية", "أوت", "كانون الثاني", "شباط", "آذار", "نيسان",
          "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول"]
SECTIONS = ["المقدمة", "مقدمة", "الملخص", "ملخص البحث", "مستخلص", "النتائج", "مناقشة النتائج", "التوصيات", "الخاتمة",
            "المراجع", "قائمة المراجع", "المصادر والمراجع", "مشكلة الدراسة", "أهداف البحث", "أهمية الدراسة",
            "منهج البحث", "الإطار النظري", "الدراسات السابقة", "فروض الدراسة", "حدود الدراسة", "مصطلحات الدراسة",
            "الفصل الأول", "المبحث الثاني", "المطلب الأول", "تمهيد", "افتتاحية العدد", "كلمة التحرير", "بحوث ودراسات",
            "عروض الكتب", "ملف العدد", "دراسات أدبية", "قضايا وآراء"]
AIN = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def num(rng, n):
    s = str(n)
    return s.translate(AIN) if rng.random() < 0.4 else s


def header(rng, name):
    y = rng.randint(1930, 2025)
    m = rng.choice(MONTHS)
    m2 = rng.choice(MONTHS)
    date = rng.choice([f"{m} {num(rng, y)}", f"{m}/{m2} {num(rng, y)}", f"{m} / {m2} {num(rng, y)}", num(rng, y),
                       f"{m} {num(rng, y)}م", f"{num(rng, rng.randint(1350, 1447))}هـ"])
    issue = rng.choice([f"العدد {num(rng, rng.randint(1, 400))}", f"العدد ({num(rng, rng.randint(1, 120))})",
                        f"المجلد {num(rng, rng.randint(1, 60))}، العدد {num(rng, rng.randint(1, 12))}",
                        f"المجلد ({num(rng, rng.randint(1, 60))}) العدد ({num(rng, rng.randint(1, 12))})",
                        f"السنة {num(rng, rng.randint(1, 60))}", f"ع {num(rng, rng.randint(1, 200))}", ""])
    sep = rng.choice([" - ", " – ", " / ", " | ", "، ", "  "])
    parts = [name] + [p for p in (issue, date) if p and rng.random() < 0.8]
    if len(parts) > 2 and rng.random() < 0.3:
        parts = [parts[0], parts[2], parts[1]]
    t = sep.join(parts)
    if rng.random() < 0.2:
        pg = num(rng, rng.randint(1, 400))
        t = rng.choice([f"{pg} | {t}", f"{t} | {pg}", f"{pg}  {t}", f"{t}  {pg}"])
    return t


def title(rng, t):
    w = t.split()
    if len(w) < 3:
        return t
    if len(w) > 12 or rng.random() < 0.25:
        k = rng.randint(2, min(12, len(w)))
        i = rng.randint(0, len(w) - k)
        w = w[i:i + k]
    return " ".join(w)


def main(n=400_000):
    rng = random.Random(84)
    held = set(json.loads((EXP / "76_finetune_pilot/out/split76.json").read_text())["test"])
    pool = {json.loads(l)["jcode"] for l in open(EXP / "83_reader_scale/out/data/plan83.jsonl", encoding="utf-8")}
    pool = {j for j in pool if j not in held and j not in NEVER and not is_locked(j)}
    c = sqlite3.connect(MARC, uri=True)
    names, titles = {}, []
    q = "select journal_code, journal, title from records where language = 'ara' and journal_code is not null"
    for jc, j, t in c.execute(q):
        if jc not in pool:
            continue
        if j:
            names.setdefault(jc, re.sub(r"\s+", " ", j).strip())
        if t and re.search("[ء-ي]", t) and 8 <= len(t) <= 300:
            titles.append((jc, re.sub(r"\s+", " ", t).strip()))
    assert_not_locked(list(names) + [jc for jc, _ in titles])
    assert not (set(names) & (held | NEVER))
    nm = [(jc, x) for jc, x in names.items() if re.search("[ء-ي]", x)]
    print(len(pool), "training-pool journals,", len(nm), "Arabic names,", len(titles), "titles")
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "display84.jsonl.gz", "wt", encoding="utf-8") as f:
        for _ in range(n):
            r = rng.random()
            if r < 0.40:
                jc, x = rng.choice(nm)
                t, src = header(rng, x), "header"
            elif r < 0.55:
                jc, x = rng.choice(nm)
                t, src = x, "name"
            elif r < 0.90:
                jc, x = rng.choice(titles)
                t, src = title(rng, x), "title"
            else:
                jc = ""
                t = rng.choice(SECTIONS)
                if rng.random() < 0.3:
                    t = f"{num(rng, rng.randint(1, 9))}. {t}" if rng.random() < 0.5 else f"{t}:"
                src = "section"
            if HDR97.search(t):                        # never 0097's header phrase, even from other journals' names
                continue
            f.write(json.dumps(dict(t=t, src=src, j=jc), ensure_ascii=False) + "\n")
    print("wrote", n)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 400_000)
