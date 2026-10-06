"""Quran quotations in Azure's reading: found, linked to sura and verse, checked word for word (experiment 20).

    q = quran()                                   # the Tanzil text, loaded once per process
    quotes = find_quotes(doc, q); classify(...)   # doc: enrich.document.load(...)

The canonical text is Tanzil's (Simple Clean v1.1 for matching, Simple v1.1 for display; CC BY 3.0, verbatim,
credit Tanzil and link tanzil.net). It ships in ``inkscript/data/quran/`` (see NOTICE.md there and
docs/decisions.md D20). Normalisation is a matching key computed in memory; the files are never changed.

Matching is diacritic- and spelling-insensitive: harakat, Quranic marks and tatweel go; alef forms become ا,
ى→ي, ة→ه, ؤ→و, ئ→ي, a bare hamza ء goes, Persian/Urdu letter forms Azure sometimes emits (ک ی ہ) become Arabic
ones. Two looser keys sit on top: ``noalef`` drops every ا too (Uthmani-script quotations write long alefs as a
dagger alef: العلمين for العالمين), and ``skel`` keeps only the dotless rasm (a "dots only" difference).

Finding (seed and extend): two consecutive reading words whose ``noalef`` key equals a Quran bigram seed a
candidate; a banded alignment (band 6, x-drop) extends it both ways, allowing a word to differ, be missing or
extra, or be split/joined. Inside ﴿ ﴾ a quotation needs >= 60% of the verse words and >= 3 matches (a short one
must fill its brackets); elsewhere >= 5 matching words and >= 75% of the verse span. A second pass anchors
bracket spans too damaged for an exact seed on their rarest Quran word. Measured on 215 documents (experiment
20): 1,173 quotations, the cited sura agrees 280/290; on the ink 20 of 24 differing words are Azure misreadings.
"""
from __future__ import annotations

import difflib
import gzip
import re
import unicodedata
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

QDIR = Path(__file__).resolve().parents[1] / "data" / "quran"
TANZIL_CREDIT = "Tanzil Project, Quran text (Simple v1.1), CC BY 3.0, https://tanzil.net"


_MARKS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ࣓-ࣿـ]")
_MAP = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا",
    "ى": "ي", "ی": "ي", "ې": "ي", "ة": "ه", "ہ": "ه", "ە": "ه", "ۀ": "ه",
    "ؤ": "و", "ئ": "ي", "ء": "", "ک": "ك", "ګ": "ك", "ڪ": "ك",
})
_KEEP = re.compile("[^ء-ي]")
_SKEL = str.maketrans({
    "ب": "ٮ", "ت": "ٮ", "ث": "ٮ", "ن": "ٮ", "ي": "ٮ",
    "ج": "ح", "خ": "ح", "ذ": "د", "ز": "ر", "ش": "س", "ض": "ص",
    "ظ": "ط", "غ": "ع", "ق": "ف",
})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = _MARKS.sub("", s).translate(_MAP)
    return _KEEP.sub("", s)


def noalef(n: str) -> str:
    return n.replace("ا", "")


def skel(n: str) -> str:
    return n.translate(_SKEL)


def _load(path: Path) -> dict[tuple[int, int], str]:
    d = {}
    for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines():
        if line and not line.startswith("#") and line.count("|") >= 2:
            s, a, t = line.split("|", 2)
            d[(int(s), int(a))] = t
    return d


