"""PyInstaller build script for the nlab-modbus-gui application."""

from __future__ import annotations

import subprocess
import sys
import textwrap
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

VERSION_FILE_TEMPLATE = textwrap.dedent(
    """\
    VSVersionInfo(
      ffi=FixedFileInfo(filevers=({v[0]}, {v[1]}, {v[2]}, 0), prodvers=({v[0]}, {v[1]}, {v[2]}, 0)),
      kids=[
        StringFileInfo([StringTable('040904B0', [
          StringStruct('CompanyName', {company!r}),
          StringStruct('FileDescription', {name!r}),
          StringStruct('FileVersion', {version!r}),
          StringStruct('ProductName', {name!r}),
          StringStruct('ProductVersion', {version!r}),
          StringStruct('LegalCopyright', {copyright!r}),
        ])]),
        VarFileInfo([VarStruct('Translation', [1033, 1200])]),
      ]
    )
    """
)


def _write_version_file() -> Path:
    parts = (list(map(int, PRODUCT_VERSION.split("."))) + [0, 0, 0])[:3]
    content = VERSION_FILE_TEMPLATE.format(
        v=parts,
        company=COMPANY,
        name=PRODUCT_NAME,
        version=PRODUCT_VERSION,
        copyright=f"Copyright (c) {COMPANY}",
    )
    path = OUTPUT / "version_info.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def build() -> int:
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconfirm",
        f"--distpath={OUTPUT}",
        f"--workpath={OUTPUT / 'work'}",
        f"--specpath={OUTPUT}",
        f"--name={OUTPUT_NAME.removesuffix('.exe')}",
        f"--add-data={DATA_DIR}{sep}nlab_modbus/data",
        f"--add-data={RESOURCES_DIR}{sep}nlab_modbus/gui/resources",
        "--hidden-import=pymodbus.client",
        "--hidden-import=pymodbus.framer",
        "--hidden-import=zeroconf",
        "--hidden-import=PySide6.QtOpenGL",
        "--hidden-import=PySide6.QtOpenGLWidgets",
    ]

    if sys.platform == "win32":
        version_file = _write_version_file()
        cmd += [
            f"--icon={ICON}",
            f"--version-file={version_file}",
            "--console",
        ]

    cmd.append(str(ENTRY))

    print("Running PyInstaller build …")
    print(" ".join(cmd))
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(build())
