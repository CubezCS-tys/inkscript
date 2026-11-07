"""Experiment 89: write FINAL_READER.json (the reader phase's pick) from the score files.   python3 final89.py
Read by experiment 90 (the locked test) and experiment 86 (public benchmarks)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
O = HERE / "out"
R = ["azure", "argon", "v3", "v5", "v6r", "v7", "l28"]


def held(tag):
    d = json.loads((O / f"heldout/est89_{tag}.json").read_text())
    out = {}
    for n in R:
        if n == "azure" or n == "argon" or n == "v3" and n not in d["two_phase"]:
            row = {"all": d["all"].get(n, {}).get("letters")}
            for e in ("pre-1950", "1950-1999", "2000+"):
                row[e] = d["by_era"][e].get(n, {}).get("letters")
            row["lines_wrong"] = d["all"].get(n, {}).get("line")
        else:
            row = {e: d["two_phase"][n][e]["letters"] for e in ("all", "pre-1950", "1950-1999", "2000+")}
            row["lines_wrong"] = d["two_phase"][n]["all"]["line"]
        if n in d.get("coverage", {}):
            row["coverage_judged_pct"] = d["coverage"][n].get("judged|all|covered")
        out[n] = row
    out["paired"] = {"l28_minus_v7": d["paired_extra"].get("l28_minus_v7"), "v7_minus_v6r": d["paired_extra"].get("v7_minus_v6r"),
                     "l28_minus_azure": d["paired"]["l28"]["minus_azure"], "v7_minus_azure": d["paired"]["v7"]["minus_azure"]}
    return out


def main():
    own = json.loads((O / "owner89.json").read_text())
    tf = O / "titles/score89_titles.json"
    T = json.loads(tf.read_text()) if tf.exists() else None
    ti = None
    if T:
        ti = {f: {g: {n: {k: v[k] for k in ("letters", "words", "lines_wrong", "letters_ci", "coverage", "lines")}
                      for n, v in T[f][g].items() if n != "paired"} | {"paired": T[f][g]["paired"]}
                  for g in ("all", "pre-1950", "1950-1999", "2000+", "all without 0097")} for f in ("strict", "folded")}
        ti["lines"], ti["truth_source"] = T["with_truth"], T["truth_source"]
    fin = {
        "name": "v7-28M",
        "decided": "2026-11-06, experiment 89",
        "weights": "experiments/89_final_reader/out/weights/v7_28m/last.pt",
        "weights_sha256": "ce8ea07c6eee03fdfd0cdb6a24d60c1565c96e33f9c9f7d8a353463dd05187a0",
        "weights_also_at": "experiments/89_final_reader/out/mirror/59344074/run_l28/ep7.pt (the same epoch; best.pt there is epoch 6 by Azure-labelled dev CER, not used)",
        "format": "experiment 77's checkpoint: {model, meta{chars (462 + blank = 463 classes), arch lstm, hid 768, cw 1.5, feat 640, H 48}, dev}",
        "code": "experiments/89_final_reader/train89.py (Reader class; `python train89.py infer --ckpt CKPT --data DIR --split NAME --pred OUT.jsonl`), greedy CTC; crops cut by experiment 77's common77.cut_line(test=True) at 48 px from a 250-dpi pypdfium2 5.12.1 render of Azure's line polygon",
        "parameters": 28467000,
        "recipe": {
            "init": "from scratch (no weights), v6r's 463-class charset",
            "architecture": "CNN channels x1.5 (48,96,192,384) -> 640, 2-layer BiLSTM 768 per direction, CTC (experiment 77's l28m sweep size)",
            "data": "v3's 2.47M consensus lines (experiment 83's cut, re-cut from S3 on the host) with v6r's labels (8,012 judged lines + 42,280 bare-alif rule lines; other held disputes dropped); real lines whose Azure label has (( or )) dropped (64,373); + experiment 84's 300k synthetic lines (180k display faces, 0097 and «العربية للتربية» excluded; 120k «»/(( )) body lines labelled as rendered); 2,739,957 training lines",
            "augmentation": "train77's + experiment 84's polarity: 6% inverted, 4% dark band (real lines only)",
            "schedule": "8 epochs, AdamW, one-cycle peak 1e-3, warm-up 5% (v3's from-scratch recipe), batches of 76,800 padded columns; checkpoint = last epoch",
            "guard": "train89.py --forbid forbidden89.json: 47 journals (split76 held-out + experiment 84 locked) and 280 documents (experiment 88 locked) checked against all 3,354,235 training and label keys before training; none found",
        },
        "runner_up": {"name": "v7", "weights": "experiments/89_final_reader/out/weights/v7/last.pt",
                      "recipe": "the same data and augmentation, fine-tuned from v6r (8.4M), 3 epochs at 3e-4, warm-up 10%"},
        "scores": {
            "heldout_exp81_letters_pct_strict": held("strict"),
            "heldout_exp81_letters_pct_strict_no_0097_header": held("strict_nohdr"),
            "heldout_exp81_letters_pct_folded": held("folded"),
            "heldout_exp81_letters_pct_folded_no_0097_header": held("folded_nohdr"),
            "owner_20_pages": {r: {n: own[r]["cer"][n] for n in own[r]["cer"]} for r in ("rev1", "rev2")},
            "quotes_owner_pages": {r: {n: own[r]["quotes"][n] for n in own[r]["quotes"]} for r in ("rev1", "rev2")},
            "titles": ti,
        },
        "notes": "Held-out letters: est81's two-phase estimate for v5/v6r/v7/l28, its stratified estimate for Azure/Argon/v3 (Argon only on pages Argon read). Every number is letters wrong %, punctuation ignored, every letter counted unless 'folded'. Owner pages: rev2 = experiment 88's truth with printed «» restored (letters without punctuation cannot change).",
    }
    (HERE / "FINAL_READER.json").write_text(json.dumps(fin, ensure_ascii=False, indent=1))
    print("written FINAL_READER.json; titles", "in" if ti else "pending")


if __name__ == "__main__":
    main()
