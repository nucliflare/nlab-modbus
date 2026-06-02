from __future__ import annotations

import numpy as np


class NumpyRingBuffer:
    def __init__(self, size: int, dtype: type = float) -> None:
        self.size = size
        self.data = np.empty(size, dtype=dtype)
        self.index = 0
        self.full = False

    def append(self, value: float) -> None:
        self.data[self.index] = value
        self.index = (self.index + 1) % self.size

        if self.index == 0:
            self.full = True

    def extend(self, values: np.ndarray) -> None:
        values = np.asarray(values)

        if len(values) >= self.size:
            self.data[:] = values[-self.size :]
            self.index = 0
            self.full = True
            return

        end = self.index + len(values)

        if end <= self.size:
            self.data[self.index : end] = values
        else:
            first_part = self.size - self.index
            self.data[self.index :] = values[:first_part]
            self.data[: end % self.size] = values[first_part:]

        self.index = end % self.size

        if end >= self.size:
            self.full = True

    def array(self) -> np.ndarray:
        """
        Return data in chronological order.
        Oldest sample first, newest sample last.
        """
        if not self.full:
            return self.data[: self.index].copy()

        return np.concatenate(
            (
                self.data[self.index :],
                self.data[: self.index],
            )
        )
