"""The documentation must not point at things that are gone."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "CLAUDE.md", ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "experiments" / "README.md",
        *sorted((ROOT / "docs").glob("*.md")), *sorted((ROOT / "experiments").glob("*/README.md"))]


def test_markdown_links_resolve():
    missing = []
    for doc in DOCS:
        for target in re.findall(r"\]\(([^)#]+?)(?:#[^)]*)?\)", doc.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("mailto:"):
                continue
            if not (doc.parent / target).exists():
                missing.append(f"{doc.relative_to(ROOT)} -> {target}")
    assert not missing, missing


def test_named_source_files_exist():
    """Paths written in backticks that look like files of this repo (src, experiments, tests, docs)."""
    missing = []
    for doc in DOCS:
        for ref in re.findall(r"`((?:src|experiments|tests|docs)/[\w./,-]+\.(?:py|sh|md|html))`", doc.read_text(encoding="utf-8")):
            if not (ROOT / ref).exists():
                missing.append(f"{doc.relative_to(ROOT)} -> {ref}")
    assert not missing, missing


def test_every_experiment_is_indexed():
    index = (ROOT / "experiments" / "README.md").read_text(encoding="utf-8")
    numbers = {p.name[:2] for p in (ROOT / "experiments").iterdir() if p.name[:2].isdigit()}
    assert all(re.search(rf"\b{n}\b", index) for n in numbers), numbers
    for d in (ROOT / "experiments").iterdir():
        if d.is_dir() and d.name[:2].isdigit():
            assert (d / "README.md").exists(), f"{d.name} has no README"