class Quran:
    """Every word of the Quran in order, with its verse and three keys.

    ``seq`` is one flat list; a ``None`` sits between suras so an alignment
    never runs from one sura into the next. The basmala that Tanzil's text
    prefixes to verse 1 of suras 2–114 (not 9) is left out: it is not part of
    the verse's numbering, and 1:1 and 27:30 still carry it.
    """

    def __init__(self, qdir: Path = QDIR):
        clean = _load(qdir / "quran-simple-clean.txt.gz")
        voc = _load(qdir / "quran-simple.txt.gz")
        root = ET.fromstring(gzip.decompress((qdir / "quran-data.xml.gz").read_bytes()))
        self.sura_name = {int(s.get("index")): s.get("name") for s in root.iter("sura")}
        self.verse_text = {}
        self.seq: list[dict | None] = []
        cur = None
        for (s, a), t in clean.items():
            if s != cur:
                self.seq.append(None)
                cur = s
            ws, vs = t.split(), voc[(s, a)].split()
            assert len(ws) == len(vs), (s, a)
            if a == 1 and s not in (1, 9) and [norm(w) for w in ws[:4]] == ["بسم", "الله", "الرحمن", "الرحيم"]:
                ws, vs = ws[4:], vs[4:]
            self.verse_text[(s, a)] = (" ".join(ws), " ".join(vs))
            i = 0
            for w, v in zip(ws, vs):
                n = norm(w)
                if not n:          # pause marks (ۛ ۚ …) stand as their own tokens
                    continue
                self.seq.append({"s": s, "a": a, "i": i, "w": w, "v": v,
                                 "n": n, "k": noalef(n)})
                i += 1
        self.seq.append(None)
        self.unigram: dict[str, list[int]] = {}
        for j, x in enumerate(self.seq):
            if x:
                self.unigram.setdefault(x["k"], []).append(j)
        self.bigram: dict[tuple[str, str], list[int]] = {}
        for j in range(len(self.seq) - 1):
            x, y = self.seq[j], self.seq[j + 1]
            if x and y:
                self.bigram.setdefault((x["k"], y["k"]), []).append(j)
        # sura names as written in citations, normalised (البقرة, آل عمران…)
        self.name_to_sura = {norm(n): i for i, n in self.sura_name.items()}


# ---------------------------------------------------------------- finding and checking quotations

GAP = -1.2
BAND = 6
XDROP = 8.0
MAXLEN = 400


def pair(d: dict, q: dict) -> tuple[float, str]:
    if d["n"] == q["n"]:
        return 2.0, "exact"
    if d["k"] == q["k"]:
        return 1.8, "spelling"
    r = difflib.SequenceMatcher(None, d["n"], q["n"]).ratio()
    if r >= 0.5:
        kind = "dots" if skel(d["n"]) == skel(q["n"]) else "letters"
        return 2 * r - 1, kind
    return -1.5, "other"


def extend(D: list[dict], Q: list, di: int, qj: int, step: int, dlim: int) -> tuple[float, list]:
    """Best anchored alignment of D[di], D[di+step]… with Q[qj], Q[qj+step]…

    Returns (score, ops) with ops in the walking order; each op is
    (kind, [doc indices], [quran indices]). dlim bounds the doc index
    (exclusive, in the walking direction).
    """
    def dget(a):          # a-th doc token from the anchor (0-based), or None
        i = di + step * a
        if (step > 0 and i >= dlim) or (step < 0 and i <= dlim) or i < 0 or i >= len(D):
            return None
        return i

    def qget(b):
        j = qj + step * b
        if j < 0 or j >= len(Q) or Q[j] is None:
            return None
        return j

    A = 0
    while A < MAXLEN and dget(A) is not None:
        A += 1
    B = 0
    while B < MAXLEN and qget(B) is not None:
        B += 1
    S = {(0, 0): (0.0, None, None)}
    best, bcell = 0.0, (0, 0)
    for a in range(0, A + 1):
        rowmax = -1e9
        for b in range(max(0, a - BAND), min(B, a + BAND) + 1):
            if a == 0 and b == 0:
                rowmax = 0.0
                continue
            cands = []
            if a and b and (a - 1, b - 1) in S:
                i, j = dget(a - 1), qget(b - 1)
                sc, kind = pair(D[i], Q[j])
                cands.append((S[(a - 1, b - 1)][0] + sc, (a - 1, b - 1), (kind, [i], [j])))
            if a and (a - 1, b) in S:
                cands.append((S[(a - 1, b)][0] + GAP, (a - 1, b), ("extra", [dget(a - 1)], [])))
            if b and (a, b - 1) in S:
                cands.append((S[(a, b - 1)][0] + GAP, (a, b - 1), ("missing", [], [qget(b - 1)])))
            if a >= 2 and b and (a - 2, b - 1) in S:
                i1, i2, j = dget(a - 2), dget(a - 1), qget(b - 1)
                ii = sorted([i1, i2])
                if D[ii[0]]["k"] + D[ii[1]]["k"] == Q[j]["k"]:
                    cands.append((S[(a - 2, b - 1)][0] + 2.2, (a - 2, b - 1), ("split", ii, [j])))
            if a and b >= 2 and (a - 1, b - 2) in S:
                i, j1, j2 = dget(a - 1), qget(b - 2), qget(b - 1)
                jj = sorted([j1, j2])
                if D[i]["k"] == Q[jj[0]]["k"] + Q[jj[1]]["k"]:
                    cands.append((S[(a - 1, b - 2)][0] + 2.2, (a - 1, b - 2), ("joined", [i], jj)))
            if not cands:
                continue
            c = max(cands, key=lambda t: t[0])
            if c[0] < best - XDROP:
                continue
            S[(a, b)] = c
            rowmax = max(rowmax, c[0])
            if c[0] > best:
                best, bcell = c[0], (a, b)
        if rowmax < best - XDROP:
            break
    ops, cell = [], bcell
    while cell != (0, 0):
        sc, prev, op = S[cell]
        ops.append(op)
        cell = prev
    ops.reverse()
    return best, ops


