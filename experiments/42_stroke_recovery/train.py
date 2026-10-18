"""A bounded CPU pilot: image, annotated trace, and recovered-path CTC readers.

Uses PyTorch's established CTC loss; no letter segmentation or language model.
Select checkpoints on validation CER, then evaluate test once per saved run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np
import torch
from torch import nn

from dataset import OUT, json_write
from geometry import render, sequence

ARMS = ("image", "reference", "recovered")


def edit(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        next_row = [i]
        for j, y in enumerate(b, 1):
            next_row.append(min(row[j] + 1, next_row[-1] + 1, row[j - 1] + (x != y)))
        row = next_row
    return row[-1]


class Reader(nn.Module):
    def __init__(self, arm, classes):
        super().__init__()
        self.arm = arm
        if arm == "image":
            self.encoder = nn.Sequential(nn.Conv2d(1, 8, 3, padding=1), nn.GELU(), nn.MaxPool2d(2),
                                         nn.Conv2d(8, 16, 3, padding=1), nn.GELU(), nn.MaxPool2d((2, 1)),
                                         nn.Conv2d(16, 32, 3, padding=1), nn.GELU())
        else:
            self.encoder = nn.Sequential(nn.Linear(6, 32), nn.GELU())
        self.rnn = nn.LSTM(32, 64, num_layers=2, bidirectional=True, batch_first=True, dropout=.1)
        self.head = nn.Linear(128, classes + 1)

    def forward(self, x, lengths):
        if self.arm == "image":
            z = self.encoder(x).mean(2).transpose(1, 2)
            lengths = torch.full_like(lengths, z.shape[1])
        else:
            z = self.encoder(x)
        z = nn.utils.rnn.pack_padded_sequence(z, lengths.cpu(), batch_first=True, enforce_sorted=False)
        z, _ = self.rnn(z)
        z, _ = nn.utils.rnn.pad_packed_sequence(z, batch_first=True)
        return self.head(z).log_softmax(-1), lengths


def load_data(rows):
    data = {}
    for r in rows:
        with np.load(OUT / "features" / f"{r['id']}.npz", allow_pickle=False) as f:
            data[r["id"]] = {k: f[k].copy() for k in ("image", "reference", "recovered")}
    return data


def batch(rows, data, arm):
    if arm == "image":
        x = np.stack([1 - data[r["id"]][arm].astype(np.float32) / 255 for r in rows])[:, None]
        return torch.from_numpy(x), torch.full((len(rows),), 96, dtype=torch.long)
    arrays = [data[r["id"]][arm] for r in rows]
    lengths = torch.tensor([len(x) for x in arrays])
    x = np.zeros((len(rows), int(lengths.max()), 6), np.float32)
    for k, a in enumerate(arrays):
        x[k, :len(a)] = a
    return torch.from_numpy(x), lengths


def decode(logits, length, vocab):
    ids = logits[:length].argmax(-1).tolist()
    out, prev = [], None
    for i in ids:
        if i and i != prev:
            out.append(vocab[i - 1])
        prev = i
    return "".join(out)


@torch.inference_mode()
def predict(model, rows, data, vocab, arm=None):
    model.eval()
    out = []
    for start in range(0, len(rows), 48):
        rs = rows[start:start + 48]
        x, lengths = batch(rs, data, arm or model.arm)
        logits, lengths = model(x, lengths)
        for k, r in enumerate(rs):
            text = decode(logits[k], int(lengths[k]), vocab)
            out.append(dict(id=r["id"], truth=r["text"], predicted=text,
                            edits=edit(text, r["text"]), chars=len(r["text"]), exact=text == r["text"]))
    return out


def metrics(predictions):
    n = len(predictions)
    edits, chars = sum(p["edits"] for p in predictions), sum(p["chars"] for p in predictions)
    return dict(samples=n, edits=edits, chars=chars, cer=edits / chars if chars else None,
                exact=sum(p["exact"] for p in predictions),
                accuracy=sum(p["exact"] for p in predictions) / n if n else None)


def run(args):
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text())
    rows = index["samples"]
    selected = {}
    for split, limit in (("train", args.train_limit), ("valid", args.valid_limit), ("test", args.test_limit)):
        rs = sorted([r for r in rows if r["split"] == split], key=lambda r: r["id"])
        selected[split] = rs[:limit] if limit else rs
    if not all(selected.values()):
        raise ValueError("Prepare non-empty train, valid and test sets first")
    config = dict(seed=args.seed, epochs=args.epochs, train_limit=args.train_limit, valid_limit=args.valid_limit,
                  test_limit=args.test_limit, learning_rate=.002, batch_size=48, hidden=64,
                  index_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest())
    if args.initial_run:
        config["initial_run"] = args.initial_run
    run_dir = OUT / "runs" / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    config_path = run_dir / "config.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("Saved run configuration differs; choose a new --name")
    json_write(config_path, config)
    result_path = run_dir / "results.json"
    if result_path.exists():
        print(f"Completed run already exists: {result_path}", flush=True)
        return
    data = load_data([r for rs in selected.values() for r in rs])
    vocab = sorted(set("".join(r["text"] for r in selected["train"])))
    mapping = {c: i + 1 for i, c in enumerate(vocab)}
    train_texts = {r["text"] for r in selected["train"]}
    results = dict(config=config, run_name=args.name, splits={k: len(v) for k, v in selected.items()}, arms={},
                   provenance="Calliar human retracings; oracle word boundaries; prescribed character-order tracing",
                   interpretation="Small from-scratch CPU pilot. Not a comparison with mature OCR systems, "
                                  "not original writer motion, not evidence on archive scans.",
                   vocabulary=vocab, upstream=index["summary"],
                   test_unseen_characters=sorted(set("".join(r["text"] for r in selected["test"])) - set(vocab)),
                   controls={})
    if args.initial_run:
        results["interpretation"] += (" Extended after weak pilot validation. The same test set was already "
                                      "inspected; these are exploratory results, not a fresh confirmation.")
    for arm in ARMS:
        torch.manual_seed(args.seed)
        model = Reader(arm, len(vocab))
        opt = torch.optim.AdamW(model.parameters(), lr=.002)
        ctc = nn.CTCLoss(blank=0, zero_infinity=False)
        best, history, begin = float("inf"), [], time.monotonic()
        state_path, best_path = run_dir / f"{arm}.last.pt", run_dir / f"{arm}.best.pt"
        start_epoch = 0
        if not state_path.exists() and args.initial_run:
            initial = OUT / "runs" / args.initial_run
            initial_config = json.loads((initial / "config.json").read_text())
            for key in ("seed", "train_limit", "valid_limit", "test_limit", "index_sha256"):
                if initial_config[key] != config[key]:
                    raise ValueError(f"Cannot extend a different cohort or seed: {key}")
            saved_best = torch.load(initial / f"{arm}.best.pt", map_location="cpu", weights_only=False)
            if saved_best["vocab"] != vocab:
                raise ValueError("Cannot extend a different vocabulary")
            torch.save(saved_best, best_path)
            torch.save(torch.load(initial / f"{arm}.last.pt", map_location="cpu", weights_only=False), state_path)
        if state_path.exists():
            saved = torch.load(state_path, map_location="cpu", weights_only=False)
            model.load_state_dict(saved["model"])
            opt.load_state_dict(saved["optimizer"])
            start_epoch, best, history = saved["epoch"], saved["best"], saved["history"]
        for epoch in range(start_epoch, args.epochs):
            torch.manual_seed(args.seed + epoch)
            model.train()
            order = np.random.default_rng(args.seed + epoch).permutation(len(selected["train"]))
            loss_sum, count = 0., 0
            for start in range(0, len(order), 48):
                rs = [selected["train"][int(i)] for i in order[start:start + 48]]
                x, lengths = batch(rs, data, arm)
                targets = torch.tensor([mapping[c] for r in rs for c in r["text"]], dtype=torch.long)
                target_lengths = torch.tensor([len(r["text"]) for r in rs])
                logits, lengths = model(x, lengths)
                loss = ctc(logits.transpose(0, 1), targets, lengths, target_lengths)
                if not torch.isfinite(loss):
                    raise ValueError(f"Non-finite {arm} loss; do not silently ignore unalignable words")
                opt.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), 5)
                opt.step()
                loss_sum += float(loss.detach()) * len(rs)
                count += len(rs)
            val = metrics(predict(model, selected["valid"], data, vocab))
            row = dict(epoch=epoch + 1, loss=loss_sum / count, validation=val)
            history.append(row)
            if val["cer"] < best:
                best = val["cer"]
                torch.save(dict(model=model.state_dict(), arm=arm, vocab=vocab, config=config), best_path)
            torch.save(dict(model=model.state_dict(), optimizer=opt.state_dict(), epoch=epoch + 1,
                            best=best, history=history), state_path)
            json_write(run_dir / f"{arm}.history.json", history)
            print(f"{arm} epoch {epoch + 1}/{args.epochs}: loss {loss_sum / count:.3f}, "
                  f"validation CER {val['cer']:.1%}, exact {val['accuracy']:.1%}", flush=True)
        model.load_state_dict(torch.load(best_path, map_location="cpu", weights_only=False)["model"])
        predictions = predict(model, selected["test"], data, vocab)
        result = dict(parameters=sum(p.numel() for p in model.parameters()), history=history,
                      seconds=time.monotonic() - begin, test=metrics(predictions), predictions=predictions,
                      seen_text=metrics([p for p in predictions if p["truth"] in train_texts]),
                      unseen_text=metrics([p for p in predictions if p["truth"] not in train_texts]))
        results["arms"][arm] = result
        if arm == "reference":
            crossed = predict(model, selected["test"], data, vocab, arm="recovered")
            results["controls"]["reference_reader_on_recovered"] = dict(test=metrics(crossed), predictions=crossed,
                note="Input substitution without retraining; includes representation/domain shift")
        json_write(run_dir / "partial.json", results)
    results["completed"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    json_write(result_path, results)
    json_write(OUT / "results.json", results)
    print(json.dumps({a: v["test"] for a, v in results["arms"].items()}, indent=2), flush=True)


def recognise(record, run_name=None):
    torch.set_num_threads(2)
    if run_name is None:
        result_path = OUT / "results.json"
        result = json.loads(result_path.read_text()) if result_path.exists() else {}
        run_name = result.get("run_name", "pilot")
    image = cv2.resize(render(record["reference"]), (192, 48), interpolation=cv2.INTER_AREA)
    row = dict(id=record["id"], text="")
    data = {row["id"]: dict(image=image, reference=sequence(record["reference"]),
                             recovered=sequence(record["recovered"]["strokes"]))}
    predictions = {}
    for arm in ARMS:
        path = OUT / "runs" / run_name / f"{arm}.best.pt"
        if not path.exists():
            continue
        saved = torch.load(path, map_location="cpu", weights_only=False)
        model = Reader(arm, len(saved["vocab"]))
        model.load_state_dict(saved["model"])
        predictions[arm] = predict(model, [row], data, saved["vocab"])[0]["predicted"]
    return predictions


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--name", default="pilot")
    p.add_argument("--epochs", type=int, default=12)
    p.add_argument("--train-limit", type=int, default=2000)
    p.add_argument("--valid-limit", type=int, default=300)
    p.add_argument("--test-limit", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--threads", type=int, default=3)
    p.add_argument("--initial-run", help="Continue a saved run with the same cohort and seed into a new name")
    args = p.parse_args()
    if args.epochs < 1 or not 1 <= args.threads <= 4 or min(args.train_limit, args.valid_limit, args.test_limit) < 0:
        p.error("epochs must be positive, limits nonnegative, threads in 1..4")
    run(args)
