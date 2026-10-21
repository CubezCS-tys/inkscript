#!/usr/bin/env python3
"""Make the copied outputs work under a home that is not /home/yassine, without sudo.

The no-sudo alternative to `sudo ln -s /home/appuser /home/yassine` (docs/moving-to-a-server.md, step 4). Run it on
the SERVER after ops/pack_v2.sh has copied everything:

    python3 ops/relocate_home.py            # dry run: counts what it would change, changes nothing
    python3 ops/relocate_home.py --apply    # does it

It rewrites the prefix /home/yassine/ to <home>/ (default: $HOME) in
  1. symlinks under <home>/inkscript/experiments/*/out and <home>/data whose target starts with it
     (the run folders in experiments/41_azure_structure/out/views, 29_catalogue/out/merged, 41's native_in, ...);
  2. text files (.json .jsonl .html .txt .md .sh .csv .tsv .xml .js .yaml .yml) in the experiments' out/ folders
     and <home>/data, plus the two tracked data files experiments/43_rehearsal/sample43.json and sample43b.json
     (git will then show those two as modified: expected, do not commit them). Other tracked files (READMEs, the
     GPU shell scripts of experiments 33/36/39) are left alone; .log files are left as the record of what ran;
  3. the stored file paths in the two platform databases (platform.db: runs, articles, judge_findings, patches;
     platform_v2.db: storage_roots, catalogue_exports). load_events keeps its history as it was.
Python code is not touched: experiments 40-47 find their files from their own location and Path.home(); the
older scripts that hard-code /home/yassine (experiments 30, 33, 36) are not read by today's code.
Re-running it is safe: a second run finds nothing to change. Stdlib only.
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

TRACKED_DATA = {"sample43.json", "sample43b.json"}
TEXT = {".json", ".jsonl", ".html", ".txt", ".md", ".sh", ".csv", ".tsv", ".xml", ".js", ".yaml", ".yml"}
SKIP_DIRS = {"venv", "env", "torchenv", "__pycache__", ".git"}
MAX_TEXT = 500 * 1024 * 1024
DB_COLUMNS = {
    "data/platform/platform.db": [("runs", "masters_dir"), ("articles", "jats_path"), ("articles", "alto_path"),
                                  ("articles", "pdf_path"), ("judge_findings", "file"), ("patches", "file")],
    "data/platform_v2/platform_v2.db": [("storage_roots", "base"), ("catalogue_exports", "file")],
}


def walk(root):
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))]
        yield dirpath, dirnames, filenames
        for d in os.listdir(dirpath):            # symlinked directories are links too
            p = os.path.join(dirpath, d)
            if os.path.islink(p) and os.path.isdir(p) and d not in filenames:
                yield dirpath, [], [d]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", default=os.path.expanduser("~"), help="the server home (default $HOME)")
    ap.add_argument("--old", default="/home/yassine", help="the laptop's home (default /home/yassine)")
    ap.add_argument("--apply", action="store_true", help="change files; without it, only count")
    a = ap.parse_args()
    home, old = Path(a.home).resolve(), a.old.rstrip("/") + "/"
    new = str(home) + "/"
    if new == old:
        sys.exit("this home is already " + old + ": nothing to do")
    oldb, newb = old.encode(), new.encode()
    repo = home / "inkscript"
    roots = [repo / "experiments", home / "data"]
    links = texts = 0
    for root in roots:
        if not root.exists():
            print(f"(missing, skipped: {root})")
            continue
        for dirpath, _dirs, files in walk(root):
            for f in files:
                p = os.path.join(dirpath, f)
                if os.path.islink(p):
                    t = os.readlink(p)
                    if t.startswith(old):
                        links += 1
                        if a.apply:
                            os.remove(p)
                            os.symlink(new + t[len(old):], p)
                    continue
                if os.path.splitext(f)[1].lower() not in TEXT:
                    continue
                if root.name == "experiments" and "/out/" not in p and f not in TRACKED_DATA:
                    continue
                try:
                    if os.path.getsize(p) > MAX_TEXT:
                        continue
                    b = open(p, "rb").read()
                except OSError:
                    continue
                if oldb in b:
                    texts += 1
                    if a.apply:
                        tmp = p + ".relocate-tmp"
                        with open(tmp, "wb") as fh:
                            fh.write(b.replace(oldb, newb))
                        os.chmod(tmp, os.stat(p).st_mode & 0o7777)
                        os.replace(tmp, p)
    rows = 0
    for rel, cols in DB_COLUMNS.items():
        db = home / rel
        if not db.exists():
            print(f"(missing, skipped: {db})")
            continue
        con = sqlite3.connect(db)
        have = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        for table, col in cols:
            if table not in have:
                continue
            n = con.execute(f'select count(*) from "{table}" where "{col}" like ?', (old + "%",)).fetchone()[0]
            rows += n
            if n and a.apply:
                con.execute(f'update "{table}" set "{col}" = ? || substr("{col}", ?) where "{col}" like ?',
                            (new, len(old) + 1, old + "%"))
        con.commit()
        con.close()
    verb = "changed" if a.apply else "would change"
    print(f"{verb}: {links} symlinks, {texts} text files, {rows} database values ({old} -> {new})")
    if not a.apply:
        print("dry run: nothing was changed. Run again with --apply.")


if __name__ == "__main__":
    main()
