"""Experiment 101 self-test of the scoring, WITHOUT the model (experiment 100's selftest100.py, copied 2026-11-24,
unchanged but for names and paths).

    nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python selftest101.py build      # fake answers
    EXP101_MODEL=out/selftest/<variant>/model EXP101_SCORES=out/selftest/<variant>/scores  python score101.py

`clean`: every exam page written as the model would if it were perfect, from the final PAGE key (pieces in the key's
reading order; each piece's lines joined; the settled reading where R1 has one, else Azure's text), the key's
headings as `## `, list items as `* `, titles as `# `, quotes as `> `, each running head in its own <page_header>, page numbers in
<page_number>, and the first table of every TAB-key page as an HTML table from the key's own cells (in key order,
c0 first, header rows in <thead>); other tables one cell per line.

`damaged`: the same, with known damage on disjoint sets of pages (listed in out/selftest/damaged/damage.json):
  drop    40 pages lose their longest paragraph               -> Q2 missing, R2 lost, R1 omitted
  invent  30 pages get an invented 80-letter Arabic paragraph -> Q2 invented
  loop    5 pages end in a sentence repeated 30 times, finish 'length'  -> loops, cut short
  swap    every TAB table: columns 0 and 1 swapped            -> P7 cells misplaced
  digit   every TAB table: first digit of the first numeric cell changed; 60 R1 lines: one digit changed -> different text, R1 letters
  order   two-column pages: the first two body pieces swapped -> P3 two-column
  heads   20 pages: headings written as paragraphs            -> headings found

`mirror`: the clean pages with every key table written left to right as seen (rows reversed): the column direction
found from Azure's boxes must undo it (cells as in `clean`).
"""
from __future__ import annotations

import html
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert101 as V  # noqa: E402
sys.path.insert(0, V.P97)
sys.path.insert(0, f"{V.X}/99_liteparse_baseline/scripts")
import score97 as S  # noqa: E402
import score99 as S99  # noqa: E402

ST = f"{V.E}/out/selftest"


def truth_by_page():
    use, truth, _ = S99.r1_truth()
    out = {}
    for k, r in use.items():
        t = (truth.get(k) or {}).get("exact")
        if t:
            out.setdefault((r["stem"], r["page"]), {})[r["line"]] = (k, t)
    return out


