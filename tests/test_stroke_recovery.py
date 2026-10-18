"""Focused safeguards for experiment 42's evidence and recording boundaries."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import urllib.error
import urllib.request

import numpy as np
import pytest

EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "42_stroke_recovery"
sys.path.insert(0, str(EXPERIMENT))
import dataset as D
import geometry as G
import serve as S


def stroke(label):
    return {label: [[0, 0], [10, 5]]}


def payload(**changes):
    value = dict(strokes=[[[0, 0, 1, .5, 0, 0], [10, 20, 2, .7, 0, 0]]],
                 text="\u0628", writer="unit-test", device="pen", style="handwriting", checked=True)
    return value | changes


def test_primitive_mapping_keeps_dots_and_word_boundaries():
    drawing = [stroke("\u066e"), stroke("."), stroke("\u0627")]
    words = D.word_traces("dataset/train/\u0628 \u0627_2.json", drawing)
    assert [w for w, _ in words] == ["\u0628", "\u0627"]
    assert [len(s) for _, s in words] == [2, 1]


def test_mismatched_annotation_is_not_assigned_to_other_ink():
    with pytest.raises(ValueError, match="primitive labels mismatch"):
        D.word_traces("dataset/train/\u0628_0.json", [stroke("\u0627")])


def test_internal_kaf_is_the_upstream_single_stroke():
    words = D.word_traces("dataset/train/\u0643\u0627_0.json", [stroke("\ufedb"), stroke("\u0627")])
    assert words[0][0] == "\u0643\u0627"


def test_normalisation_preserves_aspect_and_is_translation_invariant():
    a = G.normalise([[[0, 0], [30, 20]]])
    b = G.normalise([[[500, -30], [530, -10]]])
    assert np.allclose(a, b)
    delta = np.diff(a[0], axis=0)[0]
    assert delta[0] / delta[1] == pytest.approx(1.5, abs=.001)


def test_sequence_preserves_pen_lifts_and_does_not_connect_strokes():
    f = G.sequence([[[10, 10], [20, 20]], [[300, 100], [310, 110]]])
    assert f.shape == (128, 6)
    assert f[:, 4].sum() == 2 and f[:, 5].sum() == 2
    assert np.all(f[f[:, 4] == 1, 2:4] == 0)


def test_more_strokes_than_requested_frames_are_retained():
    f = G.sequence([[[float(i), 10]] for i in range(150)])
    assert f.shape[0] == 150
    assert f[:, 4].sum() == 150


def test_recovery_is_text_blind_and_retains_separate_components():
    paths = G.normalise([[[0, 0], [20, 0], [20, 20]], [[40, 0], [40, 30]]])
    result = G.recover(G.render(paths))
    assert result["components"] == 2
    assert len(result["strokes"]) == 2
    assert result["ink_coverage"] > .85
    assert not result["failures"]


def test_capture_retains_real_channels_and_does_not_call_mouse_pen():
    value = payload(device="mouse")
    result = S.capture_record(value)
    assert result["raw_strokes"] == value["strokes"]
    assert result["device"] == "mouse"
    assert result["transcription_status"] == "checked"
    assert result["split"] == "unassigned"


def test_empty_text_cannot_be_claimed_as_checked():
    with pytest.raises(ValueError, match="checked transcription"):
        S.capture_record(payload(text=""))


@pytest.mark.parametrize("strokes", [[], [[[0, 0, 1, float("nan"), 0, 0]]],
                                     [[[0, 0, 2, .5, 0, 0], [1, 1, 1, .5, 0, 0]]],
                                     [[[0, 0, 1, 2, 0, 0]]], [[[0, 0]]]])
def test_capture_rejects_invalid_evidence(strokes):
    with pytest.raises(ValueError):
        S.capture_record(payload(strokes=strokes))


def test_http_capture_roundtrip_and_origin_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "OUT", tmp_path)
    monkeypatch.setitem(sys.modules, "train", SimpleNamespace(recognise=lambda r, **kw: {}))
    server = S.ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        request = urllib.request.Request(base + "/api/captures", data=json.dumps(payload()).encode(),
                                         headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request) as response:
            saved = json.load(response)
            assert response.status == 201
        with urllib.request.urlopen(base + "/api/sample/" + saved["id"]) as response:
            assert json.load(response)["raw_strokes"] == payload()["strokes"]
        assert (tmp_path / "assets" / f"{saved['id']}.png").is_file()

        def failed_reader(record, **kw):
            assert (tmp_path / "captures" / f"{record['id']}.json").is_file()
            raise RuntimeError("reader unavailable")

        monkeypatch.setitem(sys.modules, "train", SimpleNamespace(recognise=failed_reader))
        with urllib.request.urlopen(request) as response:
            retained = json.load(response)
            assert response.status == 201
        assert retained["prediction_errors"]["sequence"] == "reader unavailable"
        assert retained["raw_strokes"] == payload()["strokes"]
        request.add_header("Origin", "https://unrelated.example")
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 403
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(base + "/assets/%2e%2e/upstream/LICENSE")
        assert error.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_prepared_source_drawings_do_not_cross_splits():
    path = D.OUT / "index.json"
    if not path.exists():
        pytest.skip("Downloaded experiment data is optional")
    index = json.loads(path.read_text())
    groups = {}
    for sample in index["samples"]:
        groups.setdefault(sample["parent"], set()).add(sample["split"])
    assert all(len(splits) == 1 for splits in groups.values())
