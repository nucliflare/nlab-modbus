"""Dose calibration for the Geiger-Mueller probe.

The firmware converts CPS to dose rate using a two-stage piecewise quadratic:

    CPS ≤ threshold :  dose = a2_p1·CPS² + a1_p1·CPS + a0_p1
    CPS >  threshold:  dose = a2_p2·CPS² + a1_p2·CPS + a0_p2

Each coefficient is stored as a (mantissa, exponent) pair in the device's
holding registers, where  value = mantissa × 10^exponent  (both int16).

The y-axis of the calibration CSV is the dose rate in the same unit that
the firmware reports via the ``dose_level_msvh`` input register (mSv/h).
Replace the bundled default curve with measurements from your specific tube
and a traceable reference instrument.
"""

from __future__ import annotations

import csv
import math
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from nlab_modbus.devices.geiger import GeigerDevice

_DEFAULT_CSV = "geiger_default_calibration.csv"

# Register names written by apply_calibration(), in application order.
_COEFF_REGISTERS = [
    ("scale_coeff_p1_a2", "scale_exp_p1_a2"),
    ("scale_coeff_p1_a1", "scale_exp_p1_a1"),
    ("scale_coeff_p1_a0", "scale_exp_p1_a0"),
    ("scale_coeff_th", "scale_exp_th"),
    ("scale_coeff_p2_a2", "scale_exp_p2_a2"),
    ("scale_coeff_p2_a1", "scale_exp_p2_a1"),
    ("scale_coeff_p2_a0", "scale_exp_p2_a0"),
]

MANTISSA_MAX = 32_000
EXP_MIN = -9
EXP_MAX = 9

# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------


def load_calibration_csv(
    path: str | Path | None = None,
    x_col: str = "x",
    y_col: str = "y",
) -> tuple[np.ndarray, np.ndarray]:
    """Load a CPS vs dose-rate calibration table from a CSV file.

    The CSV must contain at least two columns.  By default the columns are
    named ``x`` (counts per second) and ``y`` (dose rate in mSv/h).  Pass
    ``x_col`` / ``y_col`` to use different header names.

    If ``path`` is None the bundled default calibration for a generic GM tube
    is used.  Replace it with measurements from your specific detector and a
    traceable reference dosimeter.

    Returns ``(cps, dose_rate)`` as 1-D numpy arrays sorted by ascending CPS.
    """
    if path is None:
        ref = files("nlab_modbus.data").joinpath(_DEFAULT_CSV)
        text = ref.read_text(encoding="utf-8")
        rows = list(csv.DictReader(text.splitlines()))
    else:
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

    if not rows:
        raise ValueError("Calibration CSV is empty.")

    missing = {x_col, y_col} - rows[0].keys()
    if missing:
        raise ValueError(f"Column(s) not found in CSV: {missing}.  Available: {list(rows[0].keys())}")

    x = np.array([float(r[x_col]) for r in rows])
    y = np.array([float(r[y_col]) for r in rows])

    order = np.argsort(x)
    return x[order], y[order]


def encode_mantissa_exp(value: float) -> tuple[int, int]:
    """Encode float as (mantissa, exponent).

    Firmware interprets:

        value = mantissa * 10**exponent

    with:
        mantissa ∈ [-32000, 32000]
        exponent ∈ [-9, 9]
    """
    if not math.isfinite(value):
        raise ValueError(f"Cannot encode non-finite value: {value}")

    if value == 0.0:
        return 0, 0

    sign = 1 if value > 0 else -1
    abs_value = abs(value)

    # Estimate smallest exponent that keeps rounded mantissa <= 32000.
    # 32000.5 accounts for rounding to nearest integer.
    exp = math.ceil(math.log10(abs_value / (MANTISSA_MAX + 0.5)))

    # Clamp to allowed range.
    exp = max(EXP_MIN, min(EXP_MAX, exp))

    mantissa = round(abs_value / (10.0**exp))

    # Rounding edge case: if mantissa became too large, increase exponent.
    while mantissa > MANTISSA_MAX and exp < EXP_MAX:
        exp += 1
        mantissa = round(abs_value / (10.0**exp))

    mantissa *= sign

    if not (-MANTISSA_MAX <= mantissa <= MANTISSA_MAX):
        raise ValueError(f"Cannot encode {value}: mantissa {mantissa} outside [-{MANTISSA_MAX}, {MANTISSA_MAX}]")

    if not (EXP_MIN <= exp <= EXP_MAX):
        raise ValueError(f"Cannot encode {value}: exponent {exp} outside [{EXP_MIN}, {EXP_MAX}]")

    return int(mantissa), int(exp)


def decode_mantissa_exp(mantissa: int, exponent: int) -> float:
    return mantissa * 10.0**exponent


# ---------------------------------------------------------------------------
# Polynomial fitting
# ---------------------------------------------------------------------------