MATCHED = {"exact", "spelling", "split", "joined"}


EDGE_DROP = {"missing", "extra", "other"}


def trim(ops: list, D=None, Q=None, brk=None) -> list:
    """Drop gaps and unrelated words at the ends. A near-miss word at an end is
    kept (it is a reading to check) only when it is close — same skeleton or
    70% of its letters — and does not lie outside the brackets the rest of
    the quote is in (قوله تعالى: ﴿… must not pull in تعالى)."""
    inb = brk is not None and any(i in brk for o in ops for i in o[1])

    def drop(o):
        if o[0] in EDGE_DROP:
            return True
        if o[0] in MATCHED or D is None:
            return False
        if inb and not any(i in brk for i in o[1]):
            return True
        if o[0] == "dots":
            return False
        r = difflib.SequenceMatcher(None, D[o[1][0]]["n"], Q[o[2][0]]["n"]).ratio()
        return r < 0.7
    while ops and drop(ops[0]):
        ops = ops[1:]
    while ops and drop(ops[-1]):
        ops = ops[:-1]
    if not any(o[0] in MATCHED for o in ops):
        return []
    return ops


def stats(ops: list) -> dict:
    qn = sum(len(o[2]) for o in ops)
    m = sum(len(o[2]) for o in ops if o[0] in MATCHED)
    return {"qwords": qn, "matched": m, "differs": sum(o[0] not in MATCHED for o in ops)}


def bracket_spans(content: str) -> list[tuple[int, int]]:
    """﴿ … ﴾ spans; Azure often loses one of the pair, so an opener runs to the
    next closer within 700 characters and a lone closer is ignored."""
    out, i = [], 0
    while True:
        a = content.find("﴿", i)
        if a < 0:
            return out
        b = content.find("﴾", a + 1)
        nxt = content.find("﴿", a + 1)
        if b < 0 or b - a > 700 or (0 <= nxt < b):
            i = a + 1
            continue
        out.append((a, b + 1))
        i = b + 1


_AR_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


_CIT = re.compile(r"(?:سورة\s+)?([\u0621-\u064A\u064B-\u065F\u0670\s]{2,24}?)\s*[:،,]\s*"
                  r"(?:الآيات|الآية|آية|الاية|اية)?\s*([0-9٠-٩۰-۹]+)")


def citation(content: str, end: int, q: Quran) -> dict | None:
    """A sura cited right after the quotation: «(البقرة: 24)», «[هود: ١١١]»,
    «الحجر: ٨٧», «(سورة يس، الآية 33)». The name must be a sura's name
    exactly (with or without ال), and the citation must start within 20
    characters of the quotation's end."""
    tail = content[end:end + 60]
    for m in _CIT.finditer(tail):
        if m.start() > 20:
            break
        name = norm(m.group(1))
        for cand in (name, "ال" + name, name.removeprefix("سوره")):
            if cand in q.name_to_sura:
                return {"sura": q.name_to_sura[cand],
                        "numbers": [int(m.group(2).translate(_AR_DIG))],
                        "text": tail[m.start():m.end()].strip()}
    return None


