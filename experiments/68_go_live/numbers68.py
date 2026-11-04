"""Experiment 68: the numbers of a release next to the live one, with experiments 64 / 67's own measures and the
index's gate 1 (read-only).   numbers68.py BEFORE.db AFTER.db [--out out/numbers68.json]"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "64_apply_institutions"), str(HERE.parent / "67_apply_works"),
                str(HERE.parent / "49_correction_desk")]
import measure64  # noqa: E402
import measure67  # noqa: E402
from desk import index_pages  # noqa: E402


def one(p):
    i, _ = measure64.measure(Path(p))
    w = measure67.measure(p)
    g = index_pages.gate1(Path(p))
    return dict(institutions=i, works={k: v for k, v in w.items() if k not in ("top",)}, gate1=g)


if __name__ == "__main__":
    b, a = sys.argv[1], sys.argv[2]
    out = dict(before=dict(release=Path(b).name, **one(b)), after=dict(release=Path(a).name, **one(a)))
    o = Path(sys.argv[4]) if len(sys.argv) > 4 else HERE / "out" / "numbers68.json"
    o.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=str)[:12000])
