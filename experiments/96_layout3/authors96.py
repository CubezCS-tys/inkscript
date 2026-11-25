"""Experiment 96, goal 1, step 1: author and affiliation lines from the catalogue (marc.db, read only).

    python authors96.py [pool|extra]
                             pool  -> out/authors96.jsonl   one row per training-pool page searched (pages 1-2 of each
                                                      document): {key, labels: {line i: author|affiliation}, why}
                                out/authors96_stats.json

Names: marc.db `authors` (tags 100/700, persons only, is_org = 0) of the record the PDF stem belongs to (pdf_ids).
The catalogue writes "Surname، Given"; both orders are tried.  Folded form = common94.norm (vowel marks, alef forms,
ى/ي, ة/ه) plus punctuation removed; prefixes such as بقلم، الأستاذ، الدكتور، د.، أ.د.، الشيخ are not part of any name
and are simply allowed as extra words.

AUTHOR line: a page-1 (or page-2 when page 1 has no match) Azure line in which >= 70% of a catalogue name's words
(>= 2 words) are found, each word by fuzzy ratio >= 85, the found words in a window no longer than the name + 2, and
the line has at most name words + 7 other words (a sentence that mentions the author is not a byline).  Lines Argon
types header, footnote, reference, table or list are left alone.
AFFILIATION candidate: the lines directly under or beside an author line (vertical gap <= 1.2 line heights, chained,
horizontal overlap with the chain, at most 4 lines), stopping at a line Argon types title / abstract or a body block
of more than 3 lines, that contain an institution word (common94.AFF_WORDS: جامعة، كلية، قسم، معهد، وزارة ...).
EXTRA documents (`extra`): pages 1-2 of the local documents of experiments 77/80 (pages77/pages80.jsonl) outside
the training pool (no Argon on them), with the same guards; no Argon types, so instead an author line must start in
the top 75% of the page, and the affiliation chain stops at a body-like line (> 60% of the page's line width and
> 8 words).  -> out/authors96_extra.jsonl (+ each page's pdf / azure / size; the other lines get the stage-2 model's
own type on the GPU host, labels96.py).
Other lines keep the label experiment 94 gave them (Argon's fine type, byline split by metadata).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

from rapidfuzz import fuzz

from common96 import MARC, O94, OUT, AFF_WORDS, azure_lines, guard_training, inventory_azure, norm

PUNCT = re.compile(r"[^\w\s]|_|\d")
PREFIX = set(norm(w) for w in "بقلم بقلم: الاستاذ الأستاذ الاستاذة الدكتور الدكتورة الدكتوره د أ ا أد اد م الشيخ السيد "
             "السيدة الآنسة الانسة المهندس الباحث الباحثة اعداد إعداد تأليف تاليف ترجمة الأستاذ الدكتور".split())
SKIP = {"header", "footnote", "reference", "table", "list", "page_number", "equation"}


def words(s):
    return [w for w in PUNCT.sub(" ", norm(s)).split() if w]


def name_variants(name):
    name = (name or "").strip()
    out = []
    if "،" in name or "," in name:
        a, b = re.split("[،,]", name, 1)
        out += [words(b) + words(a), words(a) + words(b)]
    else:
        out.append(words(name))
    return [v for v in out if len(v) >= 2]


def find_name(lw, nv):
    """(found share, window length) of name words nv in line words lw."""
    hits = []
    for w in nv:
        best = max(((fuzz.ratio(w, x), j) for j, x in enumerate(lw)), default=(0, -1))
        # an attached و/ال or a short particle: also try without the line word's first letter
        if best[0] < 85:
            best = max([best] + [(fuzz.ratio(w, x[1:]), j) for j, x in enumerate(lw) if len(x) > 3])
        if best[0] >= 85:
            hits.append(best[1])
    if not hits:
        return 0.0, 99
    return len(hits) / len(nv), max(hits) - min(hits) + 1


def extra_rows():
    from common96 import E, heldout_codes, is_locked_any, test_docs
    pool = {json.loads(l)["stem"] for l in open(O94 / "train94.jsonl", encoding="utf-8")}
    held, td = heldout_codes(), test_docs()
    rows, az = {}, {}
    for fn in ("pages77.jsonl", "pages80.jsonl"):
        for l in open(E / "77_scratch_reader/out" / fn, encoding="utf-8"):
            a = json.loads(l)
            s = a["stem"]
            if s in pool or s[:4] in held or s in td or is_locked_any(s) or a["page"] > 2:
                continue
            k = f"{s}_p{a['page']:03d}"
            if k not in rows:
                L, W, H = azure_lines(a["azure"], a["page"])
                rows[k] = dict(key=k, stem=s, page=a["page"], jcode=a["jcode"], pdf=a["pdf"], azure=a["azure"],
                               W=W, H=H, extra=True,
                               lines=[dict(i=x["i"], fine=None, block=None) for x in L if x["box"]])
                az[s] = a["azure"]
    return list(rows.values()), az


def main(mode="pool"):
    if mode == "pool":
        rows = [json.loads(l) for l in open(O94 / "train94.jsonl", encoding="utf-8")]
        az = inventory_azure()
    else:
        rows, az = extra_rows()
    guard_training([r["key"] for r in rows])
    c = sqlite3.connect(MARC, uri=True)
    names = {}
    for st in sorted({r["stem"] for r in rows}):
        rec = c.execute("select rec from pdf_ids where stem = ?", (st,)).fetchone()
        names[st] = [] if not rec else [n for (n,) in c.execute(
            "select name from authors where rec = ? and coalesce(is_org, 0) = 0 and tag in ('100', '700')", rec)]
    bydoc = defaultdict(list)
    for r in rows:
        bydoc[r["stem"]].append(r)
    st = Counter()
    tag = "" if mode == "pool" else "_extra"
    with open(OUT / f"authors96{tag}.jsonl", "w", encoding="utf-8") as f:
        for stem, R in sorted(bydoc.items()):
            R.sort(key=lambda r: r["page"])
            nv = [(n, v) for n in names[stem] for v in name_variants(n)]
            st["docs"] += 1
            st["docs_with_names"] += bool(nv)
            found_doc = False
            for r in R[:2]:
                if found_doc or r["page"] > 2 or not nv:
                    break
                L, W, H = azure_lines(az[stem], r["page"])
                text = {x["i"]: x["text"] for x in L}
                info = {x["i"]: x for x in r["lines"]}
                labels, why = {}, {}
                for x in L:
                    if x["i"] not in info or not x["box"]:
                        continue
                    if (info[x["i"]]["fine"] or "") in SKIP:
                        continue
                    lw = words(x["text"])
                    for n, v in nv:
                        share, win = find_name(lw, v)
                        if r.get("extra") and x["box"][1] > 0.75 * H:
                            continue
                        if share >= 0.7 and len(v) * share >= 2 and win <= len(v) + 2 and len(lw) <= len(v) + 7:
                            labels[x["i"]] = "author"
                            why[x["i"]] = n
                            break
                if not labels:
                    st["pages_no_match"] += 1
                    continue
                found_doc = True
                # affiliation candidates under / beside each author line
                box = {x["i"]: x["box"] for x in L if x["box"]}
                blk = Counter(info[i]["block"] for i in info)
                mh = sorted(b[3] - b[1] for b in box.values())[len(box) // 2]
                for a in list(labels):
                    chain = [box[a]]
                    for x in sorted(L, key=lambda x: x["box"][1] if x["box"] else 1e9):
                        i = x["i"]
                        if i in labels or i not in info or not x["box"] or x["box"][1] < box[a][1] - 0.2 * mh:
                            continue
                        b, last = x["box"], chain[-1]
                        fi = info[i]["fine"] or ""
                        side = (min(b[3], box[a][3]) - max(b[1], box[a][1]) > 0.5 * mh)     # beside the author
                        below = 0 <= b[1] - last[3] <= 1.2 * mh and min(b[2], last[2]) - max(b[0], last[0]) > 0
                        if not (side or below):
                            continue
                        if r.get("extra") and len(words(x["text"])) > 8 and b[2] - b[0] > 0.6 * W * 0.8:
                            break
                        if fi in ("title", "abstract") or (fi == "body" and blk[info[i]["block"]] > 3) or fi in SKIP:
                            break
                        if AFF_WORDS.search(x["text"]):
                            labels[i] = "affiliation"
                            why[i] = "under " + str(a)
                            if below:
                                chain.append(b)
                        elif below and fi in ("author", "affiliation", "heading", "caption", "other", "body", ""):
                            chain.append(b)          # a second name or a post line: pass through, unlabelled
                        if len(chain) > 5:
                            break
                old = Counter(f"{info[i]['fine']}->{v}" for i, v in labels.items())
                st.update(old)
                ex = {k: r[k] for k in ("jcode", "pdf", "azure", "W", "H")} if r.get("extra") else {}
                f.write(json.dumps(dict(key=r["key"], stem=stem, page=r["page"], labels=labels, why=why,
                                        texts={i: text[i] for i in labels}, **ex), ensure_ascii=False) + "\n")
    json.dump(st, open(OUT / f"authors96{tag}_stats.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps(st.most_common(40), ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
