"""Two builds of the same documents: which letter boxes moved? The tool for judging a change to the letter cutter.

    python compare_boxes.py OLD_DIR NEW_DIR [--top 20]

Looks for <stem>_vector.pdf anywhere under each directory. Per document: characters whose text is the same in
both builds, the share of them whose box moved by more than half a point, letter coverage before and after,
and whether the copied text changed at all (it should not). Writes NEW_DIR/box_changes.json."""
import sys, glob, os, re, json
import pypdfium2 as pdfium


def read(pdf):
    a = pdfium.PdfDocument(pdf); pages = []
    for pi in range(len(a)):
        page = a[pi]; tp = page.get_textpage(); t = tp.get_text_range()
        pages.append((t, [tuple(round(v, 1) for v in tp.get_charbox(k)) for k in range(len(t))])); tp.close(); page.close()
    a.close(); return pages


def coverage(t, boxes):
    cut = tot = 0; k = 0
    for w in re.split(r"(\s+)", t):
        if re.fullmatch(r"[ء-ي]{2,}", w):
            n = len(set(boxes[k:k + len(w)])); lig = len(re.findall("لا|لأ|لإ|لآ", w)); tot += 1; cut += n >= len(w) - lig
        k += len(w)
    return cut, tot


def main(old, new, top=20):
    find = lambda d: {os.path.basename(f)[:-len("_vector.pdf")]: f for f in glob.glob(f"{d}/**/*_vector.pdf", recursive=True)}
    A, B = find(old), find(new); rows = []
    for stem in sorted(set(A) & set(B)):
        pa, pb = read(A[stem]), read(B[stem]); same = moved = 0; text_same = True; c0 = n0 = c1 = n1 = 0
        for (ta, ba), (tb, bb) in zip(pa, pb):
            x, y = coverage(ta, ba); c0 += x; n0 += y; x, y = coverage(tb, bb); c1 += x; n1 += y
            if ta != tb: text_same = False; continue
            same += len(ta); moved += sum(1 for p, q in zip(ba, bb) if max(abs(u - v) for u, v in zip(p, q)) > 0.5)
        rows.append(dict(stem=stem, chars=same, moved=moved, moved_pct=round(100 * moved / max(1, same), 2), text_same=text_same,
                         coverage_old=round(100 * c0 / max(1, n0), 1), coverage_new=round(100 * c1 / max(1, n1), 1)))
    rows.sort(key=lambda r: -r["moved_pct"]); tot = sum(r["chars"] for r in rows); mv = sum(r["moved"] for r in rows)
    print(f"{len(rows)} documents in both builds; {mv} of {tot} characters have a different box ({100 * mv / max(1, tot):.2f}%); "
          f"documents whose copied text changed: {sum(not r['text_same'] for r in rows)}; documents with over 5% of boxes moved: {sum(r['moved_pct'] > 5 for r in rows)}")
    for r in rows[:top]: print(f"  {r['stem']}: {r['moved_pct']}% of boxes moved, coverage {r['coverage_old']}% -> {r['coverage_new']}%" + ("" if r["text_same"] else "  TEXT CHANGED"))
    json.dump(rows, open(os.path.join(new, "box_changes.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 20)
