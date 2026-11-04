"""Experiment 72: the instruction and the answer schema. Experiment 71's instruction (prompt71.SYSTEM, measured on its
gold) unchanged, plus the owner's rules of 2026-11-02 (docs/decisions.md D37-D44) as one added paragraph, and two
fields for them: `roles` (the role of each body named) and `inferred` (a body filled in from the journal's
publisher). The catalogue question gains one option, same_text (D44).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "71_librarian_models"))
import prompt71 as P71  # noqa: E402

PROMPT_VERSION = "72.1"

SYSTEM = P71.SYSTEM.replace("Reply with the JSON object only.", "") + """Owner's rules (2026-11-02), to apply:
- Affiliations: give "roles", one per id, in the order of "ids": current (default) | former (the POST is printed as
  past: «سابقا», «الأسبق», «السابق» qualifying the post or its holder; not when it qualifies a body's old name) |
  educated_at (the body granted the author a degree printed there: «دكتوراه من جامعة …», «Ph.D. from …»; a doctoral
  student is current). Give "inferred": "journal" only when no body is printed by name but the wording points to
  "this" body («بالكلية», «عضو المجمع», a member of the journal's own board) and the journal's publisher is that
  body; else null.
- Cited works: «صحيح مسلم بشرح النووي» is a citation of Sahih Muslim (al-Nawawi's commentary is its edition); the
  DSM's editions are one work (edition_of); a chapter cited under its own author is its own work, part_of the
  collective book; a thesis and the article drawn from it are two works (different_work; a catalogue record of the
  other one is a relation); the same text (same title and author) published in another journal, or a reprint, is
  answered same_text when that option is offered.
Reply with the JSON object only."""

USER = P71.USER
EXTRA = P71.EXTRA

SCHEMA = json.loads(json.dumps(P71.SCHEMA))
SCHEMA["properties"]["roles"] = {"type": "array", "items": {"type": "string",
                                                            "enum": ["current", "former", "educated_at"]}}
SCHEMA["properties"]["inferred"] = {"type": ["string", "null"]}
SCHEMA["required"] = SCHEMA["required"] + ["roles", "inferred"]

GSCHEMA = json.loads(json.dumps(P71.GSCHEMA))
GSCHEMA["properties"]["roles"] = {"type": "ARRAY", "items": {"type": "STRING",
                                                             "enum": ["current", "former", "educated_at"]}}
GSCHEMA["properties"]["inferred"] = {"type": "STRING", "nullable": True}
GSCHEMA["required"] = GSCHEMA["required"] + ["roles", "inferred"]
GSCHEMA["propertyOrdering"] = ["answer", "ids", "roles", "inferred", "country", "groups", "confidence", "reason"]


def extra_for(p: dict) -> str:
    return P71.extra_for(p)


def user_text(p: dict) -> str:
    return USER.format(question=p["question"], options=", ".join(p["options"]), extra=extra_for(p),
                       evidence=json.dumps(p["evidence"], ensure_ascii=False, separators=(",", ":")))
