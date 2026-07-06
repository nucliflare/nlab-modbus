import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Resolve pyside6-uic from the same Python environment running this script
# so it works without activating the venv (e.g. in CI).
_scripts = Path(sys.executable).parent
_uic = _scripts / ("pyside6-uic.exe" if sys.platform == "win32" else "pyside6-uic")

ui_files = {
    ROOT / "src/nlab_modbus/gui/view/main_window.ui": ROOT / "src/nlab_modbus/gui/generated/ui_main_window.py",
    ROOT / "src/nlab_modbus/gui/view/device_tab.ui": ROOT / "src/nlab_modbus/gui/generated/ui_device_tab.py",
}

for ui_file, py_file in ui_files.items():
    subprocess.run([str(_uic), str(ui_file), "-o", str(py_file)], check=True)
