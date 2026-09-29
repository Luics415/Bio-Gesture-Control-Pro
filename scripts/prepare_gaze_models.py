"""Explicit download/verification of pinned local ocular models; never runs them.

Run from the development folder with its Python. No package installation,
camera access or implicit runtime download. Existing unverified files are never
overwritten. A bounded download is validated before an exclusive local write.
"""

import argparse
from pathlib import Path
import sys
import urllib.request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from biogesture.gaze_neural import MODEL_ASSETS, verify_asset  # noqa: E402


def prepare_models(directory, *, verify_only=False):
    directory = Path(directory)
    # Preflight ALL existing targets before downloading anything. Never replace
    # unknown user data, a partial file or a symbolic link.
    missing = []
    for asset in MODEL_ASSETS:
        path = directory / asset.filename
        if path.is_symlink():
            raise RuntimeError(f"No se reemplazará un enlace: {path.name}")
        if path.exists():
            if path.stat().st_size != asset.size:
                raise RuntimeError(f"Archivo existente no verificado: {path.name}; no se sobrescribe")
            verify_asset(path.read_bytes(), asset)
        else:
            missing.append(asset)
    if missing and verify_only:
        raise RuntimeError("Faltan modelos oculares: " + ", ".join(a.filename for a in missing))
    for asset in missing:
        request = urllib.request.Request(asset.url, headers={"User-Agent": "BioGesture-model-setup/1"})
        with urllib.request.urlopen(request, timeout=45) as response:
            if not response.geturl().startswith("https://storage.openvinotoolkit.org/"):
                raise RuntimeError("Origen de descarga ocular inesperado")
            data = response.read(asset.size + 1)
        verify_asset(data, asset)
        directory.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects against a file appearing after the
        # preflight. Only verified bytes are written. Runtime rechecks all bytes.
        with (directory / asset.filename).open("xb") as stream:
            stream.write(data)
        print(f"Verificado: {asset.filename} ({len(data):,} bytes)")
    return len(MODEL_ASSETS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=PROJECT_ROOT / "assets/models/gaze-precision")
    parser.add_argument("--verify-only", action="store_true", help="Comprueba sin descargar nada")
    args = parser.parse_args(argv)
    try:
        count = prepare_models(args.directory, verify_only=args.verify_only)
    except (OSError, RuntimeError) as exc:
        print(f"No se prepararon los modelos: {exc}", file=sys.stderr)
        return 1
    print(f"{count} archivos oculares íntegros. No se abrió la cámara ni se ejecutó inferencia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
