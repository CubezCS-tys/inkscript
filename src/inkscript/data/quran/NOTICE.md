# The Quran text in this folder

Three files from the **Tanzil Project** (https://tanzil.net), shipped verbatim,
each gzip-compressed (`gzip -9n`; decompressing gives the downloaded bytes):

| file | what | sha256 of the uncompressed file |
|---|---|---|
| `quran-simple-clean.txt.gz` | Tanzil Quran Text, *Simple Clean*, version 1.1 (no diacritics, with pause marks): used for matching | `1862ee63c70fbfc6285e0bb0b9587b89beb5b7891109a4d543d9d2cf8283e8c8` |
| `quran-simple.txt.gz` | Tanzil Quran Text, *Simple*, version 1.1 (vowelled): the verse shown in the XML and reports | `b3638f5cf03e2b05e4000efc0e4b656aafb3cf6ed28f8770b6497c5b43c46089` |
| `quran-data.xml.gz` | Tanzil Quran metadata (sura names, verse counts) | `8867c1d88191472adec9db694b3cd9f135b1a2ef580574d32cf888dcb22c5c7a` |

Downloaded from `tanzil.net/pub/download/` for experiment 20 (2026-10-06).

**Licence: Creative Commons Attribution 3.0.** Tanzil's terms of use (they are
repeated in the copyright block at the end of each text file, which must stay):

- Permission is granted to copy and distribute verbatim copies of this text,
  but CHANGING IT IS NOT ALLOWED.
- This Quran text can be used in any website or application, provided that its
  source (Tanzil Project) is clearly indicated, and a link is made to
  tanzil.net to enable users to keep track of changes.
- This copyright notice shall be included in all verbatim copies of the text,
  and shall be reproduced appropriately in all files derived from or
  containing substantial portion of this text.

How inkscript honours them: the files are never edited. Normalisation
(dropping harakat, folding alef forms…) is a matching key computed in memory
(`inkscript/enrich/quran.py`). Every verse written into an output (the JATS
file's Quran notes) is Tanzil's vowelled text, verbatim, with the credit
"Tanzil Project, tanzil.net, CC BY 3.0" and a link `https://tanzil.net/#S:A`.

Why the text is shipped rather than downloaded on first use: see
`docs/decisions.md`, D20 (it is small, fixed, permitted verbatim, and the build
must run offline and give the same result on any machine).
