"""Experiment 43: out/prompt_v2.html, the owner's page of what prompt v2 and the code rules change: each fix in a
sentence, the prompt text before / after side by side, and a real example (crop of the scan, what experiment 41 did,
what the new rule does). Images under out/prompt_v2/ (relative paths). No model calls.

    .venv/bin/python page43.py
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompt43 as P  # noqa: E402
ST = P.ST

OUT = HERE / "out"
IMG = OUT / "prompt_v2"
E = html.escape


def snip(text: str, start: str, end: str | None) -> str:
    i = text.find(start)
    if i < 0:
        return "(not in this prompt)"
    j = text.find(end, i + len(start)) if end else -1
    return text[i:j if j > 0 else None].rstrip()


def crop(stem: str, p: int, ids: list[str], name: str, pad=0.012, width=900, full_width=False) -> str:
    a = ST.art_of(stem)
    ls = {L["id"]: L for L in ST.page_lines(a, p)[0]}
    img = cv2.imread(str(ST.page_image(a, p)))
    H, W = img.shape[:2]
    bx = ST.union([ls[i]["px"] for i in ids if i in ls])
    x0, y0, x1, y1 = bx
    if full_width:
        x0, x1 = 0.05 * W, 0.95 * W
    m = pad * W
    c = img[int(max(0, y0 - m)):int(min(H, y1 + m)), int(max(0, x0 - m)):int(min(W, x1 + m))]
    if c.shape[1] > width:
        c = cv2.resize(c, (width, int(c.shape[0] * width / c.shape[1])), interpolation=cv2.INTER_AREA)
    IMG.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(IMG / f"{name}.jpg"), c, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return f"prompt_v2/{name}.jpg"


def shot(src: str, name: str, frac=(0.0, 1.0), width=700) -> str | None:
    f = OUT / "shots" / src
    if not f.exists():
        return None
    img = cv2.imread(str(f))
    H = img.shape[0]
    img = img[int(frac[0] * H):int(frac[1] * H)]
    if img.shape[1] > width:
        img = cv2.resize(img, (width, int(img.shape[0] * width / img.shape[1])), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(IMG / f"{name}.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return f"prompt_v2/{name}.jpg"


def fig(src, cap):
    if not src:
        return f'<figure class="missing"><figcaption>{cap}</figcaption></figure>'
    return f'<figure><img src="{src}" alt="" loading="lazy"><figcaption>{cap}</figcaption></figure>'


def section(n, title, sentence, v1, v2, body):
    return f"""<section id="f{n}"><h2><span class="n">{n}</span> {E(title)}</h2>
