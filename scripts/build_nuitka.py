"""Nuitka build script for the nlab-modbus-gui application."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ENTRY = SRC / "nlab_modbus" / "gui" / "main_app.py"
ICON = SRC / "nlab_modbus" / "gui" / "resources" / "ewt.ico"
DATA_DIR = SRC / "nlab_modbus" / "data"
RESOURCES_DIR = SRC / "nlab_modbus" / "gui" / "resources"
OUTPUT = ROOT / "build"

sys.path.insert(0, str(SRC))
from nlab_modbus._version import __version__  # noqa: E402

PRODUCT_NAME = "NLab Modbus Monitor"
PRODUCT_VERSION = __version__
COMPANY = "Nuclear-Lab / EWT"

OUTPUT_NAME = "nlab-modbus-gui.exe" if sys.platform == "win32" else "nlab-modbus-gui"


def build() -> int:
    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--output-dir={OUTPUT}",
        f"--output-filename={OUTPUT_NAME}",
        # PySide6 plugin handles Qt binaries, translations, etc.
        "--enable-plugin=pyside6",
        # Bundle data files
        f"--include-data-dir={DATA_DIR}=nlab_modbus/data",
        f"--include-data-dir={RESOURCES_DIR}=nlab_modbus/gui/resources",
        # Ensure all sub-packages are included
        "--include-package=nlab_modbus",
        # Needed at runtime but not statically imported
        "--include-module=pymodbus.client",
        "--include-module=pymodbus.framer",
        "--include-module=zeroconf",
        "--include-module=PySide6.QtOpenGL",
        "--include-module=PySide6.QtOpenGLWidgets",
        # Strip docstrings / asserts for smaller binary
        "--python-flag=no_docstrings",
    ]

    if sys.platform == "win32":
        cmd += [
            f"--windows-icon-from-ico={ICON}",
            "--windows-console-mode=force",
            f"--product-name={PRODUCT_NAME}",
            f"--product-version={PRODUCT_VERSION}",
            f"--company-name={COMPANY}",
            f"--copyright=Copyright (c) {COMPANY}",
        ]

    cmd.append(str(ENTRY))

    print("Running Nuitka build …")
    print(" ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(build())