def make_quote(D, Q, q, content, ops, sc, st, bracketed, alts, via="seed") -> dict:
    qidx = [j for o in ops for j in o[2]]
    q0, q1 = Q[min(qidx)], Q[max(qidx)]
    d0 = min(i for o in ops for i in o[1])
    d1 = max(i for o in ops for i in o[1])
    a, b = D[d0]["off"], D[d1]["off"] + D[d1]["len"]
    cit = citation(content, b, q)
    return {
        "ref": f'{q0["s"]}:{q0["a"]}' + (f'-{q1["a"]}' if q1["a"] != q0["a"] else ""),
        "sura": q0["s"], "aya": q0["a"], "aya_end": q1["a"],
        "sura_name": q.sura_name[q0["s"]],
        "score": round(sc, 2), **st, "bracketed": bracketed,
        "also": [f"{s}:{a}" for s, a in alts],
        "doc_words": [D[i]["idx"] for i in range(d0, d1 + 1)],
        "reading": content[a:b],
        "verse": " ".join(Q[j]["v"] for j in range(min(qidx), max(qidx) + 1)),
        "citation": cit,
        "citation_agrees": (cit["sura"] == q0["s"]) if cit else None,
        "citation_verse_agrees": (cit["sura"] == q0["s"] and q0["a"] <= cit["numbers"][0] <= q1["a"])
        if cit else None,
        "ops": [{"kind": k, "doc": [D[i]["idx"] for i in di_], "q": [
            {"s": Q[j]["s"], "a": Q[j]["a"], "i": Q[j]["i"], "w": Q[j]["w"], "v": Q[j]["v"]}
            for j in qj_]} for k, di_, qj_ in ops],
        "page": D[d0]["page"], "via": via,
    }


def find_quotes(doc: dict, q: Quran) -> tuple[list[dict], list[tuple[int, int]]]:
    content = doc["content"]
    D = [w for w in doc["words"] if w["n"]]
    spans = bracket_spans(content)
    brk = set()
    for a, b in spans:
        for t, w in enumerate(D):
            if a <= w["off"] < b:
                brk.add(t)
    Q = q.seq
    quotes, di, last_end = [], 0, -1
    while di < len(D) - 1:
        seeds = q.bigram.get((D[di]["k"], D[di + 1]["k"]), [])
        cands = []
        need = 2 if di in brk else 3
        for qj in seeds:
            hits = sum(1 for t in range(4)
                       if di + t < len(D) and qj + t < len(Q) and Q[qj + t]
                       and D[di + t]["k"] == Q[qj + t]["k"])
            if hits < need:
                continue
            s1, fwd = extend(D, Q, di, qj, +1, len(D))
            s0, back = extend(D, Q, di - 1, qj - 1, -1, last_end)
            ops = trim(back[::-1] + fwd, D, Q, brk)
            if not ops:
                continue
            cands.append((s0 + s1, qj, ops))
        acc = []
        for sc, qj, ops in cands:
            st = stats(ops)
            d0 = min(i for o in ops for i in o[1])
            d1 = max(i for o in ops for i in o[1])
            a, b = D[d0]["off"], D[d1]["off"] + D[d1]["len"]
            inside = sum(t in brk for t in range(d0, d1 + 1)) / (d1 - d0 + 1)
            hug = "﴿" in content[max(0, a - 3):a] or "﴾" in content[b:b + 3]
            bracketed = inside >= 0.5 or hug
            # a short bracketed quote: two words suffice if it fills its brackets
            fill, inspan = 0.0, False
            for x, y in spans:
                if x <= a < y:
                    nb = sum(1 for w in D if x <= w["off"] < y)
                    fill, inspan = (d1 - d0 + 1) / max(nb, 1), True
            if bracketed:
                # short ones must fill their brackets: Azure reads the honorific
                # signs (ﷺ, رضي الله عنه) as ﴿ ﴾ too, around ordinary prose
                short_ok = (fill >= 0.5 and st["matched"] >= 3) or fill >= 0.8 or \
                    (not inspan and hug and st["matched"] >= 3)
                ok = st["matched"] >= 0.6 * st["qwords"] and (
                    st["matched"] >= 5 or (st["matched"] >= 2 and short_ok))
            else:
                ok = st["matched"] >= 5 and st["matched"] >= 0.75 * st["qwords"]
            if ok:
                acc.append((sc, qj, ops, st, d0, d1, bracketed, a, b))
        if not acc:
            di += 1
            continue
        cit = citation(content, acc[0][8], q)
        # best score; on a tie the sura cited after the quote, then the earliest
        acc.sort(key=lambda t: (-round(t[0], 2),
                                not (cit and Q[t[1]]["s"] == cit["sura"]), t[1]))
        sc, qj, ops, st, d0, d1, bracketed, a, b = acc[0]
        qidx = [j for o in ops for j in o[2]]
        q0, q1 = Q[min(qidx)], Q[max(qidx)]
        alts = []
        for o in acc[1:]:
            if o[0] >= sc - 0.01:
                qq = [j for op in o[2] for j in op[2]]
                ref = (Q[min(qq)]["s"], Q[min(qq)]["a"])
                if ref != (q0["s"], q0["a"]) and ref not in alts:
                    alts.append(ref)
        quotes.append(make_quote(D, Q, q, content, ops, sc, st, bracketed, alts))
        last_end = d1
        di = d1 + 1
    quotes += bracket_pass(D, Q, q, content, spans, quotes, brk)
    quotes.sort(key=lambda x: x["doc_words"][0])
    return quotes, spans


