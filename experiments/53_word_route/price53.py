"""Experiment 53: what a text-only Gemini step would cost on the Word route (no calls; estimates only).

Two shapes of the call, priced from the real text of the 139 masters (out/masters, out/build.json):
  lean   a short text-only prompt (8,000 characters: block roles, reference fields, the enrich fields) + only what
         code is unsure of: the front lines kept as printed blocks, the headings found by weak signals (bold only,
         colon, centring) and the run-in bold paragraphs, each with its neighbour paragraph as context (x3), the
         table and figure captions, and the reference list
  full   a v3.5b-sized prompt (21,870 characters, prompt43.PROMPTS["v3.5b"]) + the whole article as blocks with ids
Output, both: the parts of every reference (239 characters of JSON a work: the mean of the 1,718 parsed references
in experiment 43's v33_300b_fix3 answers) + 15 tokens a block role asked + 400 tokens of enrich fields; "full" also
returns a role and level for every heading (12 tokens each).
Tokens: the project's own rule (run43.estimate): characters / 2.6, input x 1.117 (its calibration on experiment 41's
billed Argon chunks). Prices, $ per million tokens in / out, Batch (half of Standard): Argon 1 / 5 until 2026-11-30,
2 / 10 from 2026-12-01; Flash 3.8 0.375 / 1.875 until 2026-12-31, 0.75 / 3.75 from 2027-01-01.
-> stdout, out/price.json.
"""
import json
import statistics
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
CPT, IN_FACTOR = 2.6, 1.117
PROMPT_LEAN, PROMPT_FULL = 8000, 21870
REF_JSON, ROLE_TOK, ENRICH_TOK, HEAD_TOK = 239, 15, 400, 12
PRICES = {"Argon Batch now": (1.0, 5.0), "Argon Batch from 1 Dec": (2.0, 10.0),
          "Flash 3.8 Batch now": (0.375, 1.875), "Flash 3.8 Batch from 1 Jan 2027": (0.75, 3.75)}


def tx(e):
    return " ".join("".join(e.itertext()).split())


def main():
    build = {r["stem"]: r for r in json.loads((OUT / "build.json").read_text())}
    rows = []
    for stem, r in build.items():
        st = r.get("stats", {})
        t = etree.parse(str(OUT / "masters" / f"{stem}.jats.xml"), etree.XMLParser(load_dtd=False, no_network=True))
        refs = [tx(m) for m in t.iter("mixed-citation")]
        caps = [tx(c) for c in t.iter("caption")] + [tx(lb) for lb in t.iter("label")]
        front = [cm.findtext("meta-value") or "" for cm in t.iter("custom-meta")
                 if cm.findtext("meta-name") == "front-matter-block"]
        heads = list(t.iter("title"))
        n_weak = st.get("headings_by_bold", 0) + st.get("headings_by_colon", 0) + st.get("headings_by_centre", 0) + \
            st.get("run_in_bold_heads", 0)
        mean_head = statistics.mean([len(tx(h)) for h in heads]) if heads else 40
        mean_par = r["chars"] / max(1, st.get("blocks_mapped", 1))
        unsure_chars = n_weak * (mean_head + 2 * mean_par)            # the heading and a paragraph either side
        lean_in = PROMPT_LEAN + sum(map(len, refs)) + sum(map(len, caps)) + sum(map(len, front)) + unsure_chars + \
            8 * (len(refs) + n_weak + len(front))
        full_in = PROMPT_FULL + r["chars"] + 8 * st.get("blocks_mapped", 0)
        out_common = len(refs) * REF_JSON / CPT + ENRICH_TOK
        lean_out = out_common + ROLE_TOK * (n_weak + len(front))
        full_out = out_common + ROLE_TOK * (n_weak + len(front)) + HEAD_TOK * st.get("headings", 0)
        rows.append(dict(stem=stem, chars=r["chars"], refs=len(refs), weak=n_weak,
                         lean_in=lean_in / CPT * IN_FACTOR, lean_out=lean_out,
                         full_in=full_in / CPT * IN_FACTOR, full_out=full_out))
    res = {}
    for shape in ("lean", "full"):
        tin = statistics.mean(r[f"{shape}_in"] for r in rows)
        tout = statistics.mean(r[f"{shape}_out"] for r in rows)
        res[shape] = dict(in_tokens=round(tin), out_tokens=round(tout),
                          usd={k: round(tin / 1e6 * a + tout / 1e6 * b, 4) for k, (a, b) in PRICES.items()})
        print(f"{shape}: {tin:,.0f} input + {tout:,.0f} output tokens an article")
        for k, v in res[shape]["usd"].items():
            print(f"   {k:<34} ${v:.4f} an article, ${v * 1000:,.0f} per 1,000, ${v * 308593:,.0f} for the 308,593")
    res["articles"] = len(rows)
    res["mean_chars"] = round(statistics.mean(r["chars"] for r in rows))
    res["mean_refs"] = round(statistics.mean(r["refs"] for r in rows), 1)
    res["mean_weak_blocks"] = round(statistics.mean(r["weak"] for r in rows), 1)
    print(f"{len(rows)} articles: {res['mean_chars']:,} characters, {res['mean_refs']} references, "
          f"{res['mean_weak_blocks']} weak-signal headings / run-in heads an article")
    (OUT / "price.json").write_text(json.dumps(dict(summary=res, rows=rows), indent=1))


if __name__ == "__main__":
    main()
