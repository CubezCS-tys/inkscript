#!/bin/bash
# First-time setup on a fresh Ubuntu/Debian server, run from the cloned repo:  bash ops/setup_server.sh
set -e
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip rsync awscli libgl1 libglib2.0-0 fonts-noto-core
python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -e ".[dev]" fonttools
[ -f .env ] || cp .env.example .env
echo; echo "Now: 1) put GEMINI_API_KEY in .env   2) aws configure (a key that can read s3://mandumah-source-docs)"
echo "     3) export INKSCRIPT_DATA=~/inkscript-data (add to ~/.bashrc)   4) .venv/bin/pytest -q   (about 3 minutes)"
