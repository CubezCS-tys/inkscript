"""Fetch the pinned Calliar release; preserve the upstream licence and provenance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
REVISION = "dc1b9f8b58bf026f79c12fc92284ea5190d04991"
BASE = f"https://raw.githubusercontent.com/ARBML/Calliar/{REVISION}"


def fetch() -> Path:
    root = OUT / "upstream"
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    for remote, name in [("LICENSE", "LICENSE"), ("README.md", "README.md"),
                         ("scripts/chars.py", "chars.py"), ("scripts/vis.py", "vis.py"),
                         ("calliar_dataset/dataset.zip", "dataset.zip")]:
        path = root / name
        if not path.exists():
            print(f"Downloading {name}", flush=True)
            with urllib.request.urlopen(f"{BASE}/{remote}", timeout=90) as response:
                data = response.read(100_000_001)
            if len(data) > 100_000_000:
                raise ValueError("Upstream file exceeds the 100 MB download limit")
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        files[name] = dict(url=f"{BASE}/{remote}", bytes=path.stat().st_size,
                           sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    manifest = dict(dataset="Calliar", revision=REVISION,
                    paper="https://arxiv.org/abs/2106.10745", licence="MIT (upstream repository)",
                    provenance="Human retracings of existing calligraphy images; not original writer motion. "
                               "Annotation order follows decomposed characters; vowel marks omitted upstream. "
                               "No original timestamps, pressure, writer or style IDs in the JSON records.",
                    files=files)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with zipfile.ZipFile(root / "dataset.zip") as archive:
        names = [x for x in archive.namelist() if x.endswith(".json")]
        print(f"{len(names)} JSON drawings; revision {REVISION}", flush=True)
        for name in names[:2]:
            drawing = json.loads(archive.read(name))
            print(name, str(drawing)[:300], flush=True)
    return root / "dataset.zip"


if __name__ == "__main__":
    fetch()
