"""Where printed Arabic must break, and the ink/text agreement that gates a split."""
from inkscript.text import pieces


def test_text_pieces_follow_joining_rules():
    assert pieces("الحكم") == ["ا", "لحكم"]
    assert pieces("والعالم") == ["و", "ا", "لعا", "لم"]
    assert pieces("دراسات") == ["د", "ر", "ا", "سا", "ت"]
    assert pieces("لا") == ["لا"]                       # ل joins the alef; the alef ends the run


def test_marks_stay_on_their_letter():
    assert pieces("كتابُ") == ["كتا", "بُ"]
    assert pieces("السَّماءِ") == ["ا", "لسَّما", "ءِ"]


def test_non_arabic_runs_are_one_piece():
    assert pieces("362") == ["362"]
    assert pieces("126/4") == ["126/4"]
    assert pieces("(1)") == ["(1)"]
    assert pieces("379هـ)") == ["379", "هـ", ")"]


def test_words_split_where_safe(fixture):
    import fitz
    from inkscript.ocr.azure import load_azure, load_lines
    from inkscript.geometry.trace import render_gray, page_blobs
    from inkscript.geometry.layout import layout_page, split_word
    stem = fixture["stem"]; j = fixture["azure_dir"] / stem / f"{stem}.json"
    words, _, dims = load_azure(j); az_lines = load_lines(j)
    pw = [w for w in words if w["page"] == 2]
    gray = render_gray(fitz.open(fixture["scan"])[1]); blobs = page_blobs(gray)
    lines, _ = layout_page(pw, [w["text"] for w in pw], az_lines[2], blobs, gray.shape[1] / dims[2][0], gray.shape[0] / dims[2][1])
    n = split = 0
    for L in lines:
        lh = max(w["y1"] for w in L) - min(w["y0"] for w in L)
        for w in L:
            if not w["blobs"]: continue
            pcs = split_word(w, lh); n += 1; split += pcs[0]["split"]
            assert "".join(p["text"] for p in pcs).replace(" ", "") == (w["text"].strip() or w["az"]).replace(" ", "")   # text is never altered
    assert 0.15 < split / n < 0.6                        # a fair share splits; the rest stay whole rather than guess


def test_storage_is_what_chrome_reads_back():
    from inkscript.text import visual, chrome_reads
    # pdfium reverses the order of a line's bidi segments and each Arabic
    # segment in place; digits, marks and Latin keep their order. The stored
    # form is the inverse, so Chrome gives every line back exactly.
    assert visual("كتاب") == "باتك"
    assert visual("كتابُ") == "ُباتك"
    assert visual("379هـ)") == ")ـه379"
    assert visual("126/4") == "126/4"
    for line in ["362 هـ - وهو وان لم يكن فى الحقيقة", "كتابُ السَّماءِ والعالم", "التَّقَاوِيمِ",
                 "هجرية (٤٥)", "379هـ)", "126/4", "ابن خلدون (ت 808هـ)", "Kose Dagh", "معجم Lisan العرب"]:
        words = line.split()
        stored = " ".join(visual(w) for w in reversed(words)) if any(visual(w) != w for w in words) else line
        assert chrome_reads(stored) == line, line
