"""DEV ONLY (experiment 75): the Desk API with the lab pointed at a TEST COPY of the data root and a fixed test actor,
so the correction screen can be exercised (save, reload, scores) without writing a correction in anyone's name into
the real lab.  Never deployed.

    DESK_LAB_ROOT=<copy> /home/appuser/inkscript/experiments/49_correction_desk/.venv/bin/python -m uvicorn \
        labtest_app:app --app-dir experiments/75_ocr_lab --host 127.0.0.1 --port 8155
"""
import os
import sys
from pathlib import Path

assert os.environ.get("DESK_LAB_ROOT"), "set DESK_LAB_ROOT to a test copy"
assert Path(os.environ["DESK_LAB_ROOT"]).resolve() != (Path(__file__).resolve().parent / "out" / "data").resolve(), \
    "the test app must not write into the real lab"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "49_correction_desk"))
from desk import api as A  # noqa: E402

TEST_ACTOR = dict(actor_id="agent:exp75-test", kind="agent", name="exp75 test (not the owner)", role="corrector",
                  active=True, is_demo=False)
A.app.dependency_overrides[A.me] = lambda: TEST_ACTOR
app = A.app
