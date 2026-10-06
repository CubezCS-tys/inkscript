"""The canonical Quran text (Tanzil) and the normalisations used to match it.

Matching is diacritic- and spelling-insensitive: harakat, Quranic marks and
tatweel go; alef forms become ا, ى→ي, ة→ه, ؤ→و, ئ→ي, a bare hamza ء goes,
Persian/Urdu letter forms Azure sometimes emits (ک ی ہ) become Arabic ones.
Two looser keys sit on top of that:

* ``noalef`` drops every ا as well — the Uthmani script writes many long
  alefs as a small dagger alef (العلمين for العالمين), so a quote typeset in
  Uthmani script matches the simple (imla'i) text on this key;
* ``skel`` keeps only the rasm (dotless skeleton) — two words with the same
  skeleton but different readings differ only in their dots.
"""
from __future__ import annotations
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
QDIR = HERE.parent / "20_document_data" / "out" / "quran"   # experiment 20's Tanzil download, read only

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
    for line in path.read_text(encoding="utf-8").splitlines():
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
        clean = _load(qdir / "quran-simple-clean.txt")
        voc = _load(qdir / "quran-simple.txt")
        root = ET.parse(qdir / "quran-data.xml").getroot()
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
