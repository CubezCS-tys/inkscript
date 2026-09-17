from pathlib import Path
import pytest

FIX = Path(__file__).parent / "fixtures" / "0582-004-009-012"
STEM = "0582-004-009-012"


@pytest.fixture(scope="session")
def fixture():
    return dict(stem=STEM, azure_dir=FIX / "azure", scan=FIX / "input" / f"{STEM}.pdf",
                gemini_md=FIX / "frontpage" / f"{STEM}.gemini.p1.md")
