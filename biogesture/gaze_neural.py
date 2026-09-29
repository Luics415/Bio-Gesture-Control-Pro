"""Optional local appearance-based gaze features; never owns camera or input.

Intel Open Model Zoo FP32 models, Apache-2.0. The model estimates direction,
NOT a point on the monitor. Personal calibration and held-out validation remain
the caller's responsibility. No photographs, network, training or downloads.
"""

from dataclasses import dataclass
import hashlib
from importlib.abc import MetaPathFinder
import math
from pathlib import Path
import sys
import threading


ENGINE_ID = "precision-openvino-v1"
OMZ_COMMIT = "6697dead54ed1cdd664b0313189c2cb52ee6335e"
MODEL_BASE_URL = "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1"
MODEL_LICENSE_URL = f"https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/{OMZ_COMMIT}/LICENSE"
GAZE_MODEL = "gaze-estimation-adas-0002"
HEAD_MODEL = "head-pose-estimation-adas-0001"


@dataclass(frozen=True)
class ModelAsset:
    filename: str
    size: int
    sha384: str

    @property
    def url(self):
        model = self.filename.rsplit(".", 1)[0]
        return f"{MODEL_BASE_URL}/{model}/FP32/{self.filename}"


# Sizes and SHA-384 from the two model.yml files at OMZ_COMMIT. Remote BIN
# Last-Modified: 2023-10-17 15:53:40 UTC (gaze), 15:53:43 UTC (head).
MODEL_ASSETS = (
    ModelAsset(f"{GAZE_MODEL}.xml", 68724,
               "2c70fa1448aa923869b96848f1d218ac2efab5f718a57b486d7256c46853726fde71e3165398458e973200612e17529c"),
    ModelAsset(f"{GAZE_MODEL}.bin", 7529380,
               "044e39075331a7e5b3a7da7a39ccc40defda03326375295aa091b273e7395b3ab92db076d7828b9a68795fd496b572c8"),
    ModelAsset(f"{HEAD_MODEL}.xml", 53705,
               "7b155bf7821ff6e7f46e32fc6fc2cc11c7f8692957e3762d84e2aaba2718a5e07dfd1eb885a3f2953ac2b170d83975a7"),
    ModelAsset(f"{HEAD_MODEL}.bin", 7647616,
               "29c6f24561fd81516c2d12c3648fb8a5018b1a09846ef57a664667f39c3796b1007c71d8c8801eb0babaf38ac8c2556e"),
)

# The actual facial oval, not every landmark between indices 10 and 338.
FACE_OVAL = (10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
             397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
             172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109)
RIGHT_EYE = (33, 133)  # MediaPipe anatomical right; never sort by image x.
LEFT_EYE = (362, 263)
CPU_CONFIG = {"PERFORMANCE_HINT": "LATENCY", "INFERENCE_NUM_THREADS": 2,
              "NUM_STREAMS": 1, "INFERENCE_PRECISION_HINT": "f32"}
_CORE_IMPORT_LOCK = threading.Lock()


class _RuntimeOnlyImports(MetaPathFinder):
    """Skip the optional converter: its import initializes telemetry in OV2024.

    OpenVINO explicitly catches ImportError around its optional conversion API.
    We consume only Core and precompiled IR models, so conversion is unnecessary.
    This temporary guard does not alter vendor files, telemetry consent, CI
    variables or other modules. It is always removed after runtime import.
    """

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "openvino.tools.ovc" or fullname.startswith("openvino.tools.ovc."):
            raise ImportError("Bio-Gesture usa solo inferencia local; el conversor OVC no se carga")
        return None


def _load_core():
    with _CORE_IMPORT_LOCK:
        if any(name == "openvino.tools.ovc" or name.startswith("openvino.tools.ovc.") for name in tuple(sys.modules)):
            raise RuntimeError("OpenVINO se cargó con el conversor externo. Reinicia Bio-Gesture para inferencia local.")
        guard = _RuntimeOnlyImports()
        sys.meta_path.insert(0, guard)
        try:
            from openvino import Core
        except ImportError as exc:
            raise RuntimeError("El motor ocular de precisión necesita OpenVINO instalado") from exc
        finally:
            sys.meta_path.remove(guard)
        return Core