<p class="lead">{sentence}</p>
<details class="pr"><summary>Prompt text, before and after</summary><div class="cmp">
<div><h3>v1 (experiment 41)</h3><pre dir="auto">{E(v1)}</pre></div>
<div><h3>v2 (experiment 43)</h3><pre dir="auto">{E(v2)}</pre></div></div></details>
{body}</section>"""


def main():
    V1, V2 = ST.PROMPT, P.PROMPT_V2
    rl = json.loads((OUT / "replay" / "rules_log.json").read_text())
    cmp_ = json.loads((OUT / "replay" / "compare.json").read_text())
    harness = json.loads((OUT / "replay" / "harness.json").read_text())
    tot = rl["totals"]
    sec = []

    # 1 another article
    c1 = crop("0656-016-001-011", 4, [f"4:{k}" for k in range(1, 29)], "0656_p4_top", full_width=True)
    sec.append(section(
        1, "Another article on the page",
        "A page that two articles share gets a new label, <b>other_article</b>, for the end or start of the other one. "
        "The masters keep it out of this article's text; the ALTO keeps its lines (tagged as another article); the "
        "Layout view shows it faded with a small “another article” label.",
        snip(V1, "  header, footer", "Optional on any block") + "\n...\n" + snip(V1, "- Use EVERY line id", "- \"splits\""),
        snip(V2, "  other_article", "Optional on any block"),
        '<div class="ex"><p class="case">0656, page 4 (printed page 37): the top half is the end of the previous '
        'article; this article continues below “حضارة الاسلام / بقية ص ٣٣”.</p>'
        + fig(c1, "The scan: the top half belongs to another article.")
        + '<div class="row">'
        + fig(shot("0656_41_p004.png", "0656_41", (0, 0.5)), "<b>Experiment 41</b>: Argon called all 26 lines “noise”: "
              "they left the article and the top half of our page is empty.")
        + fig(shot("0656_replay_p004.png", "0656_replay", (0, 0.5)), "<b>Replay, code rules only</b> (41's answer): the "
              "never-noise rule puts the 26 lines back as two flagged blocks of type “other”, in reading order. Nothing "
              "lost, but code cannot know they belong to another article, so they sit in this article's text.")
        + fig(shot("0656_v2sim_p004.png", "0656_v2", (0, 0.5)), "<b>With a v2 answer</b> (simulated: the 26 lines "
              "labelled other_article by hand, as prompt v2 asks): faded, labelled “another article”, out of the JATS.")
        + "</div></div>"))

    # 2 list vs body
    lab = json.loads((ST.OUT / "argon" / "labels" / "0877-007-027-003.json").read_text())
    ids = [L["id"] for L in lab["lines"] if L["block"] == 70]
    c2 = crop("0877-007-027-003", 6, ids, "0877_p6_list")
    sec.append(section(
        2, "List or body text",
        "The prompt now says when lines are a list (short parallel items, each with a number or bullet, one to three "
        "lines) and when they are paragraphs that merely open with a number (running prose; in doubt: paragraph).",
        snip(V1, "  list_item", "  reference"),
        snip(V2, "  list_item", "  reference") + "\n...\n" + snip(V2, "LISTS (v2)", "FOOTNOTE AND ENDNOTE CALLS"),
        '<div class="ex"><p class="case">0877, page 6: numbered points of several lines each.</p>'
        + fig(c2, "<b>Experiment 41</b>: the same call sent twice: once paragraphs, once list items (Argon against "
              "itself changed 62 body lines to list items on the 5 repeated articles; Flash and Argon disagreed most "
              "on exactly this). <b>v2</b>: a numbered point of running prose longer than three lines is a paragraph. "
              "Not testable without a call.") + "</div>"))

    # 3 endnotes
    c3 = crop("1769-014-002-002", 15, [f"15:{k}" for k in range(1, 9)], "1769_p15_notes")
    sec.append(section(
        3, "Endnotes and footnotes",
        "Footnotes sit at the foot of the page that calls them; endnotes are gathered at the end of the article (or "
        "a section) under a heading such as هوامش، الهوامش، المراجع والهوامش، Notes. Both are labelled and both "
        "calls are linked; the masters treat an endnote as a note linked by id from any page.",
        snip(V1, "  footnote", "  verse") + "\n" + snip(V1, "FOOTNOTE CALLS", "PAGE BREAKS"),
        snip(V2, "  footnote", "  verse") + "\n" + snip(V2, "FOOTNOTE AND ENDNOTE CALLS", "PAGE BREAKS"),
        '<div class="ex"><p class="case">1769, page 15: numbered notes at the end, called from the text by '
        'their numbers.</p>'
        + fig(c3, "<b>Experiment 41</b>: typed as 43 “reference” entries; the text's 43 calls pointed at footnotes "
              "that do not exist, so none was linked (0 of 43). Across the 55 articles 98 calls had no note, mostly "
              "for this reason. <b>v2</b>: endnote blocks “en-1” … and calls to them; code turns them into linked notes "
              "(unit-tested; no v1 answer has endnotes to replay).") + "</div>"))

    # 4 never noise
    a355 = rl["articles"]["0355-000-002-006"]["bad_splits"]
    c4 = crop("0355-000-002-006", 21, ["21:62", "21:63", "21:64"], "0355_p21_line63")
    sec.append(section(
        4, "A line with words is never noise",
        f"Noise is only for marks without words (ornaments, rules, specks). The prompt says so, and code now enforces "
        f"it after every answer: a line with words that was called noise or left out goes back into the article — "
        f"one or two lines into the block of running text they touch, a longer run as its own block flagged "
        f"“from noise” — and every case is counted. Replay of experiment 41's 55 answers: <b>{tot['never_noise']} "
        f"lines put back</b> (all 0656 page 4), <b>{tot['bad_splits']} line rescued from a broken split</b>; the "
        f"15 other noise lines with letters in experiment 41's count are specks of one to three letters at page edges (“ins”, "
        f"“هـ”, “x”, a sliver “أزواجويت” 7/1000 wide) and stay noise.",
        snip(V1, "- Use EVERY line id", "- \"splits\""),
        snip(V2, "- Use EVERY line id", "- \"splits\""),
        '<div class="ex"><p class="case">0355, page 21, line 63: one Azure line holding both columns. Argon split it '
        'but retyped أن as ان inside the parts, so experiment 41 rejected the split and the line fell out of the '
        'article (its only “dropped” line, 20 words).</p>'
        + fig(c4, "The scan around line 63.")
        + '<div class="row">'
        + fig(shot("0355_41_p021.png", "0355_41", (0.75, 1.0)), "<b>Experiment 41</b>: line 63 missing from both "
              "columns.")
        + fig(shot("0355_replay_p021.png", "0355_replay", (0.75, 1.0)), "<b>Rule in code</b>: the parts are rebuilt "
              "from Azure's own words at Argon's cut (same word count), so each column gets its half back.")
        + "</div></div>"))

    # 5 verse
    c5 = crop("0747-001-003-001", 3, ["3:4", "3:5", "3:12", "3:19", "3:20", "3:21"], "0747_p3_verse", full_width=True)
    nbox = sum(json.loads(f.read_text()).get("split_lines_word_boxed", 0) for f in (OUT / "masters" / "stats").glob("*.json"))
    sec.append(section(
        5, "Verse that Azure read as one line",
        "Where one Azure line holds both halves of a verse, the model now cuts it by word number (“cut”: the first K "
        "words are the right half) instead of retyping the two parts; decorative marks between the halves (٥ ه * « » "
        "= …) are listed as ornaments: they leave the text and their ink stays in the ALTO. Code gives each half "
        "the boxes of its own Azure words (41 cut the line's box in proportion to the letters), and finds lone "
        "ornaments at a half's inner edge as a backstop.",
        snip(V1, "  verse", "  quote") + "\n...\n" + snip(V1, "- \"splits\"", "- FIXES"),
        snip(V2, "  verse", "  quote") + "\n...\n" + snip(V2, "- \"splits\"", "- FIXES"),
        '<div class="ex"><p class="case">0747, page 3: a star ornament between the halves; Azure read it as ٥, «, . '
        'or *, and read several verses as one line.</p>'
        + fig(c5, "The scan.")
        + '<div class="row">'
        + fig(shot("0747_41_p003.png", "0747_41", (0, 0.42)), "<b>Experiment 41</b>: halves cut by letter count; "
              "ornaments either stayed in the text (٥ after غُرَّتها٢) or were removed by Argon as a “fix” (e.g. "
              "“سائلة *” → “سائلة”), mixed with real fixes.")
        + fig(shot("0747_v2_p003.png", "0747_v2", (0, 0.42)), f"<b>Rules in code</b> (replay): each half drawn from "
              f"its own Azure word boxes ({nbox} split lines in 11 articles now have word boxes); the ٥ in the first "
              f"verse left the text (ALTO role.ornament). Only {tot['ornaments_code']} ornament could be found by code "
              f"here, because Argon's fixes had already rewritten the others; v2 asks for them by word number.")
        + "</div><p class=\"note\">Honest limit: on this page the halves' boxes moved little (the ornament is glued "
          "to a word in Azure's reading, e.g. “أسد؟(٥”, which no word-level rule can separate); the run-together look "
          "in the print PDF remains for those rows.</p></div>"))

    # 6 misprints
    its = {x["id"]: x for x in json.loads((ST.OUT / "sheets" / "argon_items.json").read_text())
           + json.loads((ST.OUT / "sheets" / "flash_items.json").read_text())}
    ex6 = []
    for iid, nm, what41, what43 in (
            ("argon-fix-042", "0005_misprint", "Argon <b>fixed</b> Azure's المتعمون to المتعلمون: the edition then "
             "shows a word the page does not print.", "v2: no fix; a <b>sic</b> flag {text: المتعمون, corr: "
             "المتعلمون}; the text stays as printed."),
            ("argon-fix-044", "0018_fix", "Argon fixed أصلبا to أصلها: right (Azure took ه for ب).",
             "v2: the same fix, no flag: the print is right."),
            ("flash-fix-030", "0260_both", "Flash fixed A930 to 1930: wrong, the ink shows ٨930 (the printer set an "
             "Arabic eight).", "v2: a fix to what the ink shows (٨930) <b>and</b> a sic flag proposing 1930.")):
        x = its[iid]
        p = int(x["line"].split(":")[0])
        ex6.append(fig(crop(x["stem"], p, [x["line"].rstrip("ab")], nm),
                       f"{x['stem'][:4]} p{p} line {x['line']}: Azure “{E(x['azure_line'][:70])}”.<br>"
                       f"<b>Experiment 41</b>: {what41}<br><b>v2</b>: {what43}"))
    sec.append(section(
        6, "Misprints stay as printed",
        "The fix rule now asks before every fix: does the ink show exactly these letters? A printer's error is never "
        "repaired in the text; it gets a flag with the intended word beside it (D30). Three contrasting cases from "
        "experiments 40/41 are written into the prompt.",
        snip(V1, "- FIXES ARE FOR", "- \"math\""),
        snip(V2, "- FIXES ARE FOR", "- \"math\""),
        '<div class="ex"><p class="case">By eye in experiment 41: 4 of 40 Argon fixes were wrong, each a repaired '
        'misprint; Flash 9 of 40.</p><div class="row">' + "".join(ex6) + "</div></div>"))

    # 7 small gaps
    c7 = crop("0924-012-005-007", 5, ["5:4", "5:5", "5:6", "5:7"], "0924_p5_units", full_width=True)
    sec.append(section(
        7, "Smaller gaps from experiment 41's known problems",
        "Three cheap prompt lines and two code counts: column headings and unit words (مليم جنيه) belong to their "
        "table; an author's name is the name only, a phrase printed with it (ضبطها وشرحها، بقلم) goes in a separate "
        "“role”; “missed” is never used for running heads or page numbers. Code counts fixes that only change spacing "
        f"({tot['fixes_spacing']}, mostly Azure gluing words: right to fix) or only hamza / ya / ta marbuta forms "
        f"({tot['fixes_orthographic']}), without changing them.",
        snip(V1, "  table", "  equation") + "\n...\n" + snip(V1, "- \"missed\"", "- Return"),
        snip(V2, "  table", "  equation") + "\n...\n" + snip(V2, "- \"missed\"", "- Return") + "\n...\n"
        + snip(P.META_FULL_V2, "   (every string", None),
        '<div class="ex"><p class="case">0924, page 5: the unit words above a column of sums.</p>'
        + fig(c7, "<b>Experiment 41</b>: “مليم جنيه” opened a paragraph (twice in this article). <b>v2</b>: header "
              "cells of the table. Not testable without a call.") + "</div>"))

    t = cmp_["totals"]
    summary = f"""<section id="replay"><h2>Replay of experiment 41's 55 Argon answers through the new code</h2>
