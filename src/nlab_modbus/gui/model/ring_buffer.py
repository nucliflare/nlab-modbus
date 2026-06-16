from __future__ import annotations

import numpy as np


class NumpyRingBuffer:
    """Fixed-size circular buffer backed by a pre-allocated numpy array.

    Appends are O(1) with no allocation; array() returns a contiguous copy in
    chronological order (oldest first).  Used to hold the last N samples of
    each input register for plotting in pyqtgraph.
    """

    def __init__(self, size: int, dtype: type = float) -> None:
        """Allocate the backing array without zeroing it; the buffer starts empty."""
        self.size = size
        self.data = np.empty(size, dtype=dtype)
        self.index = 0
        self.full = False

    def append(self, value: float) -> None:
        """Add one sample, overwriting the oldest value once the buffer is full."""
        self.data[self.index] = value
        self.index = (self.index + 1) % self.size

        if self.index == 0:
            self.full = True

    def extend(self, values: np.ndarray) -> None:
        """Add multiple samples efficiently, handling wraparound in at most two slices."""
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

    def clear(self) -> None:
        """Mark the buffer empty without deallocating the backing array."""
        self.index = 0
        self.full = False
