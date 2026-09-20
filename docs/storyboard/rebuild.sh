#!/bin/bash
# Rebuild the storyboard from this machine's outputs (paths are the owner's; see docs/operations.md).
cd "$(dirname "$(readlink -f "$0")")/../.."; O=${INKSCRIPT_DATA:-$HOME/Desktop/OCR_gem_json/output}; X=experiments
.venv/bin/python docs/storyboard/build.py --native-dir $X/09_pen_path/out/build \
  --azure-pdf tests/fixtures/0582-004-009-012/azure/0582-004-009-012/0582-004-009-012.pdf \
  --review $O/s3_sample/review/0450-000-022-001.review.json --review-pdf $O/s3_sample/azure/0450-000-022-001/0450-000-022-001.pdf \
  --kaf-doc "$O/bakeoff_full/azure/0690-012-001,012-028/0690-012-001,012-028.json" "$O/bakeoff_full/input/0690-012-001,012-028.pdf" \
  --fi-doc $O/s3_night/azure/0565-000-002-001/0565-000-002-001.json $O/s3_night/azure/0565-000-002-001/0565-000-002-001.pdf \
  --coverage $X/09_pen_path/out/journals227_first/w00/letter_coverage.json $X/09_pen_path/out/journals227/w00/letter_coverage.json \
  --fonts $X/11_typeface/out/Inkscript-0582.ttf $X/11_typeface/out/Inkscript-0582-Restored.ttf $X/11_typeface/out/Inkscript-0565-Restored.ttf
