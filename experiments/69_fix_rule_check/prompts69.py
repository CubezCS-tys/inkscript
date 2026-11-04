"""Experiment 69: prompt v3.6 with and without its fix-rule bullet (and one reworded bullet), registered at run time
in prompt43.PROMPTS / ENRICH, so prompt43.py is not edited. The variants differ from PROMPT_V36 ONLY in that bullet.

  v3.6            prompt43.PROMPT_V36 as it is (the lead's bullet from experiment 66)
  v3.6-nofix      the same text with the bullet removed (= v3.5b's fix / sic passage + v3.6's P1-P3)
  v3.6-faded      the bullet reworded to let a fix through where the ink is faded or broken (step 5, only if run)
"""
from __future__ import annotations

import common69  # noqa: F401  (paths)
import prompt43 as P

BULLET = """- v3.6: a fix is ONLY for a word where the IMAGE plainly shows other letters than Azure's text. If the image shows
  exactly what Azure wrote, even when it looks misspelt or another word (other dots, one letter more, less or
  swapped) would read better («حال» not «مال», «بنسبة» not «بنسية», a printed «هذ» or «ثلك»), it is NOT a fix:
  a correct word stays as it is, a printer's misprint is a "sic" flag and keeps its printed letters. Never turn
  letters into the word you expect. When unsure, do not fix.
"""
assert P.PROMPT_V36.count(BULLET) == 1

FADED = """- v3.6: a fix is ONLY for a word where the IMAGE shows other letters than Azure's text. If the image clearly
  shows exactly what Azure wrote, even when it looks misspelt or another word (other dots, one letter more, less or
  swapped) would read better («حال» not «مال», «بنسبة» not «بنسية», a printed «هذ» or «ثلك»), it is NOT a fix:
  a correct word stays as it is, a printer's misprint is a "sic" flag and keeps its printed letters. Never turn
  clear printed letters into the word you expect. Where the print is faded, broken or blotted and Azure's word
  does not fit the ink that is there, the fix stays the reading the ink supports.
"""

PROMPT_V36_NOFIX = P.PROMPT_V36.replace(BULLET, "")
PROMPT_V36_FADED = P.PROMPT_V36.replace(BULLET, FADED)
assert PROMPT_V36_NOFIX != P.PROMPT_V36 and "v3.6: a fix" not in PROMPT_V36_NOFIX


def install():
    meta = P.PROMPTS["v3.6"][1]
    P.PROMPTS["v3.6-nofix"] = (PROMPT_V36_NOFIX, meta)
    P.PROMPTS["v3.6-faded"] = (PROMPT_V36_FADED, meta)
    for k in ("v3.6-nofix", "v3.6-faded"):
        P.ENRICH[k] = P.ENRICH["v3.6"]


if __name__ == "__main__":
    import difflib
    install()
    for k in ("v3.6-nofix", "v3.6-faded"):
        d = list(difflib.unified_diff(P.PROMPT_V36.splitlines(), P.PROMPTS[k][0].splitlines(), lineterm="", n=0))
        print(k, "\n".join(d))