def verify_asset(data: bytes, asset: ModelAsset) -> None:
    if len(data) != asset.size or hashlib.sha384(data).hexdigest() != asset.sha384:
        raise RuntimeError(f"Integridad incorrecta del modelo ocular: {asset.filename}")


def verified_model_bytes(model_directory):
    """Read and verify ALL models before handing any bytes to the runtime."""
    directory = Path(model_directory)
    result = {}
    for asset in MODEL_ASSETS:
        path = directory / asset.filename
        try:
            if path.is_symlink() or path.stat().st_size != asset.size:
                raise RuntimeError(f"Integridad incorrecta del modelo ocular: {asset.filename}")
            data = path.read_bytes()
        except OSError as exc:
            raise RuntimeError(
                f"Falta el modelo ocular {asset.filename}. Ejecuta la preparación explícita de modelos."
            ) from exc
        verify_asset(data, asset)
        result[asset.filename] = data
    return result


def _square_bounds(center_x, center_y, size, width, height):
    side = int(math.ceil(size))
    left, top = int(math.floor(center_x - side / 2)), int(math.floor(center_y - side / 2))
    right, bottom = left + side, top + side
    # Do not silently stretch clipped eyes/faces or wrap negative slicing.
    if side < 12 or left < 0 or top < 0 or right > width or bottom > height:
        raise ValueError("El recorte ocular o facial sale de la imagen")
    return left, top, right, bottom


def prepare_inputs(rgb, landmarks):
    """Three square BGR NCHW tensors, f32 with original 0..255 intensity.

    RGB is already oriented by the capture pipeline: no extra flip. Eye square
    size follows Intel's demo (1.8 times corner separation). Face oval bounds
    become a square without extrapolating outside the image. This MediaPipe
    face-box adaptation requires physical validation; it is not Intel's SSD.
    """
    import cv2
    import numpy as np

    if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3
            or rgb.shape[2] != 3 or min(rgb.shape[:2]) < 60):
        raise ValueError("Se requiere una imagen RGB uint8 válida")
    height, width = rgb.shape[:2]
    points = {}
    try:
        for index in set(FACE_OVAL + LEFT_EYE + RIGHT_EYE):
            p = landmarks[index]
            if isinstance(p.x, (bool, np.bool_)) or isinstance(p.y, (bool, np.bool_)):
                raise ValueError("Coordenadas booleanas")
            x, y = float(p.x) * width, float(p.y) * height
            if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x < width and 0 <= y < height):
                raise ValueError("Punto fuera de la imagen")
            points[index] = (x, y)
    except (AttributeError, IndexError, KeyError, TypeError, OverflowError, ValueError) as exc:
        raise ValueError("Geometría facial incompleta o inválida") from exc

    bounds = {}
    for name, indices in (("left_eye_image", LEFT_EYE), ("right_eye_image", RIGHT_EYE)):
        a, b = (points[i] for i in indices)
        span = math.dist(a, b)
        if span < 12 or span > min(width, height) * .4:
            raise ValueError("Ojos demasiado pequeños o geometría no fiable")
        bounds[name] = _square_bounds((a[0] + b[0]) / 2, (a[1] + b[1]) / 2,
                                      span * 1.8, width, height)
    face = np.asarray([points[i] for i in FACE_OVAL])
    lo, hi = face.min(axis=0), face.max(axis=0)
    if min(hi - lo) < 40:
        raise ValueError("Rostro demasiado pequeño o geometría no fiable")
    bounds["data"] = _square_bounds(*(lo + hi) / 2, float(max(hi - lo)), width, height)
    prepared = {}
    for name, (left, top, right, bottom) in bounds.items():
        bgr = rgb[top:bottom, left:right, ::-1]
        resized = cv2.resize(bgr, (60, 60), interpolation=cv2.INTER_CUBIC)
        prepared[name] = np.ascontiguousarray(resized.transpose(2, 0, 1)[None], dtype=np.float32)
    return prepared


