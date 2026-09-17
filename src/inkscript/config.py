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

ARABIC_FONT = os.environ.get("INKSCRIPT_ARABIC_FONT", "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf")
