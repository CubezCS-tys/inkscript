"""Experiment 71: the one instruction and the one answer schema, the same for every model.

The conventions are the ones the librarian of experiments 56 and 62 worked under (their READMEs), written as a
librarian's house rules; nothing in them names a sampled case.
"""
from __future__ import annotations

import json

PROMPT_VERSION = "71.1"

SYSTEM = """You are the librarian of an Arabic scholarly index (Mandumah: journal articles, theses, books). Code has
already gathered the evidence for one question: the printed text, its article context, candidate cards and catalogue
records. You read it and decide, as a careful cataloguer would. You answer only from the evidence and from knowledge
you would state confidently (well-known books, authors, universities); never invent details.

House rules, cited works:
- A "card" is the machine's grouping of printed citations into one cited work. Short titles («الخزانة», «اللسان»,
  «ديوانه») are resolved by the article's own text and the other citations in the same article.
- same_work = one work, edition unknown or the same; edition_of = the same work in another printing, tahqiq or
  translation; part_of = a volume, chapter or part of the other; different_work otherwise.
- Same title and author but contradicting years, publishers or forms can still be one work (misprints); a thesis and
  a journal article drawn from it are two works.
- A card titled with a journal's or newspaper's name is not a work: drop it when it is cited only by issue or date
  (or is unpublished data / a bare web site); retitle it when it is one real item whose own title was lost;
  one_per_citation when it holds several different items.
- A catalogue record IS the cited work (links_to_publication) only when title, author, year and the venue / form
  (journal vs book vs thesis, and which journal) fit. The same text in another journal or as a book, a book review
  («عروض كتب»), a thesis summary, or an article drawn from a cited thesis is a relation, not the publication.
  no_link when unrelated.

House rules, institutions:
- An affiliation names a body when a university, ministry, centre, institute, society, company... is printed. The
  longest printed form wins; a faculty or department points to its university.
- A position, degree, place, court, or reprint source with no body printed is not_institution.
- A faculty printed without its university is unit_only, unless the page itself (city, e-mail domain, the journal's own
  publisher, the author's other statements) says which university it is.
- Generic bodies (وزارة التربية, a regional centre) are resolved per printed country; a name shared by bodies in two
  countries is chosen only by a printed place.
- Countries come from what is printed, the catalogue, the journal's publisher, or confident world knowledge.

Answer "unsure" whenever the evidence does not settle the question: an unsure costs a human a minute, a wrong answer
corrupts the index. Confidence: high = you would apply it without review; medium = probably right; low = a guess.
Reply with the JSON object only."""

USER = """Question: {question}
Options for "answer": {options}
{extra}
Evidence (JSON):
{evidence}"""

EXTRA = {
    "works_split": 'If you answer split_card, give "groups": the citation numbers of each work, e.g. [[1,3],[2]].',
    "inst_aff": ('If resolved, give "ids": the authority ids of the body or bodies named (organisation level: the '
                 'university, not its faculty), or "new:<name>" for a body not among the candidates; and "country": '
                 'the ISO 3166 alpha-2 code of the (first) body, or null.'),
    "inst_same": 'If same, give "ids": [the authority id of that body] or ["new:<name>"].',
    "inst_parent": 'If parent, give "ids": [the parent\'s authority id] or ["new:<name>"].',
    "inst_country": 'Put the ISO 3166 alpha-2 code (e.g. "EG") in "answer", or "unsure".',
}

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "ids": {"type": "array", "items": {"type": "string"}},
        "country": {"type": ["string", "null"]},
        "groups": {"type": "array", "items": {"type": "array", "items": {"type": "integer"}}},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "reason": {"type": "string"},
    },
    "required": ["answer", "ids", "country", "groups", "confidence", "reason"],
    "additionalProperties": False,
}

# Gemini's responseSchema dialect (OpenAPI subset: nullable instead of a type list)
GSCHEMA = {
    "type": "OBJECT",
    "properties": {
        "answer": {"type": "STRING"},
        "ids": {"type": "ARRAY", "items": {"type": "STRING"}},
        "country": {"type": "STRING", "nullable": True},
        "groups": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "INTEGER"}}},
        "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
        "reason": {"type": "STRING"},
    },
    "required": ["answer", "ids", "country", "groups", "confidence", "reason"],
    "propertyOrdering": ["answer", "ids", "country", "groups", "confidence", "reason"],
}


def extra_for(p: dict) -> str:
    q = p["question"]
    if p["domain"] == "works":
        return EXTRA["works_split"] if "split_card" in p["options"] else ""
    if q.startswith("Which institution"):
        return EXTRA["inst_aff"]
    if q.startswith("These machine rows"):
        return EXTRA["inst_same"]
    if q.startswith("Is this machine row a unit"):
        return EXTRA["inst_parent"]
    if q.startswith("In which country"):
        return EXTRA["inst_country"]
    return ""


def user_text(p: dict) -> str:
    return USER.format(question=p["question"], options=", ".join(p["options"]), extra=extra_for(p),
                       evidence=json.dumps(p["evidence"], ensure_ascii=False, separators=(",", ":")))
