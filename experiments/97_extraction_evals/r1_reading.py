#!/usr/bin/env python3
"""Experiment 97, R1 reading sample: 600 Azure lines from the exam pages, three witnesses each.

  (a) Azure's raw line text (azure_lines.text)
  (b) the SHOWN text: the stretch of the line's block text (blocks.text, or the page region's text) that belongs to
      this line, cut by common97.tile_block (the block's lines aligned to its text, boundaries snapped to spaces)
  (c) our own reader t91: the line box cropped from the 300 dpi page image and POSTed to http://127.0.0.1:8171/read

Sample: seed 97, lines of 3+ characters, 120 per page kind (front, body, refs, table, notes).
Writes out/reading/lines.jsonl (one line per sampled line, appended as it goes, resumable), out/reading/crops/*.png,
then out/reading/disputes.jsonl (blind: candidate readings shuffled, no witness names) and, for scoring later only,
out/reading/private/dispute_witnesses.jsonl (which witness gave which candidate; the blind agents must not read it).
Run:  nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python r1_reading.py
"""
import collections as C
import io
import json
import os
import random
import urllib.request

from PIL import Image

from common97 import OUT, PAGES, article_index, cache, exam_pages, line_targets, shown_segment, ws

SEED, PER_KIND, N_CONTROL = 97, 120, 60
READER = "http://127.0.0.1:8171"
R = f"{OUT}/reading"
os.makedirs(f"{R}/crops", exist_ok=True)
os.makedirs(f"{R}/private", exist_ok=True)
GOOD, DROP = 0.6, 0.3            # alignment similarity: >= GOOD good, < DROP dropped (kept listed, reason given)

# ---------------------------------------------------------------- the sample
pools = C.defaultdict(list)
for stem, page, kind in exam_pages():
    for l in cache(stem)["azure_lines"]:
        if l["page"] == page and len(l["text"].strip()) >= 3:
            pools[kind].append((stem, page, l["line_no"]))
rnd = random.Random(SEED)
sample = []
for kind in sorted(pools):
    for s, p, n in rnd.sample(pools[kind], min(PER_KIND, len(pools[kind]))):
        sample.append((kind, s, p, n))
assert len(sample) == 600, len(sample)

try:
    with urllib.request.urlopen(READER + "/health", timeout=10) as r:
        health = json.loads(r.read())
    reader_ok = True
except Exception as e:                                   # noqa: BLE001
    health, reader_ok = dict(error=f"{type(e).__name__}: {e}"), False
print("reader:", health, flush=True)

done = set()
LP = f"{R}/lines.jsonl"
if os.path.exists(LP):
    for x in open(LP):
        x = json.loads(x)
        done.add((x["stem"], x["page"], x["line"]))
images = {}


def page_image(stem, page):
    k = (stem, page)
    if k not in images:
        images.clear()                                   # one page in memory at a time
        pg = next(p for p in cache(stem)["pages"] if p["page"] == page)
        im = Image.open(PAGES + pg["page_image_key"]).convert("L")
        images[k] = (im, im.width / pg["width_px"], im.height / pg["height_px"])
    return images[k]


