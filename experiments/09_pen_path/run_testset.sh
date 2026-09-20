#!/bin/bash
cd /home/cubez/Desktop/inkscript
.venv/bin/inkscript native --azure-dir /home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/azure --scan-dir /home/cubez/Desktop/OCR_gem_json/output/bakeoff_full/input --frontpage-dir /home/cubez/Desktop/OCR_gem_json/output/frontpage_set --out /home/cubez/Desktop/inkscript/experiments/09_pen_path/out/testset --vector --verify 2>&1 | grep -v -i "warning\|MuPDF error" | grep -v "^$" > /home/cubez/Desktop/inkscript/experiments/09_pen_path/out/testset/run.log
echo "DONE $(date)" >> /home/cubez/Desktop/inkscript/experiments/09_pen_path/out/testset/run.log
