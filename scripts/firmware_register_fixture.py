"""Regenerate tests/fixtures/firmware_registers.json from the firmware register table.

Usage:
    uv run python scripts/firmware_register_fixture.py PATH/TO/modbus_reg.c

The firmware file is only read. The fixture lets the test suite check every
register map against the firmware without needing the firmware repository.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "firmware_registers.json"

SECTIONS = {"BOARD_SIPM": "SIPM", "BOARD_GM": "GM", "BOARD_HV": "HV"}

_META = r'/\*\{"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\}\*/'
HOLDING_RE = re.compile(
    r"^/\*(\d+)\*/\s*\{&([\w.]+),\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^,}]+?)\s*\},\s*" + _META
)
INPUT_RE = re.compile(r"^/\*(\d+)\*/\s*(?:\(int16_t\*\))?&([\w.]+),\s*" + _META)
VERSION_RE = re.compile(r"#define MB_REG_(HOLD|INPUT)_VERSION\s+(\d+)")


def _int(text: str) -> int:
    return int(text.strip(), 0)


def _meta(scale: str, unit: str) -> dict:
    return {"scale": float(scale), "unit": unit or None}


def parse(source: str) -> dict:
    boards: dict[str, dict] = {}
    board = None
    for line in source.splitlines():
        line = line.strip()
        marker = re.match(r"#(?:el)?if defined\((\w+)\)", line)
        if marker:
            board = SECTIONS.get(marker.group(1))
            if board:
                boards[board] = {"holding": [], "input": []}
            continue
        if line.startswith("#endif"):
            board = None
            continue
        if board is None:
            continue
        version = VERSION_RE.match(line)
        if version:
            boards[board][f"{version.group(1).lower().replace('hold', 'holding')}_version"] = int(version.group(2))
            continue
        holding = HOLDING_RE.match(line)
        if holding:
            number, symbol, mode, low, high, default, label, scale, unit, _ = holding.groups()
            boards[board]["holding"].append(
                {
                    "address": int(number) - 1,
                    "symbol": symbol,
                    "label": label.strip(),
                    **_meta(scale, unit),
                    "min": _int(low),
                    "max": _int(high),
                    "default": _int(default),
                    "eeprom": "EE_BKP" in mode,
                    "password": "PASS" in mode,
                }
            )
            continue
        register = INPUT_RE.match(line)
        if register:
            number, symbol, label, scale, unit, _ = register.groups()
            boards[board]["input"].append(
                {"address": int(number) - 1, "symbol": symbol, "label": label.strip(), **_meta(scale, unit)}
            )
    for name, tables in boards.items():
        for kind in ("holding", "input"):
            addresses = [entry["address"] for entry in tables[kind]]
            if addresses != list(range(len(addresses))):
                raise ValueError(f"{name} {kind} table is not contiguous: {addresses}")
    return boards


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    path = Path(argv[0])
    raw = path.read_bytes()
    fixture = {
        "source": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "boards": parse(raw.decode("cp1250")),
    }
    OUTPUT.write_text(json.dumps(fixture, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    counts = {b: (len(t["holding"]), len(t["input"])) for b, t in fixture["boards"].items()}
    print(f"Wrote {OUTPUT} (holding, input): {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