def table_html(cells, n_header):
    rows = []
    for i, r in enumerate(cells):
        tag = "th" if i < n_header else "td"
        rows.append("<tr>" + "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in r) + "</tr>")
    head = "".join(rows[:n_header])
    return "<table>" + (f"<thead>{head}</thead>" if head else "") + "<tbody>" + "".join(rows[n_header:]) + "</tbody></table>"


def write_page(g, tab, texts, damage, rng):
    pieces = [p for p in g.get("pieces") or []]
    if damage.get("order"):
        body = [i for i, p in enumerate(pieces) if p.get("role") in ("paragraph", "list-item")]
        if len(body) >= 2:
            a, b = body[0], body[1]
            pieces[a], pieces[b] = pieces[b], pieces[a]
    if damage.get("drop"):
        paras = [i for i, p in enumerate(pieces) if p.get("role") == "paragraph"]
        if paras:
            k = max(paras, key=lambda i: len(pieces[i]["lines"]))
            damage["dropped_lines"] = pieces[k]["lines"]
            pieces = pieces[:k] + pieces[k + 1:]
    first_tab = None
    if tab:
        first_tab = next((t for t in tab.get("tables") or [] if t.get("cells")), None)
    out, header, footer = [], [], []
    used_tab = False
    for p in pieces:
        lines = p.get("lines") or []
        txt = " ".join(texts.get(l, "") for l in lines).strip()
        role = p.get("role")
        if role == "table":
            if first_tab and not used_tab and set(lines) & set(first_tab.get("lines") or []):
                cells = [list(r) for r in first_tab["cells"]]
                if damage.get("mirror"):         # an Arabic table written left to right, as seen
                    cells = [list(reversed(r)) for r in cells]
                if damage.get("swap"):
                    cells = [[r[1], r[0]] + r[2:] if len(r) > 1 else r for r in cells]
                if damage.get("digit"):
                    done = False
                    for r in cells:
                        for j, c in enumerate(r):
                            m = re.search(r"[0-9٠-٩]", c)
                            if m and not done:
                                d = m.group(0)
                                nd = "٠١٢٣٤٥٦٧٨٩"[("٠١٢٣٤٥٦٧٨٩".find(d) + 1) % 10] if d in "٠١٢٣٤٥٦٧٨٩" else str((int(d) + 1) % 10)
                                r[j] = c[:m.start()] + nd + c[m.end():]
                                done = True
                out.append(table_html(cells, first_tab.get("n_header_rows") or 0))
                used_tab = True
            else:
                out.append("<table>" + "".join(f"<tr><td>{html.escape(texts.get(l, ''))}</td></tr>" for l in lines) + "</table>")
            continue
        if not txt:
            continue
        if role == "running-head":
            out.append("<page_header>" + txt + "</page_header>")
        elif role == "quote":
            out.append("> " + txt)
        elif role == "page-number":
            footer.append(f"<page_number>{txt}</page_number>")
        elif role == "heading" and not damage.get("heads"):
            out.append("## " + txt)
        elif role in ("title", "title-translated"):
            out.append("# " + txt)
        elif role == "list-item":
            out.append("* " + txt)
        else:
            out.append(txt)
    if damage.get("invent"):
        out.insert(len(out) // 2, "وقد أكدت الدراسات الحديثة أن هذا المنهج يحقق نتائج مرتفعة في جميع المراحل التعليمية المختلفة دائما")
    md = []
    if header:
        md.append("<page_header>" + " ".join(header) + "</page_header>")
    md += out
    if footer:
        md.append("<page_footer>" + " ".join(footer) + "</page_footer>")
    body = "\n\n".join(md)
    if damage.get("loop"):
        body += "\n\n" + " ".join(["وهذا ما يؤكد أهمية الموضوع في هذا البحث"] * 30)
    return "```markdown\n" + body + "\n```"


def build():
    gold, _ = S.gold_set("PAGE", "final")
    tabs, _ = S.gold_set("TAB", "final")
    tab_by = {(t["stem"], int(t["page"])): t for t in tabs["files"].values() if S._is_eval_file("TAB", t)}
    tb = truth_by_page()
    pages = sorted((g["stem"], int(g["page"]), n) for n, g in gold["files"].items() if S._is_eval_file("PAGE", g))
    rng = random.Random(100)
    order = list(range(len(pages)))
    rng.shuffle(order)
    sets = dict(drop=set(order[:40]), invent=set(order[40:70]), loop=set(order[70:75]), heads=set(order[75:95]))
    r1_digit_ids = set()
    cand = [k for (st, pg), d in tb.items() for ln, (k, t) in d.items() if re.search(r"[0-9٠-٩]", t)]
    rng.shuffle(cand)
    r1_digit_ids = set(cand[:60])
    log = dict(r1_digit_ids=sorted(r1_digit_ids))
    for variant in ("clean", "damaged", "mirror"):
        d = f"{ST}/{variant}/model/exam"
        os.makedirs(d, exist_ok=True)
        for i, (stem, page, name) in enumerate(pages):
            g = gold["files"][name]
            az = S99.V.packet_page(stem, page)["azure_lines"]
            texts = {l["line"]: l["text"] for l in az}
            for ln, (k, t) in tb.get((stem, page), {}).items():
                if variant == "damaged" and k in r1_digit_ids:
                    m = re.search(r"[0-9٠-٩]", t)
                    dd = m.group(0)
                    nd = "٠١٢٣٤٥٦٧٨٩"[("٠١٢٣٤٥٦٧٨٩".find(dd) + 1) % 10] if dd in "٠١٢٣٤٥٦٧٨٩" else str((int(dd) + 1) % 10)
                    t = t[:m.start()] + nd + t[m.end():]
                texts[ln] = t
            dmg = {"mirror": True} if variant == "mirror" else {}
            if variant == "damaged":
                dmg = {k: i in s for k, s in sets.items()}
                dmg["swap"] = dmg["digit"] = True
                dmg["order"] = g.get("columns") == 2
            raw = write_page(g, tab_by.get((stem, page)), texts, dmg, rng)
            if variant == "damaged" and any(v for k, v in dmg.items() if k not in ("swap", "digit")):
                log[name] = {k: v for k, v in dmg.items() if v and k not in ("swap", "digit")}
            json.dump(dict(page=f"{stem}_p{page:03d}", set="exam", raw=raw,
                           finish_reason="length" if dmg.get("loop") else "stop",
                           usage=dict(prompt_tokens=5000, completion_tokens=24576 if dmg.get("loop") else 1500),
                           seconds=10.0, settings=dict(concurrency=16)),
                      open(f"{d}/{stem}_p{page:03d}.json", "w"), ensure_ascii=False)
        # pages with no PAGE key file (none expected): nothing written
    json.dump(log, open(f"{ST}/damaged/damage.json", "w"), ensure_ascii=False, indent=1)
    print("built", len(pages), "pages x 2 variants")


def devfake():
    """Dev scorer check (new in exp 101): Azure's own lines as the answer for all 40 dev pages under four tags.
    p1_px20 and p2_px20 clean (expect 0.0% letters wrong, a tie, P1 chosen); p1_px41 with 5 pages finish 'length'
    (expect out for loops); p2_px41 with every page's last third dropped (expect worse)."""
    import dev101 as D
    root = f"{ST}/devfake/model"
    for tag in ("p1_px20", "p1_px41", "p2_px20", "p2_px41"):
        d = f"{root}/dev_{tag}"
        os.makedirs(d, exist_ok=True)
        for i, p in enumerate(D.DEV):
            az = D.azure_lines(p["stem"], p["page"])
            lines = [l["text"] for l in az]
            if tag == "p2_px41":
                lines = lines[:max(1, 2 * len(lines) // 3)]
            loop = tag == "p1_px41" and i < 5
            json.dump(dict(page=f"{p['stem']}_p{p['page']:03d}", set="dev", raw="```markdown\n" + "\n\n".join(lines) + "\n```",
                           finish_reason="length" if loop else "stop",
                           usage=dict(prompt_tokens=2000 if "px20" in tag else 4000, completion_tokens=24576 if loop else 900),
                           seconds=5.0, settings=dict(concurrency=16)),
                      open(f"{d}/{p['stem']}_p{p['page']:03d}.json", "w"), ensure_ascii=False)
    print("devfake built:", root)


if __name__ == "__main__":
    devfake() if sys.argv[1:2] == ["devfake"] else build()
