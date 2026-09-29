"""Build-process-only import exclusions, inherited by PyInstaller's children.

Python loads this through the builder's private PYTHONPATH, not site-packages.
The optional OpenVINO converter is unnecessary for IR/CPU inference and its
import initializes telemetry. Analysis exclusions alone do not stop imports
in PyInstaller's Windows DLL-discovery subprocess. Do not ship this module.
"""

import os
import sys


if os.environ.get("BIOGESTURE_BUILD_RUNTIME_ONLY") == "1":
    for _name in ("openvino.tools", "openvino_telemetry"):
        if any(name == _name or name.startswith(_name + ".") for name in sys.modules):
            raise RuntimeError("The build started with converter/telemetry already loaded")
        # None explicitly forbids import, including descendants, without
        # importing the vendor or altering its files/consent/global environment.
        sys.modules[_name] = None