class NeuralGazeExtractor:
    """One worker-owned synchronous extractor; initialization performs no I/O network."""

    def __init__(self, model_directory):
        blobs = verified_model_bytes(model_directory)
        Core = _load_core()
        self._core = Core()
        models = {}
        for name in (HEAD_MODEL, GAZE_MODEL):
            model = self._core.read_model(model=blobs[f"{name}.xml"], weights=blobs[f"{name}.bin"])
            models[name] = self._core.compile_model(model, "CPU", dict(CPU_CONFIG))
        self._head, self._gaze = models[HEAD_MODEL], models[GAZE_MODEL]
        for compiled, names in ((self._head, {"data": (1, 3, 60, 60)}),
                                (self._gaze, {"left_eye_image": (1, 3, 60, 60),
                                              "right_eye_image": (1, 3, 60, 60),
                                              "head_pose_angles": (1, 3)})):
            if len(compiled.inputs) != len(names):
                raise RuntimeError("Contrato de entrada ocular incompatible")
            for name, shape in names.items():
                port = compiled.input(name)
                if tuple(port.shape) != shape or port.get_element_type().get_type_name() != "f32":
                    raise RuntimeError("Contrato de entrada ocular incompatible")
        self._head_ports = tuple(self._head.output(name) for name in ("fc_y", "fc_p", "fc_r"))
        self._gaze_port = self._gaze.output("gaze_vector")
        if (len(self._head.outputs) != 3 or len(self._gaze.outputs) != 1
                or any(tuple(p.shape) != (1, 1) for p in self._head_ports)
                or tuple(self._gaze_port.shape) != (1, 3)):
            raise RuntimeError("Contrato de salida ocular incompatible")
        self._head_request = self._head.create_infer_request()
        self._gaze_request = self._gaze.create_infer_request()
        self._closed = False

    def extract(self, rgb, landmarks):
        """Return unit gaze XYZ + yaw/pitch/roll radians, or reject the frame.

        No roll alignment is applied: Intel permits raw crops plus real roll.
        Returned vector follows the model camera convention, not screen axes.
        Preserve its sign: the official demo's gazeVectorToGazeAngles maps
        (0, 0, -1) to zero horizontal/vertical angles. Negative Z is not an
        invalid estimate. Personal calibration owns projection and usability.
        """
        import numpy as np

        if self._closed:
            raise RuntimeError("El motor ocular está cerrado")
        inputs = prepare_inputs(rgb, landmarks)
        head = self._head_request.infer({"data": inputs.pop("data")}, share_inputs=False, share_outputs=False)
        angles = []
        for port in self._head_ports:
            value = np.asarray(head[port])
            if value.shape != (1, 1) or not np.isfinite(value).all():
                raise ValueError("Estimación de postura no válida")
            angles.append(float(value[0, 0]))
        if any(abs(value) > limit for value, limit in zip(angles, (90, 70, 70))):
            raise ValueError("Postura fuera del rango del modelo ocular")
        inputs["head_pose_angles"] = np.asarray([angles], dtype=np.float32)
        output = self._gaze_request.infer(inputs, share_inputs=False, share_outputs=False)
        vector = np.asarray(output[self._gaze_port], dtype=np.float64)
        if vector.shape != (1, 3) or not np.isfinite(vector).all():
            raise ValueError("Dirección ocular no válida")
        norm = float(np.linalg.norm(vector))
        if not math.isfinite(norm) or not 1e-6 <= norm <= 1e6:
            raise ValueError("Dirección ocular degenerada")
        return tuple(float(v) for v in vector[0] / norm) + tuple(math.radians(v) for v in angles)

    def close(self):
        self._closed = True
        self._head_request = self._gaze_request = None
        self._head_ports = self._gaze_port = None
        self._head = self._gaze = self._core = None
