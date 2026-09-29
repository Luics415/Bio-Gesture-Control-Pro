"""Neural backend contracts with generated pixels; no camera or desktop input."""

import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import subprocess
import textwrap
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from biogesture import gaze_neural as neural
from scripts import prepare_gaze_models as setup


def landmarks():
    points = [SimpleNamespace(x=.5, y=.5) for _ in range(478)]
    for j, i in enumerate(neural.FACE_OVAL):
        theta = j * 2 * math.pi / len(neural.FACE_OVAL)
        points[i] = SimpleNamespace(x=.5 + .25 * math.sin(theta), y=.5 - .30 * math.cos(theta))
    for i, x in ((33, .30), (133, .38), (362, .62), (263, .70)):
        points[i] = SimpleNamespace(x=x, y=.4)
    return points


def image():
    pixels = np.zeros((480, 640, 3), dtype=np.uint8)
    pixels[:, :320, 0] = 255  # RGB red in anatomical-right test fixture region.
    pixels[:, 320:, 1] = 128
    return pixels


class Port:
    def __init__(self, name, shape):
        self.name, self.shape = name, shape

    def get_element_type(self):
        return SimpleNamespace(get_type_name=lambda: "f32")


class Compiled:
    def __init__(self, head):
        self.head = head
        ins = {"data": (1, 3, 60, 60)} if head else {
            "left_eye_image": (1, 3, 60, 60), "right_eye_image": (1, 3, 60, 60), "head_pose_angles": (1, 3)}
        outs = {name: (1, 1) for name in ("fc_y", "fc_p", "fc_r")} if head else {"gaze_vector": (1, 3)}
        self.inputs = [Port(k, v) for k, v in ins.items()]
        self.outputs = [Port(k, v) for k, v in outs.items()]
        self.values = [10., -20., 30.] if head else [3., 4., 0.]
        self.request = SimpleNamespace(infer=Mock(side_effect=self.infer))

    def input(self, name):
        return next(p for p in self.inputs if p.name == name)

    def output(self, name):
        return next(p for p in self.outputs if p.name == name)

    def create_infer_request(self):
        return self.request

    def infer(self, inputs, **kwargs):
        if self.head:
            return {port: np.asarray([[v]], dtype=np.float32) for port, v in zip(self.outputs, self.values)}
        return {self.outputs[0]: np.asarray([self.values], dtype=np.float32)}


@pytest.fixture
def fake_runtime(monkeypatch):
    head, gaze = Compiled(True), Compiled(False)
    core = SimpleNamespace(read_model=Mock(side_effect=lambda **kw: kw["model"]),
                           compile_model=Mock(side_effect=[head, gaze]))
    constructor = Mock(return_value=core)
    monkeypatch.setitem(sys.modules, "openvino", SimpleNamespace(Core=constructor))
    blobs = {asset.filename: asset.filename.encode() for asset in neural.MODEL_ASSETS}
    monkeypatch.setattr(neural, "verified_model_bytes", Mock(return_value=blobs))
    extractor = neural.NeuralGazeExtractor(Path("synthetic-models"))
    return extractor, head, gaze, core, constructor


def test_preprocessing_is_bgr_f32_nchw_no_extra_mirror_or_normalization():
    rgb = image()
    original = rgb.copy()
    inputs = neural.prepare_inputs(rgb, landmarks())
    for tensor in inputs.values():
        assert tensor.shape == (1, 3, 60, 60)
        assert tensor.dtype == np.float32
        assert tensor.flags.c_contiguous
        assert not np.shares_memory(tensor, rgb)
    assert np.all(inputs["right_eye_image"][:, 2] == 255)
    assert np.all(inputs["right_eye_image"][:, :2] == 0)
    assert np.all(inputs["left_eye_image"][:, 1] == 128)
    np.testing.assert_array_equal(rgb, original)


def test_side_labels_follow_landmark_identity_even_when_image_positions_swap():
    points = landmarks()
    for point in points:
        point.x = 1 - point.x
    inputs = neural.prepare_inputs(image(), points)
    assert np.all(inputs["left_eye_image"][:, 2] == 255)
    assert np.all(inputs["right_eye_image"][:, 1] == 128)


@pytest.mark.parametrize("bad", [None, [], np.zeros((480, 640)), np.zeros((480, 640, 4), np.uint8),
                                np.zeros((480, 640, 3), np.float32), np.zeros((0, 0, 3), np.uint8),
                                np.zeros((32, 32, 3), np.uint8)])
def test_invalid_image_is_rejected(bad):
    with pytest.raises(ValueError):
        neural.prepare_inputs(bad, landmarks())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, 2, True, None, "bad"])
def test_invalid_landmark_is_rejected(value):
    points = landmarks()
    points[33].x = value
    with pytest.raises(ValueError):
        neural.prepare_inputs(image(), points)


