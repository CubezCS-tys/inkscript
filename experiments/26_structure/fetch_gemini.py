"""Fetch the Gemini title files already in the bucket (free: no Gemini call) for the 20-document set.

    python fetch_gemini.py [AZURE_DIR]   -> out/gemini/<id>.gemini.title.json (only where the bucket has one)
"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AZ = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "24_product" / "out" / "azure"
AWS = str(Path(sys.executable).parent / "aws")
OUT = HERE / "out" / "gemini"
OUT.mkdir(parents=True, exist_ok=True)
for d in sorted(os.listdir(AZ)):
    for name in (f"{d}.gemini.title.json", f"{d}.html"):
        if (OUT / name).exists():
            continue
        r = subprocess.run([AWS, "s3", "cp", f"s3://mandumah-source-docs/{d}/{name}", str(OUT / name)],
                           capture_output=True, text=True)
        print(d, name, "ok" if r.returncode == 0 else "none")
