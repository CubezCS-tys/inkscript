"""Validate Calliar annotations, split words, rasterise and recover paths locally."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

import cv2
import numpy as np

from fetch import OUT, REVISION, fetch
from geometry import normalise, recover, render, sequence

# From the authors' scripts/chars.py (MIT); preserve their annotation protocol.
PARTS = {
    "\u0623": "\u0621\u0627", "\u0622": "\u0605\u0627", "\u0625": "\u0627\u0621",
    "\u0628": "\u066e.", "\u062a": "..\u066e", "\u062b": "...\u066e",
    "\u062c": "\u062d.", "\u062e": ".\u062d", "\u0630": ".\u062f",
    "\u0632": ".\u0631", "\u0634": "...\u0633", "\u0636": ".\u0635",
    "\u0637": "\u0627\ufebb", "\u0638": ".\u0627\ufebb", "\u063a": ".\u0639",
    "\u0641": ".\u066f", "\u0642": "..\u066f", "\u06a4": "...\u066f",
    "\u0643": "\u0621\u0644", "\u0646": ".\u06ba", "\u0624": "\u0621\u0648",
    "\u064a": "\u0649..", "\u0626": "\u0621\u0649", "\u0629": "..\u0647",
}


def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def annotation(name):
    text = re.sub(r"_\d+$", "", Path(name).stem)
    return re.sub(r"[\u064b-\u0652\dA-Za-z\u00f6\u00a0_]", "", text).strip()


def word_traces(name, drawing):
    """Use upstream character decomposition for oracle word boundaries only.

    Reject mismatched primitive sequences rather than silently pairing a word
    with another word's strokes. Primitive labels never reach a recogniser.
    """
    text = annotation(name)
    if not isinstance(drawing, list) or not drawing:
        raise ValueError("empty drawing")
    keys, strokes = [], []
    for item in drawing:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError("invalid stroke record")
        key, pts = next(iter(item.items()))
        a = np.asarray(pts, dtype=float)
        if a.ndim != 2 or a.shape[1] != 2 or not len(a) or not np.isfinite(a).all():
            raise ValueError("invalid stroke points")
        keys.append(key)
        strokes.append(pts)
    expected, sizes = [], []
    words = text.split()
    for word in words:
        parts = "".join("\ufedb" if c == "\u0643" and k < len(word) - 1 else PARTS.get(c, c)
                        for k, c in enumerate(word))
        expected.extend(parts)
        sizes.append(len(parts))
    if expected != keys:
        raise ValueError(f"primitive labels mismatch ({len(expected)} expected, {len(keys)} recorded)")
    result, start = [], 0
    for word, size in zip(words, sizes):
        result.append((word, strokes[start:start + size]))
        start += size
    return result


def prepare(refresh=False):
    source = OUT / "upstream" / "dataset.zip"
    if not source.exists():
        fetch()
    records, rejected, duplicates = [], [], []
    seen = {}
    with zipfile.ZipFile(source) as z:
        names = [n for n in z.namelist() if n.endswith(".json")]
        # Prefer held-out copies, so an exact held-out raster never enters train.
        priority = {"test": 0, "valid": 1, "train": 2}
        names.sort(key=lambda n: (priority[n.split("/")[1]], n))
        for ni, name in enumerate(names):
            split = name.split("/")[1]
            try:
                words = word_traces(name, json.loads(z.read(name)))
            except (ValueError, TypeError) as exc:
                rejected.append(dict(source=name, reason=str(exc)))
                continue
            for wi, (text, strokes) in enumerate(words):
                ident = hashlib.sha256(f"{name}:{wi}".encode()).hexdigest()[:16]
                target = OUT / "records" / f"{ident}.json"
                cached = json.loads(target.read_text()) if target.exists() else None
                reference = normalise(strokes)
                image = render(reference)
                digest = hashlib.sha256(image.tobytes()).hexdigest()
                if digest in seen:
                    duplicates.append(dict(source=name, word=wi, split=split, text=text,
                                           matches=seen[digest]))
                    continue
                seen[digest] = dict(source=name, word=wi, split=split, text=text)
                reuse = (not refresh and cached and cached.get("source_revision") == REVISION
                         and cached.get("raster_sha256") == digest)
                if reuse:
                    record = cached
                else:
                    recovered = recover(image)
                    record = dict(id=ident, schema="inkscript-strokes/1", dataset="Calliar", split=split,
                                  parent=name, text=text, word_index=wi, source_revision=REVISION,
                                  provenance="human_retracing", timing="unavailable", style="unlabelled",
                                  segmentation="oracle word boundary from upstream primitive annotation",
                                  reference=reference, recovered=recovered, raster_sha256=digest,
                                  width=image.shape[1], height=image.shape[0])
                    json_write(target, record)
                asset = OUT / "assets" / f"{ident}.png"
                asset.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(asset), image)
                cache = OUT / "features" / f"{ident}.npz"
                cache.parent.mkdir(parents=True, exist_ok=True)
                if not reuse or not cache.exists():
                    np.savez_compressed(cache, image=cv2.resize(image, (192, 48), interpolation=cv2.INTER_AREA),
                                        reference=sequence(reference),
                                        recovered=sequence(record["recovered"]["strokes"]))
                records.append({k: record[k] for k in ("id", "dataset", "split", "parent", "text",
                                                       "provenance", "style", "segmentation")}
                               | dict(ink_coverage=record["recovered"]["ink_coverage"],
                                      failures=len(record["recovered"]["failures"])))
            if (ni + 1) % 100 == 0:
                print(f"{ni + 1}/{len(names)} drawings, {len(records)} words, {len(rejected)} rejected", flush=True)
    train_text = {r["text"] for r in records if r["split"] == "train"}
    counts = Counter(r["split"] for r in records)
    summary = dict(source_drawings=len(names), words=len(records), splits=dict(counts),
                   rejected_drawings=len(rejected), duplicate_word_rasters=len(duplicates),
                   parents_by_split={s: len({r["parent"] for r in records if r["split"] == s}) for s in counts},
                   heldout_unseen_text={s: sum(r["text"] not in train_text for r in records if r["split"] == s)
                                        for s in ("valid", "test")},
                   mean_ink_coverage=float(np.mean([r["ink_coverage"] for r in records])) if records else None,
                   words_with_recovery_failures=sum(r["failures"] > 0 for r in records),
                   notes=["Human retracing, not original writing motion; no timestamps or pressure.",
                          "Oracle word segmentation and prescribed character-order tracing favour the reference arm.",
                          "Upstream random drawing splits are not writer- or style-disjoint.",
                          "Identical normalised word rasters kept once, preferring test then valid then train.",
                          "All arms include recovery failures; no success-only recognition denominator."])
    json_write(OUT / "index.json", dict(summary=summary, samples=records))
    json_write(OUT / "audit.json", dict(rejected=rejected, duplicates=duplicates))
    print(json.dumps(summary, indent=2), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Recompute paths/features after preparation code changes")
    prepare(parser.parse_args().refresh)