@pytest.mark.parametrize("points", [None, [], [SimpleNamespace(x=.5, y=.5)] * 300])
def test_incomplete_mesh_is_rejected(points):
    with pytest.raises(ValueError):
        neural.prepare_inputs(image(), points)


def test_eye_box_uses_1_8_span_and_does_not_clip_or_wrap():
    assert neural._square_bounds(100, 100, 20 * 1.8, 640, 480) == (82, 82, 118, 118)
    for args in ((5, 100, 36, 640, 480), (100, 5, 36, 640, 480),
                 (635, 100, 36, 640, 480), (100, 475, 36, 640, 480)):
        with pytest.raises(ValueError):
            neural._square_bounds(*args)


def test_small_eye_and_face_geometry_fail_closed():
    points = landmarks()
    points[133].x = points[33].x + .005
    with pytest.raises(ValueError, match="pequeños"):
        neural.prepare_inputs(image(), points)
    points = landmarks()
    for i in neural.FACE_OVAL:
        points[i] = SimpleNamespace(x=.5, y=.5)
    with pytest.raises(ValueError, match="Rostro"):
        neural.prepare_inputs(image(), points)


def test_constructor_uses_verified_bytes_and_bounded_cpu(fake_runtime):
    _, _, _, core, _ = fake_runtime
    assert core.compile_model.call_count == 2
    for call in core.compile_model.call_args_list:
        assert call.args[1] == "CPU"
        assert call.args[2] == neural.CPU_CONFIG
    for call in core.read_model.call_args_list:
        assert isinstance(call.kwargs["model"], bytes)
        assert isinstance(call.kwargs["weights"], bytes)


@pytest.mark.parametrize("kind", ["input_shape", "input_dtype", "missing_input", "output_shape", "extra_output"])
def test_constructor_rejects_model_contract_changes(fake_runtime, monkeypatch, kind):
    _, head, gaze, _, _ = fake_runtime
    if kind == "input_shape":
        gaze.inputs[0].shape = (1, 3, 224, 224)
    elif kind == "input_dtype":
        gaze.inputs[0].get_element_type = lambda: SimpleNamespace(get_type_name=lambda: "f16")
    elif kind == "missing_input":
        gaze.inputs.pop()
    elif kind == "output_shape":
        gaze.outputs[0].shape = (1, 2)
    else:
        head.outputs.append(Port("unexpected", (1, 1)))
    core = SimpleNamespace(read_model=Mock(return_value="bytes"), compile_model=Mock(side_effect=[head, gaze]))
    monkeypatch.setitem(sys.modules, "openvino", SimpleNamespace(Core=lambda: core))
    with pytest.raises(RuntimeError, match="Contrato"):
        neural.NeuralGazeExtractor("synthetic")


def test_extract_returns_unit_vector_and_angles_radians_without_double_roll(fake_runtime):
    extractor, head, gaze, _, _ = fake_runtime
    actual = extractor.extract(image(), landmarks())
    assert actual == pytest.approx((.6, .8, 0, math.radians(10), math.radians(-20), math.radians(30)))
    call = gaze.request.infer.call_args
    np.testing.assert_array_equal(call.args[0]["head_pose_angles"], [[10, -20, 30]])
    assert call.kwargs == {"share_inputs": False, "share_outputs": False}
    assert head.request.infer.call_count == 1


def test_front_facing_negative_z_convention_is_preserved(fake_runtime):
    extractor, _, gaze, _, _ = fake_runtime
    gaze.values = [0., 0., -7.]
    vector = extractor.extract(image(), landmarks())[:3]
    assert vector == pytest.approx((0., 0., -1.))
    # Official OMZ demo utils.cpp: atan2(z, x) with +pi/2 is zero here.
    horizontal = math.pi / 2 + math.atan2(vector[2], vector[0])
    vertical = math.pi / 2 - math.acos(vector[1])
    assert (horizontal, vertical) == pytest.approx((0., 0.))


@pytest.mark.parametrize("angles", [[float("nan"), 0, 0], [0, float("inf"), 0], [91, 0, 0],
                                    [0, 71, 0], [0, 0, -71]])
def test_invalid_head_angles_never_reach_gaze_network(fake_runtime, angles):
    extractor, head, gaze, _, _ = fake_runtime
    head.values = angles
    with pytest.raises(ValueError):
        extractor.extract(image(), landmarks())
    gaze.request.infer.assert_not_called()


@pytest.mark.parametrize("vector", [[0, 0, 0], [float("nan"), 1, 1], [1, float("inf"), 1],
                                    [1e-9, 0, 0], [1e9, 0, 0], [1, 2]])
def test_invalid_gaze_vector_is_rejected(fake_runtime, vector):
    extractor, _, gaze, _, _ = fake_runtime
    gaze.values = vector
    with pytest.raises(ValueError):
        extractor.extract(image(), landmarks())


