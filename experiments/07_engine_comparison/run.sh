#!/bin/bash
S=/tmp/claude-1000/-home-cubez-Desktop-OCR-gem-json/93f783bf-a6aa-4452-9130-81759923e8c9/scratchpad/ocrmypdf; O=/home/cubez/Desktop/OCR_gem_json/output
for d in 0582-004-009-012 0655-015-003-009 0690-012-001,012-028; do
  ocrmypdf -l ara --force-ocr --jobs 4 "$O/bakeoff_full/input/$d.pdf" "$S/$d.pdf" > "$S/$d.log" 2>&1; echo "$d exit $?"
done
echo "OCRMYPDF DONE"
