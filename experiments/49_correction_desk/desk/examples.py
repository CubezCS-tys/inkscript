"""The example decisions of P1 (DESIGN §4: each of experiment 48's error kinds is one operation). Used by test (a)
and by the demo data loaded into the real `inkdesk` database for P2's screens. The verdicts are an agent's
(Claude's), read from the printed citations; no person has checked them."""
from __future__ import annotations

from . import ops

DIWAN = "work:CK4KYP6BAX"              # «الديوان»: six poets' diwans on one card (probe B)
DIWAN_GROUPS = [
    ("الأخطل", ["0690-016-001,002-006|p2|w196-204|1"]),
    ("ابن رشيق", ["1967-000-008-012|p13|w13-26|1"]),
    ("ابن الفارض", ["1716-000-002-018|p18|w226-245|1"]),
    ("محمد علي اليعقوبي", ["0944-004-004-003|p21|w79-94|1"]),
    ("مهيار الديلمي", ["0138-005-006-003|p5|w244-258|1"]),
    ("العسكري", ["0691-041-001,004-046|p7|w208-220|1"]),
    ("no author printed; the article (0416) names no poet nearby", ["0416-053-004-004|p9|w218-222|1"]),
]
# 1875's «الديوان، ص ١٩٥» is the diwan of عبد الكريم القيسي cited in full two notes earlier (p5): it is left on the
# first group by the split and moved to that card by a move_member decision.
QAYSI_MEMBER = "mention:1875-005-020-001|p6|w271-274|1"
QAYSI_CARD = "work:CGKWRHA4PH"
MUQADDIMA = ("work:CF622F7PED", "work:CVSFVRG2E8")     # «المقدّمة» + «مقدمة ابن خلدون»: one work (keep the first)
ALOTAIBI = ("person:AB5Y33ZFR1", "person:AXSY5WYC4V")   # «العتيبي، خالد طلال» (authority 441962) + «Khalid Talal Alotaibi»
NOT_SAME = ("work:CEZMTGEP1N", "work:CCYV22W48A")       # «إدارة الموارد البشرية - مدخل إستراتيجي» (جاد الرب) ≠ Dessler's
UNRESOLVABLE = "mention:0852-001-004,005-003|p26|w203-207|1"   # «B Hansem, op.cit. P. 26»: no earlier full citation


def make_test_a(pg, actor: str, is_demo: bool = False, note_prefix: str = "") -> dict:
    """The four decisions test (a) names, plus the move that places 1875's «الديوان»."""
    kw = dict(is_demo=is_demo)
    n = lambda s: (note_prefix + s).strip()  # noqa: E731
    out = {}
    out["split"] = ops.split_work(pg, actor, DIWAN, [dict(label=lab, members=[f"mention:{m}" for m in ms])
                                                     for lab, ms in DIWAN_GROUPS],
                                  reason_code="different-works", note=n("six poets' diwans joined through citations "
                                                                        "that print no author"), **kw)
    out["move"] = ops.move_member(pg, actor, QAYSI_MEMBER, QAYSI_CARD, reason_code="short-form-of",
                                  note=n("«الديوان، ص ١٩٥» follows the full citation of ديوان عبد الكريم القيسي (p5)"),
                                  **kw)
    out["same_work"] = ops.same_work(pg, actor, *MUQADDIMA, reason_code="same-work-other-title",
                                     note=n("«المقدّمة» is Ibn Khaldun's Muqaddima, as «مقدمة ابن خلدون»"), **kw)
    out["same_person"] = ops.same_person(pg, actor, *ALOTAIBI, reason_code="transliteration",
                                         note=n("«Khalid Talal Alotaibi» is the Latin byline of «العتيبي، خالد طلال», "
                                                "the article's catalogue contributor (authority 441962)"), **kw)
    out["not_same"] = ops.not_same_work(pg, actor, *NOT_SAME, reason_code="different-authors",
                                        note=n("Jad al-Rabb's book is not Dessler's (translated by Abd al-Muta'al)"),
                                        **kw)
    return out


def make_more(pg, actor: str, is_demo: bool = False, note_prefix: str = "") -> dict:
    return dict(unresolvable=ops.unresolvable(pg, actor, UNRESOLVABLE, reason_code="no-earlier-full",
                                              note=(note_prefix + "no full citation of Hansem earlier in the "
                                                                  "article").strip(), is_demo=is_demo))