def test_invalid_geometry_does_not_run_any_inference(fake_runtime):
    extractor, head, gaze, _, _ = fake_runtime
    with pytest.raises(ValueError):
        extractor.extract(None, landmarks())
    head.request.infer.assert_not_called()
    gaze.request.infer.assert_not_called()


def test_close_releases_requests_and_prevents_reuse(fake_runtime):
    extractor, *_ = fake_runtime
    extractor.close()
    extractor.close()
    assert extractor._head_request is None
    with pytest.raises(RuntimeError, match="cerrado"):
        extractor.extract(image(), landmarks())


def tiny_asset(name="sample.bin", data=b"verified"):
    return neural.ModelAsset(name, len(data), hashlib.sha384(data).hexdigest())


def test_hash_checks_exact_size_and_content():
    asset = tiny_asset()
    neural.verify_asset(b"verified", asset)
    for data in (b"", b"verifiedmore", b"tampered"):
        with pytest.raises(RuntimeError, match="Integridad"):
            neural.verify_asset(data, asset)


def test_files_read_via_unicode_python_path_and_verified_before_load(tmp_path, monkeypatch):
    folder = tmp_path / "calibración ángulos"
    folder.mkdir()
    asset = tiny_asset()
    (folder / asset.filename).write_bytes(b"verified")
    monkeypatch.setattr(neural, "MODEL_ASSETS", (asset,))
    assert neural.verified_model_bytes(folder) == {"sample.bin": b"verified"}
    (folder / asset.filename).write_bytes(b"tampered")
    constructor = Mock()
    monkeypatch.setitem(sys.modules, "openvino", SimpleNamespace(Core=constructor))
    with pytest.raises(RuntimeError, match="Integridad"):
        neural.NeuralGazeExtractor(folder)
    constructor.assert_not_called()


def test_missing_models_do_not_import_or_download_runtime(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "openvino", None)
    urlopen = Mock(side_effect=AssertionError("Network forbidden"))
    monkeypatch.setattr(setup.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="Falta el modelo"):
        neural.NeuralGazeExtractor(tmp_path)
    urlopen.assert_not_called()


def test_existing_corrupt_file_stops_preparation_before_any_download(tmp_path, monkeypatch):
    first, second = tiny_asset("one.bin"), tiny_asset("two.bin")
    (tmp_path / second.filename).write_bytes(b"untrusted")
    monkeypatch.setattr(setup, "MODEL_ASSETS", (first, second))
    urlopen = Mock(side_effect=AssertionError("Network forbidden"))
    monkeypatch.setattr(setup.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError):
        setup.prepare_models(tmp_path)
    assert (tmp_path / second.filename).read_bytes() == b"untrusted"
    urlopen.assert_not_called()


def test_verify_only_never_downloads(tmp_path, monkeypatch):
    asset = tiny_asset()
    monkeypatch.setattr(setup, "MODEL_ASSETS", (asset,))
    urlopen = Mock(side_effect=AssertionError("Network forbidden"))
    monkeypatch.setattr(setup.urllib.request, "urlopen", urlopen)
    with pytest.raises(RuntimeError, match="Faltan"):
        setup.prepare_models(tmp_path, verify_only=True)
    (tmp_path / asset.filename).write_bytes(b"verified")
    assert setup.prepare_models(tmp_path, verify_only=True) == 1
    urlopen.assert_not_called()


@pytest.mark.parametrize("body,url,okay", [(b"verified", "https://storage.openvinotoolkit.org/model", True),
                                          (b"tampered", "https://storage.openvinotoolkit.org/model", False),
                                          (b"verified", "https://other.example/model", False)])
def test_explicit_download_only_writes_verified_official_bytes(tmp_path, monkeypatch, body, url, okay):
    asset = tiny_asset()
    monkeypatch.setattr(setup, "MODEL_ASSETS", (asset,))
    response = Mock(geturl=Mock(return_value=url), read=Mock(return_value=body))
    manager = Mock(__enter__=Mock(return_value=response), __exit__=Mock(return_value=False))
    urlopen = Mock(return_value=manager)
    monkeypatch.setattr(setup.urllib.request, "urlopen", urlopen)
    if okay:
        assert setup.prepare_models(tmp_path) == 1
        assert (tmp_path / asset.filename).read_bytes() == body
        response.read.assert_called_once_with(asset.size + 1)
    else:
        with pytest.raises(RuntimeError):
            setup.prepare_models(tmp_path)
        assert not (tmp_path / asset.filename).exists()


