"""Refresh the shareholder deck's numbers from GET /desk/api/headlines (experiment 73, agent C, 2026-11-03).

Every live number in web/public/pitch/index.html sits in an element carrying data-h="<dotted key>" (list indexes
as numbers, e.g. gate2.shared_authors.0) and data-f="<format>". This script fetches the headlines JSON, formats each
value and rewrites the element's text when it differs, printing every change. A key missing from the JSON keeps the
value written in the deck (those are the measured values of 2-3 Nov 2026, sourced in the speaker notes) and is
reported. Nothing is invented: derived keys (names starting with "=") are computed from headline values only.

    .venv/bin/python ../73_desk_showcase/fill_deck_c.py --token-file <file> [--url URL] [--dry-run]
    .venv/bin/python ../73_desk_showcase/fill_deck_c.py --json headlines.json [--dry-run]

Formats: n (integer with thousands commas), d1 / d2 (fixed decimals), usd2 (two decimals), raw (as in the JSON).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

DECK = Path(__file__).resolve().parents[1] / "49_correction_desk" / "web" / "public" / "pitch" / "index.html"
URL = "http://127.0.0.1:8005/desk/api/headlines"
TAG = re.compile(r'(<(span|b|strong|div)\b[^>]*\bdata-h="([^"]+)"[^>]*\bdata-f="([^"]+)"[^>]*>)([^<]*)(</\2>)')


def derived(h: dict, key: str):
    if key == "=nine_usd":   # the other nine of gate 2's ten = ten at measured rates minus the pilot, to the nearest $10
        ten, pilot = h.get("gate2", {}).get("ten_journals_usd"), h.get("gate2", {}).get("cost_usd")
        return None if ten is None or pilot is None else int(round((ten - pilot) / 10.0) * 10)
    return None


def lookup(h: dict, key: str):
    if key.startswith("="):
        return derived(h, key)
    cur = h
    for part in key.split("."):
        if isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        elif isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur if isinstance(cur, (int, float)) and not isinstance(cur, bool) else None


def fmt(v, f: str) -> str:
    if f == "n":
        return f"{int(round(v)):,}"
    if f == "d1":
        return f"{v:.1f}"
    if f == "d2":
        return f"{v:.2f}"
    if f == "usd2":
        return f"{v:,.2f}"
    return str(v)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=URL)
    ap.add_argument("--token-file", help="file holding an X-Desk-Token (never printed)")
    ap.add_argument("--json", help="read the headlines from this file instead of the API")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.json:
        h = json.loads(Path(a.json).read_text(encoding="utf-8"))
    else:
        req = urllib.request.Request(a.url)
        if a.token_file:
            req.add_header("X-Desk-Token", Path(a.token_file).read_text().strip())
        with urllib.request.urlopen(req, timeout=120) as r:
            h = json.loads(r.read().decode("utf-8"))
    html = DECK.read_text(encoding="utf-8")
    changes, missing, seen = [], set(), 0

    def sub(m):
        nonlocal seen
        seen += 1
        key, f, old = m.group(3), m.group(4), m.group(5)
        v = lookup(h, key)
        if v is None:
            missing.add(key)
            return m.group(0)
        new = fmt(v, f)
        if new != old:
            changes.append((key, old, new))
        return m.group(1) + new + m.group(6)

    out = TAG.sub(sub, html)
    print(f"release {h.get('release')}: {seen} numbers, {len(changes)} changed, {len(missing)} keys missing")
    for k, o, n in changes:
        print(f"  {k}: {o} -> {n}")
    for k in sorted(missing):
        print(f"  missing (kept as written): {k}")
    if changes and not a.dry_run:
        DECK.write_text(out, encoding="utf-8")
        print(f"wrote {DECK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