<ul>
<li>The harness first rebuilt experiment 41's masters with 41's own code: <b>{harness['same']} of 55 identical byte for
byte</b>, so every difference below comes from the new rules.</li>
<li>With the rules: JATS (the article's text) unchanged in <b>{t['jats_identical']} of 55</b>; changed on purpose in
three: 0656 (+26 lines put back, 216 words), 0355 (line 21:63 back, 20 words), 0747 (one ornament ٥ out).</li>
<li>ALTO identical in {t['alto_identical']} of 55 apart from the two new role tags; in 9 more only box coordinates
moved (split lines now drawn from their own words: {nbox} lines in 11 articles); the words are the same.</li>
<li>The owner's five hand-checked articles: 2382, 0877, 1140 identical; 0924 identical text, 29 split lines with
word boxes; 0747 one ornament out of the text, 13 split verse lines with word boxes.</li>
<li>Rule firings: never-noise {tot['never_noise']} lines, broken split repaired {tot['bad_splits']}, ornaments by code
{tot['ornaments_code']}, spacing-only fixes counted {tot['fixes_spacing']}, orthography-only fixes counted
{tot['fixes_orthographic']}. Endnotes, cuts, model ornaments and other_article cannot fire on v1 answers (0); they are
covered by unit tests ({len(list((HERE).glob('test_rules43.py')))} file, 11 tests) and the two simulated answers.</li>
</ul></section>"""
    css = """:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6860;--line:#e2ded4;--card:#fff;--acc:#8a4b14}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#17171a;--fg:#ecebe6;--mut:#a29f96;--line:#33323a;
--card:#202026;--acc:#e0a46a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}h1{font-size:1.5em;margin:.4em 0}h2{font-size:1.2em;margin:1.6em 0 .4em;
border-top:1px solid var(--line);padding-top:1em}.n{display:inline-block;min-width:1.6em;color:var(--acc)}
.lead{max-width:75ch}.case{color:var(--mut);margin:.4em 0}.note{color:var(--mut);font-size:.92em}
figure{margin:.6em 0;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px}
figure img{display:block;max-width:100%;height:auto;background:#fff}figcaption{font-size:.9em;margin-top:6px}
.row{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
details.pr{margin:.5em 0}summary{cursor:pointer;color:var(--acc)}.cmp{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.cmp pre{white-space:pre-wrap;word-break:break-word;font:12px/1.45 ui-monospace,monospace;background:var(--card);
border:1px solid var(--line);padding:8px;border-radius:6px;margin:0;max-height:480px;overflow:auto}
.cmp h3{font-size:.85em;margin:.2em 0;color:var(--mut)}
@media (max-width:700px){.cmp{grid-template-columns:1fr}}
nav a{margin-inline-end:.8em;color:var(--acc)}"""
    nav = " ".join(f'<a href="#f{k}">{k}</a>' for k in range(1, 8)) + ' <a href="#replay">replay</a>'
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prompt v2 changes</title>
<style>{css}</style></head><body><main>
<h1>Prompt v2 and the new code rules (experiment 43)</h1>
<p class="lead">What changes before the dress rehearsal, each with a real page from experiment 41. Nothing here
called Gemini: the examples are experiment 41's saved answers, replayed through the new code; “simulated” marks the two
places where an answer was relabelled by hand to show what a v2 answer would produce. Tap “Prompt text” in a section
to see the old and new instructions side by side.</p>
<nav>{nav}</nav>
{''.join(sec)}
{summary}
</main></body></html>"""
    (OUT / "prompt_v2.html").write_text(page, encoding="utf-8")
    print(OUT / "prompt_v2.html")


if __name__ == "__main__":
    main()
