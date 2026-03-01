from __future__ import annotations

import os
import ctypes


class SleepBlocker:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001

    def __init__(self) -> None:
        self._enabled = False
        self._is_windows = os.name == "nt"

    def enable(self) -> None:
        if not self._is_windows:
            return
        ctypes.windll.kernel32.SetThreadExecutionState(
            self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED
        )
        self._enabled = True

    def disable(self) -> None:
        if not self._is_windows or not self._enabled:
            return
        ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
        self._enabled = False
