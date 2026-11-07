#!/usr/bin/env bash
# The final reader (v7-28M) as a local service for the Desk's /try-reader page: 127.0.0.1:8171, niced, 2 threads.
#   ./serve_reader.sh          start (or restart: the previous one, by its pid file, is stopped first)
#   ./serve_reader.sh stop     stop it
# The log (out/serve_reader.log) holds only start-up lines; nothing about an uploaded image is logged or kept.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/../81_heldout_scale/out/venv/bin/python"       # torch 2.15 CPU + cv2 (what experiment 90 read with)
PORT="${PORT:-8171}"
PID="$HERE/out/serve_reader.pid"
LOG="$HERE/out/serve_reader.log"
mkdir -p "$HERE/out"
if [[ -f "$PID" ]] && kill -0 "$(cat "$PID")" 2>/dev/null; then
  kill "$(cat "$PID")"; sleep 1
fi
rm -f "$PID"
[[ "${1:-}" == "stop" ]] && { echo "stopped"; exit 0; }
cd "$HERE"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 nohup nice -n 19 ionice -c3 "$PY" serve_reader.py --port "$PORT" --threads 2 >>"$LOG" 2>&1 &
echo $! > "$PID"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "reader up on http://127.0.0.1:$PORT (pid $(cat "$PID"))"; exit 0
  fi
  sleep 0.5
done
echo "the reader did not answer on :$PORT; see $LOG" >&2; exit 1
