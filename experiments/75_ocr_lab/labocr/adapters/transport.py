"""The core side of the engine contract: EngineAdapter (brief §6) over a JSONL subprocess.

The core never imports an engine.  A worker is started from an argument list (no shell, no document names or OCR
text interpolated into a command); for a rented GPU the argument list is an `ssh … python worker.py` command and the
page image travels inside the request as base64.  Each request has an id, the protocol version is checked on every
reply, every op has a timeout, and a worker that times out or dies is terminated by its own PID.
"""
from __future__ import annotations

import itertools
import json
import queue
import subprocess
import threading
import time
from typing import Optional, Protocol

from .. import PROTOCOL_VERSION
from ..schemas import (EngineCapabilities, EngineConfig, EngineHealth, ErrorRecord, Message, PageRequest,
                       PredictionResult, Reply)


class EngineAdapter(Protocol):
    def capabilities(self) -> EngineCapabilities: ...
    def health(self) -> EngineHealth: ...
    def load(self, config: EngineConfig) -> None: ...
    def predict(self, request: PageRequest) -> PredictionResult: ...
    def close(self) -> None: ...


class WorkerError(Exception):
    def __init__(self, error: ErrorRecord):
        super().__init__(f"{error.kind}: {error.message}")
        self.error = error


class SubprocessAdapter:
    """EngineAdapter backed by a worker process speaking labocr-jsonl/1."""

    def __init__(self, argv: list[str], *, timeouts: Optional[dict[str, float]] = None, env: Optional[dict] = None,
                 stderr_path: Optional[str] = None):
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
            raise TypeError("argv must be a list of strings (no shell)")
        self.argv = argv
        self.timeouts = {"capabilities": 60, "health": 120, "load": 3600, "predict": 1800, "close": 60,
                         **(timeouts or {})}
        self._ids = itertools.count(1)
        self._q: queue.Queue = queue.Queue()
        self._stderr = open(stderr_path, "ab") if stderr_path else subprocess.DEVNULL
        self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._stderr,
                                     env=env, bufsize=0)
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.load_seconds: Optional[float] = None

    # ---------------------------------------------------------------- plumbing
    def _read(self):
        for raw in self.proc.stdout:
            self._q.put(raw)
        self._q.put(None)          # EOF: the worker exited

    def _call(self, op: str, payload: Optional[dict] = None):
        if self.proc.poll() is not None:
            raise WorkerError(ErrorRecord(kind="worker_crash", message=f"worker exited with {self.proc.returncode}"))
        mid = f"m{next(self._ids)}"
        msg = Message(protocol=PROTOCOL_VERSION, id=mid, op=op, payload=payload or {})
        try:
            self.proc.stdin.write((msg.model_dump_json() + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            raise WorkerError(ErrorRecord(kind="worker_crash", message=f"cannot write to worker: {e}"))
        deadline = time.monotonic() + self.timeouts[op]
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                self.terminate()
                raise WorkerError(ErrorRecord(kind="timeout", message=f"{op} exceeded {self.timeouts[op]} s",
                                              retryable=True))
            try:
                raw = self._q.get(timeout=min(left, 1.0))
            except queue.Empty:
                continue
            if raw is not None and not raw.strip():
                continue                      # a blank line is not a reply (and carries nothing)
            if raw is None:
                self.proc.wait(timeout=10)
                raise WorkerError(ErrorRecord(kind="worker_crash",
                                              message=f"worker exited with {self.proc.returncode} during {op}",
                                              retryable=True))
            try:
                rep = Reply.model_validate_json(raw)
            except Exception as e:  # noqa: BLE001
                raise WorkerError(ErrorRecord(kind="protocol_error", message=f"bad reply line: {e}; "
                                              f"{raw[:300]!r}"))
            if rep.protocol != PROTOCOL_VERSION:
                raise WorkerError(ErrorRecord(kind="protocol_error", message=f"protocol {rep.protocol}"))
            if rep.id != mid:
                raise WorkerError(ErrorRecord(kind="protocol_error", message=f"reply id {rep.id} != {mid}"))
            if not rep.ok:
                raise WorkerError(rep.error or ErrorRecord(kind="other", message="worker said not ok"))
            return rep.result

    # ---------------------------------------------------------------- the contract
    def capabilities(self) -> EngineCapabilities:
        return EngineCapabilities.model_validate(self._call("capabilities"))

    def health(self) -> EngineHealth:
        return EngineHealth.model_validate(self._call("health"))

    def load(self, config: EngineConfig) -> None:
        t = time.monotonic()
        self._call("load", config.model_dump())
        self.load_seconds = time.monotonic() - t

    def predict_raw(self, request: PageRequest) -> dict:
        """The worker's reply exactly as sent (the run stores it before validating)."""
        return self._call("predict", request.model_dump())

    def predict(self, request: PageRequest) -> PredictionResult:
        res = self.predict_raw(request)
        try:
            return PredictionResult.model_validate(res)
        except Exception as e:  # noqa: BLE001 — keep the raw reply as evidence
            raise WorkerError(ErrorRecord(kind="invalid_output", message=f"{e}"[:2000])) from e

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self._call("close")
        except WorkerError:
            pass
        finally:
            self.terminate()

    def terminate(self) -> None:
        """Stop this worker by its own PID (never by name)."""
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        if self._stderr not in (None, subprocess.DEVNULL):
            try:
                self._stderr.close()
            except Exception:  # noqa: BLE001
                pass
