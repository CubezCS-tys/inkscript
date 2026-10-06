"""Replay the cutter on the four documents' sample pages under a named variant (patch25 flags), and keep the plans
(21's stripped form, with page) for drawing and boxes.

    ../../.venv/bin/python variants.py VARIANT [DOC...]     -> out/plans/<variant>_<doc>.pkl
VARIANT: today | any name known to patch25.VARIANTS
"""
import sys, pickle, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from replay import replay, DOCS, P
import build as B21


def run(variant, docs):
    import patch25; patch25.use(variant)
    for doc in docs:
        t = time.time(); kept, atlas = replay(doc, set(DOCS[doc]["pages"]))
        out = []
        for r, p in kept:
            s = B21.strip(p, dict(r["word"] or {}, page=r["page"])); s["page"] = r["page"]; s["cand"] = list(p["cand"]); s["scores"] = p.get("scores"); s["accepted"] = P.accepted(p); out.append(s)
        (HERE / "out/plans").mkdir(parents=True, exist_ok=True)
        pickle.dump(out, open(HERE / f"out/plans/{variant}_{doc}.pkl", "wb"))
        print(variant, doc, len(out), f"{time.time() - t:.0f}s", flush=True)
    patch25.use("today")


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2:] or list(DOCS))
