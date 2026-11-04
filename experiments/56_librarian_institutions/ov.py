"""Append the librarian's overrides (one JSON object per affiliation key) to overrides56.json."""
import json, sys
from pathlib import Path
P = Path(__file__).resolve().parent / "overrides56.json"


def add(items: dict):
    d = json.loads(P.read_text(encoding="utf-8")) if P.exists() else {}
    for k, v in items.items():
        d[k] = v
    P.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(d), "overrides")
