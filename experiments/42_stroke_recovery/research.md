# Data and interpretation

Checked 2026-10-17 against primary sources.

## Calliar

- [Authors' repository](https://github.com/ARBML/Calliar), pinned revision
  `dc1b9f8b58bf026f79c12fc92284ea5190d04991`.
- [Paper, section 3.1](https://arxiv.org/html/2106.10745v2): four annotators
  trace existing calligraphy images with a digital pen. Their prescribed
  decomposition separates letter bodies and dots, ordering them by character.
  Vowel marks and decorative characters are generally omitted.
- JSON files retain point sequences and primitive stroke annotations. These
  are observed annotator trajectories, not the original artists' trajectories.
  No timing, pressure, reliable style labels or writer identities are supplied
  in the inspected representation. Do not call the annotation sequence the
  original writing order, or its point index physical time.
- MIT licence is supplied by the repository. Keep its text and source hashes
  beside the downloads. No assertion about rights to the scraped originals is
  made by this experiment.

Calliar is useful for reconstruction diagnostics and replay. A successful
recogniser can exploit the annotation procedure's ordering and segmentation;
it would not establish natural online calligraphy recognition. Recognisers
must never receive primitive character labels as input features.

## Other sources

[Online-KHATT](https://hamzah-luqman.github.io/datasets.html) is described by
its authors as 10,040 lines from 623 writers captured on digital devices.
It is a candidate for natural writing, not assumed downloaded or available
under an unrestricted licence. Offline KHATT, Muharaf and ordinary scanned
character datasets do not supply recorded pen trajectories.

## Representation and measurement

[InkML](https://www.w3.org/TR/InkML/) records pen traces and optional dynamics.
[TRACE](https://arxiv.org/abs/2105.11559) studies learned trajectory recovery.
Neither source establishes performance on the archive. Captured traces,
human retracings and inferred paths must retain distinct provenance.

Re-rendered ink coverage measures preservation of geometry, not correct
letters, writer motion or semantics. Use identical source samples in all
recognition arms; preserve source-drawing groups across splits; report
duplicate images and text overlap. A single small pilot is not a model ranking.
