"""Ruled lines are cut out of the ink before letters are traced."""
import numpy as np, cv2
from inkscript.geometry.trace import page_blobs


def test_underline_touching_a_word_is_furniture():
    img = np.full((600, 2400), 255, np.uint8)
    cv2.putText(img, "word", (1200, 300), cv2.FONT_HERSHEY_SIMPLEX, 3, 0, 8)   # letter-like ink
    cv2.rectangle(img, (100, 322), (2300, 326), 0, -1)                         # a rule under it, touching the descender area
    blobs = page_blobs(img)
    rules = [b for b in blobs if b.get("rule")]
    letters = [b for b in blobs if not b.get("rule")]
    assert len(rules) == 1 and rules[0]["w"] > 2000
    assert letters and all(b["w"] < 400 for b in letters)                     # no letter blob swallowed the rule
    assert all(b["word"] is None for b in rules)


def test_short_strokes_are_not_rules():
    img = np.full((300, 1200), 255, np.uint8)
    cv2.rectangle(img, (100, 150), (140, 154), 0, -1)                           # a 40 px tatweel-like stroke
    blobs = page_blobs(img)
    assert blobs and not any(b.get("rule") for b in blobs)
