"""Experiment 102: what every example is, shared by train102.py, eval102.py and the self-test.

  line crop (tar shards of <key>.jpg, cut102.py)  ->  model image (cut102.model_image: height H, white padding left,
  width a multiple of 32)  ->  chat: system = prompts/system102.txt, user = [image, "Read this line."]  ->  answer =
  the line's text, then <|im_end|>.  Thinking is off (enable_thinking=False: the template then ends the prompt with
  "<think>\\n\\n</think>\\n\\n", exactly what vLLM sends at inference).  Loss only on the answer tokens.
"""
from __future__ import annotations

import io
import json
import os
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
USER_TEXT = "Read this line."
SYSTEM_FILE = HERE / "prompts" / "system102.txt"
IM_END = "<|im_end|>"


def system_prompt(path=None) -> str:
    return Path(path or SYSTEM_FILE).read_text(encoding="utf-8").strip()


def messages(system: str):
    return [{"role": "system", "content": [{"type": "text", "text": system}]},
            {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": USER_TEXT}]}]


class LineStore:
    """Reads <key>.jpg members from tar shards by offset (no extraction); one open file per shard per process."""

    def __init__(self, dirs):
        self.where = {}
        for d in ([dirs] if isinstance(dirs, (str, Path)) else dirs):
            for t in sorted(Path(d).glob("*.tar")):
                with tarfile.open(t) as tf:
                    for m in tf.getmembers():
                        if m.name.endswith(".jpg"):
                            self.where[m.name[:-4]] = (str(t), m.offset_data, m.size)
        self._fh = {}

    def __contains__(self, key):
        return key in self.where

    def __len__(self):
        return len(self.where)

    def bytes(self, key: str) -> bytes:
        p, off, n = self.where[key]
        fh = self._fh.get((os.getpid(), p))
        if fh is None:
            fh = self._fh[(os.getpid(), p)] = open(p, "rb")
        fh.seek(off)
        return fh.read(n)

    def gray(self, key: str):
        import numpy as np
        from PIL import Image
        return np.array(Image.open(io.BytesIO(self.bytes(key))).convert("L"))


def read_set(path, limit: int = 0) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for l in f:
            if l.strip():
                rows.append(json.loads(l))
                if limit and len(rows) >= limit:
                    break
    return rows
