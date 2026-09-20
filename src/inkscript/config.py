"""Environment: the repo-root .env (GEMINI_API_KEY) is loaded on import, so
every entry point sees the same settings."""
from __future__ import annotations
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:  # optional
    pass

# Data lives outside the repo; on another machine point INKSCRIPT_DATA at the copy (docs/moving-to-a-server.md).
DATA_ROOT = Path(os.environ.get("INKSCRIPT_DATA", Path.home() / "Desktop" / "OCR_gem_json" / "output"))

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


def arabic_font() -> str | None:
    """A font that can draw Arabic labels, or None. Only diagnostics label pictures with it; nothing the PDFs
    need depends on a system font, so a machine without one (a server with no root) still builds everything."""
    env = os.environ.get("INKSCRIPT_ARABIC_FONT")
    if env and Path(env).exists():
        return env
    for c in _FONT_CANDIDATES:
        if Path(c).exists():
            return c
    import glob
    for pat in ("/usr/share/fonts/**/*Arabic*.ttf", str(Path.home() / ".local/share/fonts/**/*.ttf"), "/usr/share/fonts/**/*.ttf"):
        hit = sorted(glob.glob(pat, recursive=True))
        if hit:
            return hit[0]
    return None


ARABIC_FONT = arabic_font()
