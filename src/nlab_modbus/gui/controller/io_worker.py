from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class DeviceIoThread(QThread):
    """Run a bounded connection/setup operation away from the Qt GUI thread."""

    result_ready = Signal(str, str, object)
    operation_failed = Signal(str, str, str)

    def __init__(
        self,
        connection_kind: str,
        stage: str,
        operation: Callable[[Callable[[], bool]], Any],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.connection_kind = connection_kind
        self.stage = stage
        self._operation = operation

    def run(self) -> None:
        try:
            result = self._operation(self.isInterruptionRequested)
        except Exception as exc:
            logger.exception(
                "%s device %s failed",
                self.connection_kind.capitalize(),
                self.stage,
            )
            if not self.isInterruptionRequested():
                self.operation_failed.emit(
                    self.connection_kind,
                    self.stage,
                    str(exc),
                )
            return

        if not self.isInterruptionRequested():
            self.result_ready.emit(self.connection_kind, self.stage, result)
