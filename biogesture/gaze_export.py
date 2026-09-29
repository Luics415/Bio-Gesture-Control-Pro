"""Explicit, local-only numeric diagnostic export. Never called on a timer."""

from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4


MAX_EXPORT_BYTES = 8 * 1024 * 1024


def save_gaze_diagnostic(payload: dict, directory: Path) -> Path:
    """Persist a caller-requested JSON report without replacing an earlier test.

    The report builder supplies numeric measurements, not camera frames. This
    boundary refuses non-JSON objects and nonfinite values rather than silently
    serializing images or opaque objects. Nothing is uploaded or auto-loaded.
    """
    if not isinstance(payload, dict):
        raise ValueError("El diagnóstico debe ser un objeto de datos")
    content = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
    if len(content) > MAX_EXPORT_BYTES:
        raise ValueError("El diagnóstico supera el tamaño permitido")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"mirada-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.json"
    path = directory / name
    with path.open("xb") as output:
        output.write(content)
    return path
