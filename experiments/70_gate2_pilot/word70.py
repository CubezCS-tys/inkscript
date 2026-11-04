"""Experiment 70: the Word route for 0165's Word-only articles (experiment 53's code, pointed at this experiment's out/).

    .venv/bin/python experiments/70_gate2_pilot/word70.py prep      # .docx copied, .doc converted by soffice -> out/word/docx
    .venv/bin/python experiments/70_gate2_pilot/word70.py legacy    # S3 legacy/<stem>/<stem>.pdf (read only) -> out/word/legacy_pdf
    .venv/bin/python experiments/70_gate2_pilot/word70.py check     # first-page + title check -> out/word/check.json
    .venv/bin/python experiments/70_gate2_pilot/word70.py build     # code-only JATS (build53) for the accepted -> out/w0165_code/masters

The check (experiments 53 and 54): a Word file is the catalogue's article when its opening text (first 3,000
characters) carries at least 60% of the catalogue title's words (3+ letters, hamza / ta marbuta folded). The body's
first page number (pgNumType/@start) is recorded beside it: in exp 54 it was off by 1-3 pages on 25 of 30 right files,
so it never rejects a file alone; a file with a low title share is rejected (another article), and the page test
tells how far it is off. English-language records are checked against the record's title as well (the catalogue may
hold an Arabic title for an English article): the share is the better of the Arabic and the Latin words.
Read-only under /home/adminuser; soffice with its own profile, batches of 20, nice.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out" / "word"
WL = HERE / "out" / "word70.json"
F = str.maketrans("أإآٱىة", "اااايه")


def arts():
    return json.loads(WL.read_text(encoding="utf-8"))["articles"]


def cmd_prep():
    dx = OUT / "docx"
    dx.mkdir(parents=True, exist_ok=True)
    need = []
    for a in arts():
        s, fs = a["stem"], a["files"]
        if (dx / f"{s}.docx").exists():
            continue
        d = [f for f in fs if f.endswith(".docx")]
        if d:
            shutil.copy2(d[0], dx / f"{s}.docx")
        else:
            need.append(fs[0])
    print(len(need), ".doc to convert")
    for i in range(0, len(need), 20):
        b = need[i:i + 20]
        subprocess.run(["nice", "-n", "10", "soffice", f"-env:UserInstallation=file://{OUT}/profile", "--headless",
                        "--convert-to", "docx", "--outdir", str(dx)] + b, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=1800)
        print(f"  {min(i + 20, len(need))}/{len(need)}", flush=True)
    missing = [a["stem"] for a in arts() if not (dx / f"{a['stem']}.docx").exists()]
    print("missing after prep:", missing)


def cmd_legacy():
    lp = OUT / "legacy_pdf"
    lp.mkdir(parents=True, exist_ok=True)
    aws = str(ROOT / ".venv" / "bin" / "aws")
    ok = bad = 0
    for a in arts():
        s = a["stem"]
        if (lp / f"{s}.pdf").exists() and (lp / f"{s}.pdf").stat().st_size:
            ok += 1
            continue
        r = subprocess.run([aws, "s3", "cp", f"s3://mandumah-source-docs/legacy/{s}/{s}.pdf", str(lp / f"{s}.pdf"),
                            "--quiet"], capture_output=True)
        ok, bad = (ok + 1, bad) if r.returncode == 0 else (ok, bad + 1)
    print("legacy PDFs", ok, "missing", bad)


def words(s):
    s = re.sub(r"[ً-ْـ]", "", s or "").translate(F).lower()
    return [w for w in re.findall(r"\w+", s) if len(w) >= 3]


def doc_text_and_start(p: Path):
    with zipfile.ZipFile(p) as z:
        x = z.read("word/document.xml").decode("utf8", "ignore")
    secs = re.findall(r"<w:sectPr\b.*?</w:sectPr>", x, re.S)
    m = re.search(r'<w:pgNumType\b[^>]*w:start="(\d+)"', secs[-1]) if secs else None
    paras = re.findall(r"<w:p[ >].*?</w:p>", x, re.S)        # runs of a paragraph joined as Word draws them
    t = " ".join("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", q)) for q in paras)
    return t[:3000], (int(m.group(1)) if m else None)


def cmd_check():
    res, c = {}, Counter()
    for a in arts():
        s = a["stem"]
        p = OUT / "docx" / f"{s}.docx"
        if not p.exists():
            res[s] = dict(verdict="no file")
            c["no file"] += 1
            continue
        try:
            t, start = doc_text_and_start(p)
        except Exception as e:  # noqa: BLE001
            res[s] = dict(verdict="unreadable", error=repr(e))
            c["unreadable"] += 1
            continue
        tw, have = words(a["title"]), set(words(t))
        share = round(sum(w in have for w in tw) / len(tw), 2) if tw else None
        try:
            first = int(a["page_first"])
        except (TypeError, ValueError):
            first = None
        page = "no number" if start is None else ("same" if start == first else
                                                    f"off {start - first:+d}" if first is not None else "no catalogue page")
        verdict = "accept" if share is not None and share >= 0.6 else "reject"
        res[s] = dict(verdict=verdict, title_share=share, word_start=start, cat_first=first, page=page,
                      language=a.get("language"), year=a["year"], head=t[:300])
        c[verdict] += 1
        c[f"page {page if not page.startswith('off') else ('off 1-3' if abs(start - first) <= 3 else 'off >3')}"] += 1
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "check.json").write_text(json.dumps(dict(counts=dict(c), articles=res), ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print(dict(c))
    for s, r in res.items():
        if r["verdict"] != "accept" or r.get("page") not in ("same",):
            print(s, r.get("verdict"), r.get("title_share"), r.get("page"), (r.get("head") or "")[:80])


def cmd_build(stems=None):
    sys.path.insert(0, str(ROOT / "experiments" / "53_word_route"))
    import build53 as B
    B.HERE = HERE / "out"          # pdfmap's legacy_pdf path is relative to this
    B.OUT = OUT
    B.MAST = HERE / "out" / "w0165_code" / "masters"      # the code-only run (exp 43's out/w0165_code is a symlink here)
    chk = json.loads((OUT / "check.json").read_text(encoding="utf-8"))["articles"]
    stems = stems or [s for s, r in chk.items() if r["verdict"] == "accept"]
    cat = B.CAT.open_catalogue()
    res = []
    for s in stems:
        try:
            r = B.build_one(s, cat)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            r = dict(stem=s, valid=False, crash=repr(e), stats={})
        res.append(r)
        print(f"{s}: {'valid' if r.get('valid') else 'INVALID ' + str(r.get('errors', r.get('crash', '')))[:200]}"
              f" headings {r['stats'].get('headings', 0)} refs {r['stats'].get('refs', 0)} "
              f"fn {r['stats'].get('footnotes', 0)} tables {r['stats'].get('tables', 0)}", flush=True)
    (B.MAST.parent / "build.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = Counter()
    for r in res:
        tot.update(r.get("stats", {}))
    print(f"\n{len(res)} articles, {sum(1 for r in res if r.get('valid'))} valid")
    for k in sorted(tot):
        print(f"  {k:<44} {tot[k]:>7}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "build":
        cmd_build(sys.argv[2:] or None)
    else:
        {"prep": cmd_prep, "legacy": cmd_legacy, "check": cmd_check}[cmd]()
