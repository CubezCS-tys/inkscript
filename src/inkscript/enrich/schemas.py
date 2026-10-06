"""The official schemas, fetched once and cached, and validation against them.

    validate_jats(path) -> list of errors ([] = valid)       JATS 1.4 Archiving DTD (MathML3 variant)
    validate_alto(path) -> list of errors                    ALTO 4.4 XSD (Library of Congress)

Cache: $INKSCRIPT_SCHEMAS, else ~/.cache/inkscript/schemas (outside the repo; nothing to commit). The first
validation downloads (JATS: one zip from NLM, 0.4 MB; ALTO: the XSD and the xlink XSD it imports, from
loc.gov). Nothing is fetched while building; only validation needs them.
"""
from __future__ import annotations

import io
import os
import urllib.request
import zipfile
from pathlib import Path

JATS_ZIP = "https://public.nlm.nih.gov/projects/jats/archiving/1.4/JATS-Archiving-1-4-MathML3-DTD.zip"
JATS_DTD = "JATS-Archiving-1-4-MathML3-DTD/JATS-archivearticle1-4-mathml3.dtd"
ALTO_XSD = "https://www.loc.gov/standards/alto/v4/alto-4-4.xsd"
XLINK_XSD = "http://www.loc.gov/standards/xlink/xlink.xsd"
VERSIONS = {"jats": "JATS 1.4 Journal Archiving and Interchange DTD, MathML3 (NISO Z39.96-2024), " + JATS_ZIP,
            "alto": "ALTO 4.4 XSD, " + ALTO_XSD}


def cache_dir() -> Path:
    d = Path(os.environ.get("INKSCRIPT_SCHEMAS") or Path.home() / ".cache" / "inkscript" / "schemas")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "inkscript (schema fetch)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def jats_dtd() -> Path:
    d = cache_dir() / "jats-1.4"
    p = d / JATS_DTD
    if not p.exists():
        z = zipfile.ZipFile(io.BytesIO(_get(JATS_ZIP)))
        for n in z.namelist():                # unpack only plain relative paths inside the expected folder
            if n.startswith("JATS-Archiving-1-4-MathML3-DTD/") and ".." not in n and not n.endswith("/"):
                out = d / n
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(z.read(n))
    return p


def alto_xsd() -> Path:
    d = cache_dir() / "alto-4.4"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "alto-4-4.xsd"
    if not p.exists():
        (d / "xlink.xsd").write_bytes(_get(XLINK_XSD))
        x = _get(ALTO_XSD).replace(XLINK_XSD.encode(), b"xlink.xsd")     # the import resolves locally
        p.write_bytes(x)
    return p


def validate_jats(path) -> list[str]:
    from lxml import etree
    dtd = etree.DTD(str(jats_dtd()))
    doc = etree.parse(str(path), etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False))
    if dtd.validate(doc):
        return []
    return [f"{e.line}: {e.message}" for e in dtd.error_log]


_alto_schema = None


def validate_alto(path) -> list[str]:
    global _alto_schema
    from lxml import etree
    if _alto_schema is None:
        _alto_schema = etree.XMLSchema(etree.parse(str(alto_xsd())))
    doc = etree.parse(str(path), etree.XMLParser(no_network=True, resolve_entities=False, huge_tree=True))
    if _alto_schema.validate(doc):
        return []
    return [f"{e.line}: {e.message}" for e in _alto_schema.error_log]