def fit_piecewise_quadratic(
    x: np.ndarray,
    y: np.ndarray,
    threshold_cps: float | None = None,
    dose_limit: float | None = None,
) -> dict[str, int]:
    """Fit a two-stage piecewise quadratic and return encoded register values.

    Args:
        x:              CPS values from the calibration table.
        y:              Dose-rate values (mSv/h) from the calibration table.
        threshold_cps:  CPS value at which the firmware switches from the P1
                        polynomial to P2.  Defaults to the geometric mean of
                        the CPS range, which roughly bisects the dynamic range
                        on a logarithmic scale.

    Returns a dict of ``{register_name: integer_value}`` covering all 14
    calibration registers.  Values are ready to pass to ``device.write()``.

    Raises ValueError if either segment has fewer than 3 data points (the
    minimum for a quadratic fit).
    """
    if threshold_cps is None:
        x_pos = x[x > 0]
        threshold_cps = float(np.exp(np.log(x_pos.min()) / 2 + np.log(x_pos.max()) / 2))

    low = x <= threshold_cps
    high = (x > threshold_cps) & (y < dose_limit)

    if low.sum() < 3:
        raise ValueError(
            f"Only {low.sum()} point(s) at or below threshold {threshold_cps:.1f} CPS. Lower the threshold or add more low-CPS calibration points."
        )
    if high.sum() < 3:
        raise ValueError(f"Only {high.sum()} point(s) above threshold {threshold_cps:.1f} CPS. Raise the threshold or add more high-CPS calibration points.")

    # np.polyfit returns [a2, a1, a0] for degree-2 fit

    w_low = 1.0 / np.abs(y[low])
    w_high = 1.0 / np.abs(y[high])

    p1 = np.polyfit(x[low], y[low], 2, w=w_low)
    p2 = np.polyfit(x[high], y[high], 2, w=w_high)

    th_m, th_e = encode_mantissa_exp(threshold_cps)
    p1a2_m, p1a2_e = encode_mantissa_exp(p1[0])
    p1a1_m, p1a1_e = encode_mantissa_exp(p1[1])
    p1a0_m, p1a0_e = encode_mantissa_exp(p1[2])
    p2a2_m, p2a2_e = encode_mantissa_exp(p2[0])
    p2a1_m, p2a1_e = encode_mantissa_exp(p2[1])
    p2a0_m, p2a0_e = encode_mantissa_exp(p2[2])

    return {
        "scale_coeff_p1_a2": p1a2_m,
        "scale_exp_p1_a2": p1a2_e,
        "scale_coeff_p1_a1": p1a1_m,
        "scale_exp_p1_a1": p1a1_e,
        "scale_coeff_p1_a0": p1a0_m,
        "scale_exp_p1_a0": p1a0_e,
        "scale_coeff_th": th_m,
        "scale_exp_th": th_e,
        "scale_coeff_p2_a2": p2a2_m,
        "scale_exp_p2_a2": p2a2_e,
        "scale_coeff_p2_a1": p2a1_m,
        "scale_exp_p2_a1": p2a1_e,
        "scale_coeff_p2_a0": p2a0_m,
        "scale_exp_p2_a0": p2a0_e,
    }


def fit_residuals(
    x: np.ndarray, y: np.ndarray, registers: dict[str, int], threshold_cps: float | None = None, dose_limit: float | None = None
) -> dict[str, float]:
    """Evaluate fit quality by reconstructing the polynomial from register values.

    Useful before committing to the device — call this after fit_piecewise_quadratic
    to verify the encoded coefficients reproduce the calibration data acceptably.

    Returns a dict with keys ``rmse``, ``max_abs_err``, and ``threshold_cps``.
    """

    def _decode(coeff_key: str, exp_key: str) -> float:
        return registers[coeff_key] * 10 ** registers[exp_key]

    if threshold_cps is None:
        threshold_cps = _decode("scale_coeff_th", "scale_exp_th")

    if dose_limit is None:
        dose_limit = max(y)

    a2_p1 = _decode("scale_coeff_p1_a2", "scale_exp_p1_a2")
    a1_p1 = _decode("scale_coeff_p1_a1", "scale_exp_p1_a1")
    a0_p1 = _decode("scale_coeff_p1_a0", "scale_exp_p1_a0")
    a2_p2 = _decode("scale_coeff_p2_a2", "scale_exp_p2_a2")
    a1_p2 = _decode("scale_coeff_p2_a1", "scale_exp_p2_a1")
    a0_p2 = _decode("scale_coeff_p2_a0", "scale_exp_p2_a0")

    low = x <= threshold_cps
    high = (x > threshold_cps) & (y < dose_limit)

    y_low = a2_p1 * x[low] ** 2 + a1_p1 * x[low] + a0_p1
    y_high = a2_p2 * x[high] ** 2 + a1_p2 * x[high] + a0_p2
    y_hat = [*y_low, *y_high]
    err = y_hat - y[low | high]
    return {
        "rmse": float(np.sqrt(np.mean(err**2))),
        "max_abs_err": float(np.max(np.abs(err))),
        "threshold_cps": threshold_cps,
    }


# ---------------------------------------------------------------------------
# High-level entry point
# ---------------------------------------------------------------------------


def apply_calibration(
    device: GeigerDevice,
    path: str | Path | None = None,
    threshold_cps: float | None = None,
    x_col: str = "x",
    y_col: str = "y",
    dry_run: bool = False,
) -> dict[str, int]:
    """Load a calibration CSV, fit the polynomial, and write coefficients to the device.

    Args:
        device:         A connected GeigerDevice instance.
        path:           Path to a CSV file with CPS (x) and dose-rate (y) columns.
                        Pass None to use the bundled default calibration.
        threshold_cps:  CPS split point between the two polynomial segments.
                        Defaults to the geometric mean of the CPS range.
        x_col:          Name of the CPS column in the CSV (default ``"x"``).
        y_col:          Name of the dose-rate column in the CSV (default ``"y"``).
        dry_run:        If True, fit and return the register dict without writing
                        to the device.  Useful for previewing before committing.

    Returns the dict of ``{register_name: value}`` that was (or would be) written.
    """
    x, y = load_calibration_csv(path, x_col=x_col, y_col=y_col)
    registers = fit_piecewise_quadratic(x, y, threshold_cps)

    if not dry_run:
        for name, value in registers.items():
            device.write(name, value)

    return registers