def test_manifest_has_pinned_official_sources_and_full_sha384():
    assert len(neural.OMZ_COMMIT) == 40
    assert len(neural.MODEL_ASSETS) == 4
    for asset in neural.MODEL_ASSETS:
        assert len(asset.sha384) == 96
        assert asset.url.startswith(neural.MODEL_BASE_URL + "/")
        assert "/FP32/" in asset.url
        assert "/" not in asset.filename and "\\" not in asset.filename
    license_path = Path(__file__).resolve().parents[1] / "assets/models/OPENVINO-LICENSE.txt"
    assert "Apache License" in license_path.read_text(encoding="utf-8")


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_OPENVINO") != "1", reason="Opt-in synthetic OpenVINO CPU check")
def test_real_cpu_models_with_generated_pixels_and_unicode_model_directory(tmp_path):
    """Load real weights, never camera/photos: this does not measure accuracy."""
    if importlib.util.find_spec("openvino") is None:
        pytest.skip("OpenVINO runtime not installed")
    source = Path(__file__).resolve().parents[1] / "assets/models/gaze-precision"
    destination = tmp_path / "modelos precisión áéñ"
    destination.mkdir()
    for asset in neural.MODEL_ASSETS:
        data = (source / asset.filename).read_bytes()
        neural.verify_asset(data, asset)
        (destination / asset.filename).write_bytes(data)
    extractor = neural.NeuralGazeExtractor(destination)
    try:
        assert extractor._head.get_property("INFERENCE_NUM_THREADS") == 2
        assert extractor._head.get_property("NUM_STREAMS") == 1
        result = extractor.extract(image(), landmarks())
        assert len(result) == 6
        assert np.isfinite(result).all()
        assert math.sqrt(sum(v * v for v in result[:3])) == pytest.approx(1)
        assert all(abs(v) <= math.pi / 2 for v in result[3:])
    finally:
        extractor.close()


@pytest.mark.parametrize("module", ["openvino.tools.ovc", "openvino.tools.ovc.convert", "openvino.tools.ovc.deep.module"])
def test_runtime_guard_blocks_only_converter_tree(module):
    guard = neural._RuntimeOnlyImports()
    with pytest.raises(ImportError, match="solo inferencia local"):
        guard.find_spec(module)
    for other in ("openvino", "openvino.runtime", "openvino.tools", "openvino.tools.ovcx", "json"):
        assert guard.find_spec(other) is None


def test_import_guard_is_removed_on_success_and_failure(monkeypatch):
    previous = list(sys.meta_path)
    sentinel = object()
    monkeypatch.setitem(sys.modules, "openvino", SimpleNamespace(Core=sentinel))
    assert neural._load_core() is sentinel
    assert sys.meta_path == previous
    monkeypatch.setitem(sys.modules, "openvino", None)
    with pytest.raises(RuntimeError, match="OpenVINO instalado"):
        neural._load_core()
    assert sys.meta_path == previous


def test_preloaded_converter_is_not_silently_accepted(monkeypatch):
    previous = list(sys.meta_path)
    monkeypatch.setitem(sys.modules, "openvino.tools.ovc", SimpleNamespace())
    with pytest.raises(RuntimeError, match="Reinicia"):
        neural._load_core()
    assert sys.meta_path == previous


@pytest.mark.skipif(os.environ.get("BIOGESTURE_TEST_OPENVINO") != "1", reason="Opt-in fresh runtime privacy check")
def test_fresh_native_inference_never_initializes_converter_telemetry_or_network():
    program = textwrap.dedent('''
        import socket, sys
        calls = []
        def deny(*args, **kwargs):
            calls.append("network")
            raise AssertionError("Network forbidden in native inference check")
        socket.socket.connect = deny
        socket.socket.connect_ex = deny
        socket.socket.sendto = deny
        socket.getaddrinfo = deny
        from openvino_telemetry.utils.sender import TelemetrySender
        from openvino_telemetry import Telemetry
        def no_telemetry(*args, **kwargs):
            calls.append("telemetry")
            raise AssertionError("Telemetry forbidden in native inference check")
        TelemetrySender.send = no_telemetry
        Telemetry.init = no_telemetry
        Telemetry.send_event = no_telemetry
        from biogesture.gaze_neural import NeuralGazeExtractor, _RuntimeOnlyImports
        from tests.test_gaze_neural import image, landmarks
        engine = NeuralGazeExtractor("assets/models/gaze-precision")
        try:
            values = engine.extract(image(), landmarks())
            assert len(values) == 6
            assert not any(n == "openvino.tools.ovc" or n.startswith("openvino.tools.ovc.") for n in sys.modules)
            assert not any(isinstance(f, _RuntimeOnlyImports) for f in sys.meta_path)
            assert not calls, calls
            print("native inference: no OVC, no telemetry, no network attempts")
        finally:
            engine.close()
    ''')
    result = subprocess.run([sys.executable, "-c", program], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no telemetry, no network attempts" in result.stdout
