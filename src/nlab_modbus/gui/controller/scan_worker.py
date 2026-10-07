from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class DeviceScanThread(QThread):
    """Run one blocking discovery operation without blocking the Qt event loop."""

    result_ready = Signal(str, object)
    scan_failed = Signal(str, str)

    def __init__(
        self,
        kind: str,
        scan: Callable[[Callable[[], bool]], Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self._scan = scan

    def run(self) -> None:
        try:
            result = self._scan(self.isInterruptionRequested)
        except Exception as exc:
            logger.exception("%s device scan failed", self.kind.capitalize())
            if not self.isInterruptionRequested():
                self.scan_failed.emit(self.kind, str(exc))
            return

        if not self.isInterruptionRequested():
            self.result_ready.emit(self.kind, result)
