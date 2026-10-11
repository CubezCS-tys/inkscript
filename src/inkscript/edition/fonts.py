"""The editions' fonts (all SIL Open Font Licence), found on the system or fetched once into a cache.

    font_dir()                         ~/.cache/inkscript/fonts (or $INKSCRIPT_FONTS); created on demand
    font_path(name, weight="regular")  a static TTF: name in markazi | amiri | naskh | kufi; weight regular | bold
    all_fonts()                        {(name, weight): path} for the ones that can be provided
    licence_path(name)                 the font's OFL text when known (EPUB and HTML bundles carry it)

Markazi Text (Borna Izadpanah, Google Fonts) is a variable font upstream; static Regular (400) and Bold (700)
instances are cut from it with fontTools and cached. Amiri and Noto Naskh/Kufi Arabic are taken from the system
(Debian/Ubuntu fonts-hosny-amiri, fonts-noto-core) or fetched from their upstream repositories when missing.
"""
from __future__ import annotations

import os
import urllib.request
from pathlib import Path

MARKAZI_URL = "https://github.com/google/fonts/raw/main/ofl/markazitext/MarkaziText%5Bwght%5D.ttf"
MARKAZI_OFL = "https://github.com/google/fonts/raw/main/ofl/markazitext/OFL.txt"

SYSTEM = {
    ("amiri", "regular"): ["/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Regular.ttf",
                           "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf"],
    ("amiri", "bold"): ["/usr/share/fonts/opentype/fonts-hosny-amiri/Amiri-Bold.ttf",
                        "/usr/share/fonts/truetype/amiri/Amiri-Bold.ttf"],
    ("naskh", "regular"): ["/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"],
    ("naskh", "bold"): ["/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"],
    ("kufi", "regular"): ["/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf"],
    ("kufi", "bold"): ["/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf"],
}
UPSTREAM = {
    ("amiri", "regular"): "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Regular.ttf",
    ("amiri", "bold"): "https://github.com/google/fonts/raw/main/ofl/amiri/Amiri-Bold.ttf",
    ("naskh", "regular"): "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoNaskhArabic/hinted/ttf/NotoNaskhArabic-Regular.ttf",
    ("naskh", "bold"): "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoNaskhArabic/hinted/ttf/NotoNaskhArabic-Bold.ttf",
    ("kufi", "regular"): "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoKufiArabic/hinted/ttf/NotoKufiArabic-Regular.ttf",
    ("kufi", "bold"): "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoKufiArabic/hinted/ttf/NotoKufiArabic-Bold.ttf",
}
FAMILY = {"markazi": "Markazi Text", "amiri": "Amiri", "naskh": "Noto Naskh Arabic", "kufi": "Noto Kufi Arabic"}
FILE = {("markazi", "regular"): "MarkaziText-Regular.ttf", ("markazi", "bold"): "MarkaziText-Bold.ttf",
        ("amiri", "regular"): "Amiri-Regular.ttf", ("amiri", "bold"): "Amiri-Bold.ttf",
        ("naskh", "regular"): "NotoNaskhArabic-Regular.ttf", ("naskh", "bold"): "NotoNaskhArabic-Bold.ttf",
        ("kufi", "regular"): "NotoKufiArabic-Regular.ttf", ("kufi", "bold"): "NotoKufiArabic-Bold.ttf"}


def font_dir() -> Path:
    d = Path(os.environ.get("INKSCRIPT_FONTS") or Path.home() / ".cache" / "inkscript" / "fonts")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str, dest: Path) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "inkscript (font fetch)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest


def _markazi(weight: str) -> Path:
    d = font_dir()
    out = d / FILE[("markazi", weight)]
    if out.exists():
        return out
    var = d / "MarkaziText[wght].ttf"
    if not var.exists():
        _get(MARKAZI_URL, var)
    if not (d / "OFL-markazi.txt").exists():
        try:
            _get(MARKAZI_OFL, d / "OFL-markazi.txt")
        except OSError:
            pass
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    f = TTFont(str(var))
    inst = instancer.instantiateVariableFont(f, {"wght": 700 if weight == "bold" else 400},
                                             updateFontNames=True)
    tmp = out.with_suffix(".part")
    inst.save(str(tmp))
    tmp.replace(out)
    return out


def font_path(name: str = "markazi", weight: str = "regular") -> Path:
    name, weight = name.lower(), weight.lower()
    if name == "markazi":
        return _markazi(weight)
    for p in SYSTEM.get((name, weight), []):
        if Path(p).exists():
            return Path(p)
    out = font_dir() / FILE[(name, weight)]
    if not out.exists():
        _get(UPSTREAM[(name, weight)], out)
    return out


def all_fonts() -> dict:
    out = {}
    for k in FILE:
        try:
            out[k] = font_path(*k)
        except Exception:                    # offline, no system copy: that font is not offered
            pass
    return out


def licence_path(name: str) -> Path | None:
    if name == "markazi":
        p = font_dir() / "OFL-markazi.txt"
        return p if p.exists() else None
    for c in ("/usr/share/doc/fonts-hosny-amiri/copyright", "/usr/share/doc/fonts-noto-core/copyright"):
        if name in ("amiri",) and "amiri" in c and Path(c).exists():
            return Path(c)
        if name in ("naskh", "kufi") and "noto" in c and Path(c).exists():
            return Path(c)
    return None
