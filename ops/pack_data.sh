#!/bin/bash
# Copy the INPUTS this project needs (not in git, ~6 GB) to another machine, or into one folder.
#   ops/pack_data.sh user@server:/home/user/inkscript-data      (rsync over ssh; resumable, rerun to continue)
#   ops/pack_data.sh /mnt/usb/inkscript-data                    (a local folder)
# Source: $INKSCRIPT_DATA, default ~/Desktop/OCR_gem_json/output (the owner's laptop).
set -e
SRC=${INKSCRIPT_DATA:-$HOME/Desktop/OCR_gem_json/output}; DEST=$1
[ -z "$DEST" ] && { echo "usage: $0 <user@host:/path | /local/path>"; exit 1; }
# Inputs only: Azure JSON+PDF, the scans, Gemini's page-1 readings (they cost money to redo), id lists.
# Built PDFs are left out: they are reproducible and large.
rsync -avh --progress --partial \
  --include='bakeoff_full/***' --include='frontpage_set/***' \
  --include='s3_sample/' --include='s3_sample/azure/***' --include='s3_sample/frontpage/***' --include='s3_sample/review/***' --include='s3_sample/*.txt' \
  --include='s3_night/' --include='s3_night/azure/***' --include='s3_night/frontpage/***' --include='s3_night/ids.txt' \
  --include='s3_big/' --include='s3_big/azure/***' --include='s3_big/frontpage/***' --include='s3_big/ids.txt' \
  --exclude='*' "$SRC/" "$DEST/"
echo "done. On the other machine: export INKSCRIPT_DATA=<that path>"
