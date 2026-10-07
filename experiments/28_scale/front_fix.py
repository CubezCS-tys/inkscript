"""A candidate fallback for the layout title rule (structure._front_by_layout), tried only where the product's rule
finds no title. Works on page 1's *lines* in top-to-bottom order (not Azure's paragraphs in its reading order), so
it survives the four misses experiment 28 found:
  A  a running head that repeats the title sits above it (small, many words): skipped, not a stop;
  B  Azure merged title, author and affiliation into one paragraph: lines are looked at one by one;
  C  the title repeats as the running head on later pages and was classed as furniture: page 1's large lines count;
  D  Azure's reading order puts the title last on the page: lines are ordered by their place on the page.
The title is the lines just above the byline ("إعداد", "بقلم", "د.", a name with "(*)") when there is one, else the
largest lines (>= 1.2x the body) in the top of the page; the author is the byline's name.

    import front_fix; front_fix.install(inkscript.enrich.structure)
"""
import os
import re

DEBUG = bool(os.environ.get("FRONT_DEBUG"))

INSTITUTION = ("جامعه", "كليه", "قسم", "وزاره", "الجمهوريه", "المملكه", "مركز", "معهد", "دوله", "الهيئه")


def install(S):
    orig = S._front_by_layout

    def front(doc, info, kinds, furniture, note_word, body_h):
        r = orig(doc, info, kinds, furniture, note_word, body_h)
        if r.get("title"):
            return r
        f = fallback(S, doc, info, kinds, furniture, note_word, body_h)
        return f or r

    S._front_by_layout = front


def fallback(S, doc, info, kinds, furniture, note_word, body_h):
    W = doc["words"]
    p0 = min(doc["pages"])
    H = doc["pages"][p0]["h"]
    foot = {k for i, inf in enumerate(info) if kinds[i] == "footnote" for k in doc["paras"][i]["words"]}
    lines = {}
    for w in W:
        if w["page"] == p0 and w["idx"] not in note_word and w["idx"] not in foot:
            lines.setdefault(w["line"], []).append(w)
    L = []
    for li, ws in lines.items():
        b = S._box(ws)
        if (b[1] + b[3]) / 2 > 0.75 * H:
            continue
        txt = " ".join(w["out"] for w in ws).strip()
        L.append(dict(ws=ws, txt=txt, b=b, h=S._h(ws), k=S.key(txt)))
    L.sort(key=lambda l: (l["b"][1], -l["b"][2]))
    kept = []
    for l in L:
        k, n, rel = l["k"], len(l["ws"]), l["h"] / body_h
        if k in S.ABSTRACT or any(k.startswith(x) for x in ("ملخص", "مستخلص", "مقدمه", "المقدمه", "abstract", "تمهيد")):
            break
        if n > 14 and rel < 1.1:
            if kept:
                break                                  # the text has begun
            continue                                   # a long running head above the title (A)
        if len(re.sub(r"[\W\d_]", "", l["txt"])) < 3 or k.startswith(S.BASMALA):
            continue
        if l["b"][1] < 0.1 * H and rel < 0.95:
            continue                                   # small text at the very top: a running head
        first = S.norm(l["ws"][0]["out"].strip("./:،-"))
        l["inst"] = first in INSTITUTION or "مجله" in k[:8]
        l["byline"] = S._is_byline(l["txt"]) or bool(re.search(r"\(\s*\*+\s*\)|\*$", l["txt"])) and n <= 7
        l["aff"] = first in ("استاذ", "الاستاذ", "مدرس", "المدرس", "باحث", "الباحث", "استاذه", "محاضر") or first in INSTITUTION
        kept.append(l)
    for j, l in enumerate(kept[:-1]):                   # a short line over an affiliation is a name
        if 2 <= len(l["ws"]) <= 6 and not l["inst"] and not l["aff"] and kept[j + 1]["aff"]:
            l["byline"] = True
    if DEBUG:
        for l in kept:
            print(f"   {l['h'] / body_h:4.2f}x {len(l['ws']):2d}w y={l['b'][1] / H:.2f} {'INST' if l['inst'] else ''}{'BYL' if l['byline'] else ''} {l['txt'][:60]}")
    if not kept:
        return {}
    title, auth = [], None
    bi = next((j for j, l in enumerate(kept) if l["byline"]), None)
    if bi:
        j = bi - 1
        while j >= 0 and len(title) < 3 and not kept[j]["inst"] and not kept[j]["byline"] and len(kept[j]["ws"]) <= 16:
            if title and kept[j + 0]["b"][3] < title[0]["b"][1] - 3.0 * max(title[0]["h"], body_h):
                break                                  # far above: not the same title
            title.insert(0, kept[j])
            j -= 1
        auth = kept[bi]
        if len(auth["ws"]) <= 2 and S.key(auth["txt"]) in S.BYLINE and bi + 1 < len(kept):
            auth = kept[bi + 1]                        # "إعداد" alone: the name is the next line
    if not title:
        big = [l for l in kept if l["h"] >= 1.2 * body_h and len(l["ws"]) <= 16 and not l["inst"]]
        if not big:
            return {}
        t = max(big, key=lambda l: l["h"])
        j = kept.index(t)
        title = [t]
        for d in (-1, 1):
            m = j + d
            while 0 <= m < len(kept) and kept[m]["h"] >= 0.85 * t["h"] and len(kept[m]["ws"]) <= 16 \
                    and not kept[m]["inst"] and not kept[m]["byline"] and len(title) < 4:
                title.insert(0, kept[m]) if d < 0 else title.append(kept[m])
                m += d
        nxt = kept.index(title[-1]) + 1
        if nxt < len(kept) and (kept[nxt]["byline"] or (2 <= len(kept[nxt]["ws"]) <= 5 and kept[nxt]["h"] < t["h"]
                                                        and not kept[nxt]["inst"] and not kept[nxt]["aff"])):
            auth = kept[nxt]
    tw = [w["idx"] for l in title for w in sorted(l["ws"], key=lambda w: w["idx"])]
    out = dict(title=" ".join(W[k]["out"] for k in tw), title_words=tw, title_source="layout: page 1's lines (experiment 28 fallback)")
    authors = []
    if auth:
        pref, name = S._split_honorific(auth["txt"])
        if name and len(re.sub(r"[\W\d_]", "", name)) >= 4 and not any(S.key(name).startswith(S.key(x)) for x in S.NOT_AUTHOR):
            a = dict(name=name, prefix=pref, words=[w["idx"] for w in auth["ws"]], prefix_words=[],
                     source="layout: the byline (experiment 28 fallback)")
            S._split_aff(a, W)
            authors.append(a)
    out["authors"] = authors
    return out
