"""Experiment 54 step 5: experiment 53's first-page check on a sample of each candidate's Word-route articles.
A Word file whose first page number (the body's sectPr pgNumType/@start, as docx53 reads it) differs from the
catalogue's first page is likely another article (exp 53: 17 of 17 caught). .docx are read in place; .doc are converted
by soffice (batches, own profile) into out/wordcheck/. Read-only under /home/adminuser. -> out/wordcheck.json

    python wordcheck54.py CODE [CODE ...] [--n 15]"""
import csv, json, random, re, subprocess, sys, zipfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
AI = Path("/home/adminuser/ai_data")
OUT = HERE / "out/wordcheck"; OUT.mkdir(parents=True, exist_ok=True)
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

def page_start(docx):
    try:
        with zipfile.ZipFile(docx) as z:
            x = z.read("word/document.xml").decode("utf8", "ignore")
    except Exception as e:
        return "unreadable"
    # the body's own sectPr is the last one in the document (docx53 reads body/w:sectPr)
    secs = re.findall(r"<w:sectPr\b.*?</w:sectPr>", x, re.S)
    if not secs: return None
    m = re.search(r'<w:pgNumType\b[^>]*w:start="(\d+)"', secs[-1])
    return int(m.group(1)) if m else None

args = [a for a in sys.argv[1:] if not a.startswith("--")]
n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 15
if "--n" in sys.argv: args.remove(str(n))
rows = [r for r in csv.DictReader(open(HERE / "out/articles.tsv"), delimiter="\t")
        if r["journal_code"] in args and r["route"] == "word" and 2010 <= int(r["year"]) <= 2025]
res = json.load(open(HERE / "out/wordcheck.json")) if (HERE / "out/wordcheck.json").exists() else {}
for code in args:
    todo = []
    rs = sorted((r for r in rows if r["journal_code"] == code), key=lambda r: r["rec"])
    random.Random(5454).shuffle(rs)
    for r in rs[:n]:
        stem = r["stems"].split(",")[0]
        files = r["word"].split(",")
        folder, ext = files[0].split("/")
        dx = [f for f in files if f.endswith("/docx")]
        if dx:
            todo.append((r, stem, AI / dx[0].split("/")[0] / "docs" / f"{stem}.docx", None))
        else:
            todo.append((r, stem, OUT / f"{stem}.docx", AI / folder / "docs" / f"{stem}.{ext}"))
    need = [t for t in todo if t[3] is not None and not t[2].exists()]
    for i in range(0, len(need), 20):
        b = need[i:i + 20]
        subprocess.run(["soffice", f"-env:UserInstallation=file://{OUT}/profile", "--headless", "--convert-to", "docx",
                        "--outdir", str(OUT)] + [str(t[3]) for t in b], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=1800)
    res[code] = {}
    for r, stem, p, src in todo:
        ps = page_start(p) if p.exists() else "missing"
        res[code][stem] = dict(year=int(r["year"]), cat_first=r["page_first"], word_start=ps, from_doc=src is not None)
    (HERE / "out/wordcheck.json").write_text(json.dumps(res, ensure_ascii=False, indent=0))
    v = res[code].values()
    ok = sum(1 for x in v if str(x["word_start"]) == str(x["cat_first"]))
    bad = sum(1 for x in v if isinstance(x["word_start"], int) and str(x["word_start"]) != str(x["cat_first"]))
    print(code, "checked", len(v), "same first page", ok, "different", bad, "no number", len(v) - ok - bad, flush=True)
