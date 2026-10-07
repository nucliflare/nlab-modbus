from __future__ import annotations

import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from nlab_modbus.core.enums import DeviceType  # noqa: E402
from nlab_modbus.gui.controller.main_controller import ModbusMainWindow  # noqa: E402


class _ProbeDevice:
    device_type = DeviceType.SIPM

    def __init__(self) -> None:
        self.io_thread_ids: list[int] = []

    def read(self, name: str) -> int:
        self.io_thread_ids.append(threading.get_ident())
        return 0x0101 if name == "hardware_version" else 0x0002

    def get_all_input_registers(self, *, raw=False) -> dict[str, int]:
        self.io_thread_ids.append(threading.get_ident())
        return {"hardware_version": 0x0101}

    def get_all_holding_registers(self, *, raw=False) -> dict[str, int]:
        self.io_thread_ids.append(threading.get_ident())
        return {"setting": 1}

    def connection_info(self) -> str:
        return "serial://COM9:1"


class GuiIoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _process_until(self, predicate, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertTrue(predicate(), "timed out waiting for Qt worker completion")

    @patch(
        "nlab_modbus.gui.controller.main_controller.scan_remote_boards",
        return_value=[],
    )
    @patch(
        "nlab_modbus.gui.controller.main_controller.scan_local_modbus_devices",
        return_value=[],
    )
    def test_connection_probe_and_initial_reads_run_off_gui_thread(
        self,
        _local_scan,
        _remote_scan,
    ) -> None:
        window = ModbusMainWindow()
        self.addCleanup(window.deleteLater)
        self._process_until(lambda: not window._scan_threads)

        device = _ProbeDevice()
        window.manager.find_device = Mock(return_value=None)
        window.manager.connect_local = Mock(return_value=device)
        window.add_device_tab = Mock()
        window.ui.port_select.setEditText("COM9")
        window.ui.local_id_select.setEditText("1")
        window.ui.local_type_select.setCurrentText("SIPM")
        gui_thread_id = threading.get_ident()

        window.on_connect_local_clicked()
        self._process_until(
            lambda: not window._connections_in_progress and not window._io_threads
        )

        window.add_device_tab.assert_called_once()
        self.assertTrue(device.io_thread_ids)
        self.assertTrue(
            all(thread_id != gui_thread_id for thread_id in device.io_thread_ids)
        )
        window._shutdown()


if __name__ == "__main__":
    unittest.main()