def read_t91(png: bytes):
    req = urllib.request.Request(READER + "/read", data=png, method="POST", headers={"Content-Type": "image/png"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    lines = d.get("lines") or []
    if not lines:
        return "", 0, None
    if len(lines) == 1:
        return lines[0]["text"], 1, None
    # several bands found in the crop (a neighbour line's feet or heads): keep the band nearest the crop's middle
    mid = d["size"][1] / 2
    best = min(lines, key=lambda l: abs((l["box"][1] + l["box"][3]) / 2 - mid))
    return best["text"], len(lines), [l["text"] for l in lines]


def witness_b(rec):
    """(b) the shown text; also the three agree flags.  Recomputed for every record at the end of a run, so
    lines.jsonl always follows the current common97 alignment (the reader's text (c) is kept)."""
    stem, page, n = rec["stem"], rec["page"], rec["line"]
    ix = article_index(stem)
    t = line_targets(stem, page, n)
    rec["targets"] = [f"{k}:{i}" for k, i in t]
    rec["shown"], rec["align_sim"], rec["drop_reason"] = None, None, None
    rec.pop("align_quality", None); rec.pop("shown_source", None)
    if not t:
        rec["drop_reason"] = "R2: line mapped to no block"
    elif len(t) > 1:
        roles = {ix["blocks"][i]["role"] if k == "block" else "region" for k, i in t}
        rec["drop_reason"] = f"line spread over {len(t)} targets ({'+'.join(sorted(roles))}); no single shown text"
    else:
        k, i = t[0]
        tid = i if k == "block" else f"region:{i}"
        rec["shown_source"] = ix["blocks"][i]["role"] if k == "block" else "region:" + ix["regions"][i]["role"]
        seg, sim = shown_segment(stem, page, n, tid)
        rec["shown"], rec["align_sim"] = seg, round(sim, 3)
        rec["align_quality"] = "good" if sim >= GOOD else ("weak" if sim >= DROP else "unaligned")
        if sim < DROP:
            rec["drop_reason"] = f"cannot align the line inside its block text (similarity {sim:.2f})"
    a, b, c = (x.strip() if isinstance(x, str) else None for x in (rec["azure"], rec["shown"], rec.get("t91")))
    rec["agree"] = dict(azure_shown=None if b is None else a == b, azure_t91=None if c is None else a == c,
                        shown_t91=None if (b is None or c is None) else b == c)
    rec["all_three_agree"] = None if (b is None or c is None) else (a == b == c)
    return rec


with open(LP, "a") as out:
    for kind, stem, page, n in sorted(sample, key=lambda t: (t[1], t[2], t[3])):
        if (stem, page, n) in done:
            continue
        ix = article_index(stem)
        az = ix["azure"][(page, n)]
        rec = dict(stem=stem, page=page, line=n, kind=kind, box=[az["x"], az["y"], az["w"], az["h"]])
        # crop: the Azure box plus a small margin (12 px across, 15% of the height up and down)
        im, sx, sy = page_image(stem, page)
        px, py = 12, max(4, 0.15 * az["h"])
        box = (max(0, int((az["x"] - px) * sx)), max(0, int((az["y"] - py) * sy)),
               min(im.width, int((az["x"] + az["w"] + px) * sx + 1)), min(im.height, int((az["y"] + az["h"] + py) * sy + 1)))
        crop = im.crop(box)
        cp = f"{R}/crops/{stem}_p{page:03d}_l{n:03d}.png"
        crop.save(cp)
        rec["crop"] = cp
        rec["crop_box_image_px"] = list(box)
        # (a)
        rec["azure"] = az["text"]
        witness_b(rec)
        # (c)
        rec["t91"], rec["t91_n_bands"] = None, None
        if reader_ok:
            buf = io.BytesIO()
            crop.save(buf, format="PNG")
            try:
                txt, nb, allb = read_t91(buf.getvalue())
                rec["t91"], rec["t91_n_bands"] = txt, nb
                if allb:
                    rec["t91_all_bands"] = allb
            except Exception as e:                      # noqa: BLE001
                rec["t91_error"] = f"{type(e).__name__}: {e}"
        witness_b(rec)
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

# ---------------------------------------------------------------- disputes (blind)
recs = [witness_b(json.loads(x)) for x in open(LP)]
with open(LP + ".tmp", "w") as f:
    for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
os.replace(LP + ".tmp", LP)
usable = [r for r in recs if r["shown"] is not None and r["drop_reason"] is None]
rnd = random.Random(SEED + 1)
disp, priv = [], []
agree_all = [r for r in usable if r["all_three_agree"]]
controls = {(r["stem"], r["page"], r["line"]) for r in rnd.sample(agree_all, min(N_CONTROL, len(agree_all)))}
for r in recs:
    k = (r["stem"], r["page"], r["line"])
    wit = {"azure": r["azure"], "shown": r["shown"], "t91": r["t91"]}
    wit = {w: v.strip() for w, v in wit.items() if isinstance(v, str)}
    distinct = sorted(set(wit.values()))
    is_control = k in controls
    if len(distinct) <= 1 and not is_control:
        continue
    rnd.shuffle(distinct)
    did = f"{r['stem']}_p{r['page']:03d}_l{r['line']:03d}"
    disp.append(dict(id=did, stem=r["stem"], page=r["page"], line=r["line"], crop=r["crop"], control=is_control,
                     candidates=[dict(c=i, text=t) for i, t in enumerate(distinct)],
                     note=("line not in one block: " + r["drop_reason"]) if r["drop_reason"] else None))
    priv.append(dict(id=did, witnesses={w: distinct.index(v) for w, v in wit.items()}))
with open(f"{R}/disputes.jsonl", "w") as f:
    for d in disp:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
with open(f"{R}/private/dispute_witnesses.jsonl", "w") as f:
    for d in priv:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

# ---------------------------------------------------------------- summary
three = [r for r in usable if r["t91"] is not None]
S = dict(sampled=len(recs), reader=health, reader_answered=sum(r["t91"] is not None for r in recs),
         dropped=C.Counter(r["drop_reason"].split(" (")[0].split(";")[0] for r in recs if r["drop_reason"]),
         align_quality=C.Counter(r.get("align_quality") for r in recs if r["shown"] is not None),
         three_witness_lines=len(three),
         all_three_agree=sum(r["all_three_agree"] for r in three),
         all_three_agree_rate=round(sum(r["all_three_agree"] for r in three) / max(1, len(three)), 4),
         pairwise=dict((k, round(sum(r["agree"][k] for r in three) / max(1, len(three)), 4))
                       for k in ("azure_shown", "azure_t91", "shown_t91")),
         by_kind={kind: dict(n=len(g), all_agree=round(sum(r["all_three_agree"] for r in g) / max(1, len(g)), 4),
                             azure_shown=round(sum(r["agree"]["azure_shown"] for r in g) / max(1, len(g)), 4))
                  for kind in sorted({r["kind"] for r in three}) for g in [[r for r in three if r["kind"] == kind]]},
         disputes=len(disp), controls=sum(d["control"] for d in disp),
         t91_multi_band_crops=sum(1 for r in recs if (r.get("t91_n_bands") or 0) > 1))
json.dump(S, open(f"{R}/summary.json", "w"), ensure_ascii=False, indent=1, default=dict)
print(json.dumps(S, ensure_ascii=False, indent=1, default=dict))
