"""The Article page links to the article beside its scans (experiment 41's mirror pages, proxied as /views/)."""
import pytest

from desk import pages


def test_mirror_link_for_a_run_with_an_underscore():
    if not (pages.VIEWS / "j0130_final" / "mirror").is_dir():
        pytest.skip("experiment 41's views are not on this machine")
    assert pages.mirror_of("j0130_final", "0130-018-072-003") == "/views/j0130_final/mirror/0130-018-072-003.html"
    assert pages.mirror_of("j0130_final", "no-such-stem") is None
    assert pages.mirror_of("../etc", "0130-018-072-003") is None
