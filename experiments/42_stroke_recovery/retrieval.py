"""A fixed nearest-example control, independent of neural training convergence.

Every arm uses one nearest training example in its fixed representation.
This is closed-vocabulary retrieval, not open-vocabulary transcription.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "3")
import cv2
import numpy as np

from dataset import OUT, json_write
from geometry import render, sequence

ARMS = ("image", "reference", "recovered")


def edit(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        out = [i]
        for j, y in enumerate(b, 1):
            out.append(min(row[j] + 1, out[-1] + 1, row[j - 1] + (x != y)))
        row = out
    return row[-1]


def metrics(predictions):
    n = len(predictions)
    chars = sum(len(p["truth"]) for p in predictions)
    correct = sum(p["truth"] == p["predicted"] for p in predictions)
    return dict(samples=n, accuracy=correct / n if n else None,
                cer=sum(edit(p["predicted"], p["truth"]) for p in predictions) / chars if chars else None)


def features(value, arm):
    if arm == "image":
        a = 1 - cv2.resize(value, (96, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        a /= max(float(np.linalg.norm(a)), 1e-8)
    else:
        # Fixed path-distance sampling; x/y, local direction, and pen lifts.
        # This crude control has no learned warping or character boundaries.
        a = cv2.resize(value, (6, 128), interpolation=cv2.INTER_LINEAR).astype(np.float32)
        a = a * np.array([1, 1, 2, 2, .25, .25], np.float32)
    return a.ravel()


def matrix(rows, arm):
    out = []
    for r in rows:
        with np.load(OUT / "features" / f"{r['id']}.npz", allow_pickle=False) as f:
            out.append(features(f[arm], arm))
    return np.stack(out)


def nearest(queries, templates):
    values = []
    tsq = (templates * templates).sum(1)
    for start in range(0, len(queries), 64):
        q = queries[start:start + 64]
        distance = np.maximum(0, (q * q).sum(1)[:, None] + tsq - 2 * q @ templates.T)
        ks = distance.argmin(1)
        values.extend((int(k), float(distance[i, k])) for i, k in enumerate(ks))
    return values


def run(train_limit=2000, test_limit=500):
    index = json.loads((OUT / "index.json").read_text())
    train = sorted([r for r in index["samples"] if r["split"] == "train"], key=lambda r: r["id"])[:train_limit]
    test = sorted([r for r in index["samples"] if r["split"] == "test"], key=lambda r: r["id"])[:test_limit]
    train_text = {r["text"] for r in train}
    result = dict(train_samples=len(train), test_samples=len(test), arms={},
                  interpretation="One nearest training example per input, using fixed geometry features and "
                                 "Euclidean distance. Closed vocabulary: unseen words cannot be transcribed. "
                                 "Human retracings, oracle word crops, no writer/style separation. "
                                 "These controls do not establish natural motion or archive OCR accuracy.")
    for arm in ARMS:
        template = matrix(train, arm)
        query = matrix(test, arm)
        matches = nearest(query, template)
        predictions = [dict(id=r["id"], truth=r["text"], predicted=train[k]["text"], match=train[k]["id"],
                            distance=d) for r, (k, d) in zip(test, matches)]
        result["arms"][arm] = dict(test=metrics(predictions), predictions=predictions,
                                  seen_text=metrics([p for p in predictions if p["truth"] in train_text]),
                                  unseen_text=metrics([p for p in predictions if p["truth"] not in train_text]))
        print(arm, result["arms"][arm]["test"], flush=True)
    json_write(OUT / "retrieval.json", result)
    return result


_TEMPLATES = None


def recognise(record):
    global _TEMPLATES
    if _TEMPLATES is None:
        index = json.loads((OUT / "index.json").read_text())
        train = sorted([r for r in index["samples"] if r["split"] == "train"], key=lambda r: r["id"])[:2000]
        _TEMPLATES = (train, {arm: matrix(train, arm) for arm in ARMS})
    train, templates = _TEMPLATES
    values = dict(image=render(record["reference"]), reference=sequence(record["reference"]),
                  recovered=sequence(record["recovered"]["strokes"]))
    result = {}
    for arm in ARMS:
        k, d = nearest(features(values[arm], arm)[None], templates[arm])[0]
        result[arm] = dict(predicted=train[k]["text"], match=train[k]["id"], distance=d)
    return result


if __name__ == "__main__":
    run()
