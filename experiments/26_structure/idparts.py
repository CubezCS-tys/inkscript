"""Check what the Mandumah id's parts mean: print each document's id beside the printed lines that name a volume,
issue or year (المجلد / العدد / السنة / الجزء), from Azure's reading.

    python idparts.py DIR...     (each DIR holds <id>/<id>.json)
"""
import json
import re
import sys
from pathlib import Path

PAT = re.compile(r"(المجلد|مجلد|العدد|عدد|السنة|الجزء|Vol|No\.)")
for d in sys.argv[1:]:
    for sub in sorted(Path(d).iterdir())[:400]:
        f = sub / f"{sub.name}.json"
        if not f.exists():
            continue
        j = json.loads(f.read_text(encoding="utf-8"))
        ar = j.get("analyzeResult", j)
        hits = []
        for pg in ar.get("pages", [])[:3]:
            for ln in pg.get("lines", []):
                t = ln.get("content", "")
                if PAT.search(t) and re.search(r"[0-9٠-٩]", t) and len(t) < 80:
                    hits.append(f"p{pg['pageNumber']}: {t}")
        if hits:
            print(sub.name, "|", " || ".join(hits[:3]))


def agreement(dirs):
    """Count documents whose printed issue / volume number (digits after العدد / المجلد or السنة) equals the id's."""
    D = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    res = dict(issue=[0, 0], volume=[0, 0])
    for d in dirs:
        for sub in sorted(Path(d).iterdir()):
            f = sub / f"{sub.name}.json"
            parts = sub.name.split("-")
            if not f.exists() or len(parts) != 4:
                continue
            j = json.loads(f.read_text(encoding="utf-8"))
            ar = j.get("analyzeResult", j)
            txt = " ".join(ln.get("content", "") for pg in ar.get("pages", [])[:3] for ln in pg.get("lines", [])
                           if len(ln.get("content", "")) < 90).translate(D)
            for key, pat, part in (("issue", r"(?:العدد|عدد)\s*[:/(]?\s*(\d{1,4})\b", parts[2]),
                                   ("volume", r"(?:المجلد|مجلد|السنة)\s*[:/(]?\s*(\d{1,3})\b", parts[1])):
                m = re.search(pat, txt)
                if m and part.isdigit() and int(part) > 0:
                    res[key][1] += 1
                    res[key][0] += int(m.group(1)) == int(part)
                    if int(m.group(1)) != int(part):
                        print("  differs:", sub.name, key, m.group(0))
    return res


if __name__ == "__main__" and len(sys.argv) > 1:
    print(agreement(sys.argv[1:]))
