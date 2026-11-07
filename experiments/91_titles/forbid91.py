"""Experiment 91: the guard's list for the GPU host, forbidden91.json (local, no network); experiment 89's forbid89.py
with this folder's URL lists and label files.

    python3 forbid91.py      -> out/gpu/up/forbidden91.json, then checks every local training input against it

journals: split76's 27 held-out codes + experiment 84's 20 locked journals; documents: experiment 88's locked
old-print documents.  train91.py --forbid refuses to train if any training or label key belongs to one of them.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "88_truth_and_lock"))
from locked_old import assert_not_locked, locked_codes, locked_docs  # noqa: E402

OUT = HERE / "out/gpu/up"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    held = json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"]
    fb = dict(journals=sorted(set(held) | set(locked_codes())), documents=sorted(locked_docs()),
              note="exp 91 guard: split76 held-out journals + exp 84 locked journals + exp 88 locked old documents")
    (OUT / "forbidden91.json").write_text(json.dumps(fb, indent=0))
    print(len(fb["journals"]), "journals,", len(fb["documents"]), "documents forbidden")
    codes, docs = set(fb["journals"]), set(fb["documents"])
    keys = [json.loads(l)["key"] for l in open(E / "85_disputes/out/labels/labels_v6r.jsonl", encoding="utf-8")]
    assert_not_locked(keys)
    assert not [k for k in keys if k[:4] in codes], "held-out key in v6r labels"
    print(len(keys), "v6r label keys: none held out or locked")
    for f in sorted(OUT.glob("urls_*.jsonl")):
        ids = [json.loads(l)["id"] for l in open(f, encoding="utf-8")]
        assert_not_locked(ids)
        assert not [i for i in ids if i[:4] in codes or i in docs], f
        print(f.name, len(ids), "documents: none held out or locked")


if __name__ == "__main__":
    main()
