"""Experiment 60: one page of a master as its reader sees it, from the ALTO (blocks in reading order, each with its
role and its text as the master holds it, fixes applied), and the comparison of two masters page by page.

    from pagedump60 import page_blocks, same_page
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

NS = {"a": "http://www.loc.gov/standards/alto/ns-v4#"}


@lru_cache(maxsize=64)
def _alto(path: str):
    return etree.parse(path)


def page_blocks(masters: Path, stem: str, page: int) -> list[tuple[str, str]]:
    """[(role, text)] of the page's text blocks in the ALTO's order (= the master's reading order)."""
    f = Path(masters) / f"{stem}.alto.xml"
    t = _alto(str(f))
    root = t.getroot()
    ns = {"a": root.nsmap.get(None, NS["a"])}
    pg = root.find(f".//a:Page[@ID='page{page}']", ns)
    if pg is None:
        return []
    out = []
    for tb in pg.iter(f"{{{ns['a']}}}TextBlock"):
        role = (tb.get("TAGREFS") or "").split()
        role = next((r for r in role if r.startswith("role.")), role[0] if role else "?")
        words = []
        for ln in tb.iter(f"{{{ns['a']}}}TextLine"):
            words += [s.get("CONTENT") for s in ln.iter(f"{{{ns['a']}}}String")]
            words.append("/")
        out.append((role.replace("role.", ""), " ".join(words).rstrip(" /")))
    return out


def same_page(m1: Path, m2: Path, stem: str, page: int) -> tuple[bool, list[str]]:
    """Whether two masters show the page alike (roles, order, text); the differences as readable lines."""
    import difflib
    a = [f"{r}: {t}" for r, t in page_blocks(m1, stem, page)]
    b = [f"{r}: {t}" for r, t in page_blocks(m2, stem, page)]
    if a == b:
        return True, []
    return False, [l for l in difflib.unified_diff(a, b, "argon", "claude", lineterm="", n=0)][2:]
