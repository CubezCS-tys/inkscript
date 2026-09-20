#!/bin/bash
# Set up inkscript on a machine where you have NO root. Run from the cloned repo:  bash ops/setup_nosudo.sh
#
# Nothing here needs a system package. The wheels (pymupdf, opencv-python-headless, pypdfium2) carry their own
# libraries; the only system library they use is libz, which every Linux already has. `aws` is installed into
# the venv by pip, so `inkscript fetch` works without root too. LibreOffice and a system Arabic font are
# optional (only some experiment scripts draw labels with them) and are skipped silently.
set -e
cd "$(dirname "$(readlink -f "$0")")/.."

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  command -v "$c" >/dev/null 2>&1 || continue
  "$c" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null && { PY=$c; break; }
done
if [ -z "$PY" ]; then
  cat <<'MSG'
No Python 3.10+ found, and installing one needs root — unless you use uv, which is a single binary that
installs into your home directory and can bring its own Python:

    curl -LsSf https://astral.sh/uv/install.sh | sh     # installs to ~/.local/bin, no root
    export PATH="$HOME/.local/bin:$PATH"                # add this line to ~/.bashrc
    uv python install 3.12
    uv venv --python 3.12 .venv
    uv pip install -e ".[dev]" fonttools awscli
    .venv/bin/pytest -q

Then skip the rest of this script.
MSG
  exit 1
fi
echo "using $($PY -V) at $(command -v $PY)"

if [ ! -x .venv/bin/python ]; then
  if ! "$PY" -m venv .venv 2>/dev/null; then
    echo "python -m venv failed (the venv/ensurepip module is often a separate system package)."
    echo "Bootstrapping pip by hand instead..."
    "$PY" -m venv --without-pip .venv
    "$PY" - <<'PYEOF'
import urllib.request
urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", "/tmp/get-pip.py")
PYEOF
    .venv/bin/python /tmp/get-pip.py
  fi
fi

.venv/bin/python -m pip install -q -U pip
.venv/bin/python -m pip install -q -e ".[dev]" fonttools awscli
[ -f .env ] || cp .env.example .env

.venv/bin/python - <<'PYEOF'
import cv2, pymupdf, pypdfium2, numpy, fontTools
from inkscript.config import arabic_font
print(f"opencv {cv2.__version__} · pymupdf {pymupdf.__doc__.split()[1] if pymupdf.__doc__ else 'ok'} · pypdfium2 {pypdfium2.V_PYPDFIUM2} · numpy {numpy.__version__}")
print("arabic font for diagnostics:", arabic_font() or "none found (fine — only some experiment labels use one)")
PYEOF

cat <<'MSG'

Installed. Next:
  1) put GEMINI_API_KEY in .env            (only `frontpage`, `numbers`, `second` call Gemini)
  2) .venv/bin/aws configure               (a key that can read s3://mandumah-source-docs, region eu-north-1)
  3) export INKSCRIPT_DATA=$HOME/inkscript-data    (add to ~/.bashrc; where the copied inputs live)
  4) .venv/bin/pytest -q                   (about 3 minutes, builds the bundled document end to end)
MSG
