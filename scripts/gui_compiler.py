import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ui_files = {
    ROOT / "gui/view/main_window.ui": ROOT / "gui/generated/ui_main_window.py",
    ROOT / "gui/view/device_tab.ui": ROOT / "gui/generated/ui_device_tab.py",
}

for ui_file, py_file in ui_files.items():
    subprocess.run(
        ["pyside6-uic", str(ui_file), "-o", str(py_file)],
        check=True,
    )
