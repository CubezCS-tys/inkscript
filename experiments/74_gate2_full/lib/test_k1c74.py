"""Experiment 74: the tightened K1c venue test and the D44 rule (works74.venue_fits74, works74.d44).

    cd experiments/74_gate2_full/lib && LIB74_J=0165 LIB74_RELEASE=x ../../49_correction_desk/.venv/bin/python -m pytest -q test_k1c74.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("LIB74_J", "0165")
os.environ.setdefault("LIB74_RELEASE", "/nonexistent.db")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import works74 as W  # noqa: E402


def dec(journal, ctype="journal"):
    return dict(decision=dict(target=dict(journal=journal), card=dict(type=ctype)), printed=["…"])


def test_k1c_other_journal_fails():
    # exp 72's C70RAZGS25: a record in «مجلة الطفولة والتربية» for a citation of «مجلة الطفولة والتنمية»
    assert not W.venue_fits74(dec("مجلة الطفولة والتربية"), ["مجلة الطفولة والتنمية"])


def test_k1c_same_journal_passes():
    assert W.venue_fits74(dec("مجلة الطفولة والتنمية"), ["مجلة الطفولة والتنمية، المجلس العربي للطفولة والتنمية"])
    assert W.venue_fits74(dec("المجلة العربية للتربية"), ["المجلة العربية للتربية"])


def test_k1c_generic_only_fails():
    assert not W.venue_fits74(dec("المجلة العربية للعلوم التربوية والنفسية"), ["مجلة العلوم التربوية"])


def test_d44():
    best = dict(s_title=1.0, s_author=1.0, type="بحوث ومقالات", journal="مجلة الطفولة والتربية", journal_code="1234",
                c999="1")
    assert W.d44(dec("مجلة الطفولة والتربية"), best, ["مجلة كلية التربية جامعة أسيوط"])
    assert not W.d44(dec("مجلة الطفولة والتربية"), best, ["مجلة الطفولة والتربية"])          # the same journal
    top = [best, dict(best, c999="2", journal="مجلة كلية التربية جامعة أسيوط")]
    assert not W.d44(dec("مجلة الطفولة والتربية"), best, ["مجلة كلية التربية جامعة أسيوط"], top)     # the cited one exists