def bracket_pass(D, Q, q, content, spans, quotes, brk) -> list[dict]:
    """Short bracketed quotes too damaged for an exact bigram seed.

    For each ﴿ … ﴾ span no quotation starts in, anchor on its rarest word that
    occurs in the Quran and align the span's words around every occurrence.
    Accept when the alignment covers 80% of the span and at least 75% of the
    verse words match or nearly match (dots/letters)."""
    starts = {x["doc_words"][0] for x in quotes}
    taken = {i for x in quotes for i in x["doc_words"]}
    out = []
    for a, b in spans:
        T = [t for t, w in enumerate(D) if a <= w["off"] < b]
        if len(T) < 2 or any(D[t]["idx"] in taken for t in T):
            continue
        lo, hi = T[0] - 1, T[-1] + 1
        anchors = sorted((len(q.unigram.get(D[t]["k"], [])), t) for t in T
                         if q.unigram.get(D[t]["k"]))
        best = None
        for _, t in anchors[:2]:
            for qj in q.unigram[D[t]["k"]][:400]:
                s1, fwd = extend(D, Q, t, qj, +1, hi)
                s0, back = extend(D, Q, t - 1, qj - 1, -1, lo)
                ops = trim(back[::-1] + fwd, D, Q, brk)
                if ops and (best is None or s0 + s1 > best[0]):
                    best = (s0 + s1, qj, ops)
        if not best:
            continue
        sc, qj, ops = best
        st = stats(ops)
        near = sum(len(o[2]) for o in ops if o[0] in MATCHED | {"dots", "letters"})
        dset = sorted(i for o in ops for i in o[1])
        if len(dset) < 0.8 * len(T) or near < 0.75 * st["qwords"] or st["matched"] < 1:
            continue
        out.append(make_quote(D, Q, q, content, ops, sc, st, True, [], via="bracket"))
    return out


def classify(qt: dict, words: list[dict]) -> None:
    """Attach to each differing op what we think it is."""
    ops = qt["ops"]
    for n, o in enumerate(ops):
        k = o["kind"]
        if k in MATCHED:
            o["verdict"] = None
            continue
        edge = n <= 1 or n >= len(ops) - 2
        if k in ("dots",):
            o["verdict"] = "reading error? (dots only)"
        elif k == "letters":
            dn = norm(words[o["doc"][0]]["text"])
            qn = norm(o["q"][0]["w"])
            if (dn[1:] == qn and dn[0] in "وف") or (qn[1:] == dn and qn[0] in "وف"):
                o["verdict"] = "quotation choice (و/ف)"
            else:
                o["verdict"] = "reading error? (letters)"
        elif k == "other":
            o["verdict"] = "different word"
        elif k == "missing":
            o["verdict"] = "word not in reading (omitted or lost)"
        elif k == "extra":
            o["verdict"] = "word not in verse"
        o["edge"] = edge


@lru_cache(maxsize=1)
def quran() -> "Quran":
    """The Quran index, built once per process (about 2 s, 60 MB)."""
    return Quran()


def check_document(doc: dict, q: "Quran | None" = None) -> list[dict]:
    """Every quotation in the document, each difference classified. Word indices are doc["words"] idx."""
    q = q or quran()
    quotes, _ = find_quotes(doc, q)
    for qt in quotes:
        classify(qt, doc["words"])
    return quotes
