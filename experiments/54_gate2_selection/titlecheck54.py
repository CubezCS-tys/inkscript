"""Experiment 54 step 5b: for every Word file sampled by wordcheck54, does its opening text carry the catalogue title?
Share of the catalogue title's words (3+ letters, hamza/ta-marbuta folded) found in the file's first 3,000 characters.
Complements the first-page test, whose misses here are mostly one page off. -> adds title_share to out/wordcheck.json"""
import json, re, sqlite3, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
AI = Path("/home/adminuser/ai_data")
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
c = sqlite3.connect(MARC, uri=True)
F = str.maketrans("أإآٱىة", "اااايه")
def words(s):
    s = re.sub(r"[ً-ْـ]", "", s or "").translate(F)
    return [w for w in re.findall(r"\w+", s) if len(w) >= 3]
def text(p):
    with zipfile.ZipFile(p) as z:
        x = z.read("word/document.xml").decode("utf8", "ignore")
    return " ".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", x))[:3000]
wc = json.load(open(HERE / "out/wordcheck.json"))
for code, d in wc.items():
    for stem, x in d.items():
        r = c.execute("select r.title from pdf_ids p join records r on r.rec = p.rec where p.stem = ?", (stem,)).fetchone()
        p = HERE / "out/wordcheck" / f"{stem}.docx"
        if not p.exists():
            for f in ("journals", "ai_batch2", "ai_batch3"):
                q = AI / f / "docs" / f"{stem}.docx"
                if q.exists(): p = q; break
        try:
            t = set(words(text(p))); tw = words(r[0] if r else "")
            x["title_share"] = round(sum(w in t for w in tw) / len(tw), 2) if tw else None
        except Exception:
            x["title_share"] = None
(HERE / "out/wordcheck.json").write_text(json.dumps(wc, ensure_ascii=False, indent=0))
for code, d in wc.items():
    v = list(d.values())
    print(code, len(v), "title>=0.6:", sum(1 for x in v if (x.get("title_share") or 0) >= .6),
          [(s, x["cat_first"], x["word_start"], x.get("title_share")) for s, x in d.items()
           if str(x["word_start"]) != str(x["cat_first"]) or (x.get("title_share") or 0) < .6])
