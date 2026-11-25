#!/bin/bash
# Run LiteParse sandboxed as far as this box allows (no user namespaces here, so `unshare -n` is refused):
#  - own HOME, model dir and tessdata under out/; telemetry off; proxies pointed at a closed local port;
#  - every connect() the process tree makes is logged by strace to out/logs/net_<tag>.log (netcheck.py reads them);
#  - nice 19 + ionice idle; peak memory and wall time from /usr/bin/time -v into out/logs/time_<tag>.log;
#  - thread pools capped at 4.
# usage: litrun.sh <tag> lit-args...          (the `lit` CLI)
#        litrun.sh <tag> --py script.py args   (one of our scripts, run with the LiteParse venv's python -I)
set -u
X=/home/appuser/inkscript/experiments/99_liteparse_baseline
O=$X/out
TAG=$1; shift
mkdir -p $O/logs $O/runs
cd $O/runs                                   # never run from a folder holding our code
export HOME=$O/home LITEPARSE_MODEL_DIR=${LITEPARSE_MODEL_DIR:-$O/models} TESSDATA_PREFIX=$O/tessdata
export ORT_DISABLE_TELEMETRY=1 HF_HUB_OFFLINE=1 DO_NOT_TRACK=1 PYTHONNOUSERSITE=1 PYTHONPATH=
export OMP_NUM_THREADS=4 RAYON_NUM_THREADS=4 OMP_THREAD_LIMIT=4
export HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 ALL_PROXY=http://127.0.0.1:9 \
       http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 all_proxy=http://127.0.0.1:9 NO_PROXY= no_proxy=
if [ "${1:-}" = "--py" ]; then shift; CMD=("$O/venv/bin/python" -I "$@"); else CMD=("$O/venv/bin/python" -I "$O/venv/bin/lit" "$@"); fi
exec /usr/bin/time -v -o $O/logs/time_$TAG.log nice -n 19 ionice -c3 \
  strace -f -qq -e trace=connect -o $O/logs/net_$TAG.log "${CMD[@]}"
