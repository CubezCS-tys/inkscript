"""Experiment 86, step 1: unpack KITAB-Bench's parquet files into images + one jsonl of ground truth per subset.

    out/venv/bin/python dump86.py      -> data/kitab_img/<subset>/<idx>.<ext>, data/kitab_img/<subset>.jsonl

Images are written byte-for-byte as stored (no re-encoding).  Ground truth is the column the official
ocr-eval/eval.py reads ("answer" for patsocr/historicalbooks/khattparagraph, else "text"; ourslines: "data").
"""
import io
import json
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image

HERE = Path(__file__).resolve().parent
D = HERE / "data"


def main():
    for f in sorted((D / "kitab").glob("*.parquet")):
        name = f.stem
        od = D / "kitab_img" / name
        od.mkdir(parents=True, exist_ok=True)
        t = pq.read_table(f).to_pylist()
        with open(D / "kitab_img" / f"{name}.jsonl", "w", encoding="utf-8") as mf:
            for i, r in enumerate(t):
                b = r["image"]["bytes"]
                im = Image.open(io.BytesIO(b))
                ext = (im.format or "png").lower().replace("jpeg", "jpg")
                (od / f"{i:04d}.{ext}").write_bytes(b)
                gt = r.get("answer") if "answer" in r else r.get("text")
                if name == "ourslines":
                    gt = r["data"]
                mf.write(json.dumps(dict(idx=i, file=f"{i:04d}.{ext}", w=im.size[0], h=im.size[1], mode=im.mode,
                                         gt=gt, source=r.get("source")), ensure_ascii=False) + "\n")
        print(name, len(t))


if __name__ == "__main__":
    main()
