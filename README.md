# nlab-modbus

Desktop GUI and Python library for the Modbus RTU boards from Nuclear-Lab / EWT:
**SiPM bias board**, **PMT high-voltage supply** and **Geiger-Mueller board**.

## Quick start

```bash
# Install uv once: Windows
winget install --id=astral-sh.uv -e
# ... or Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/nucliflare/nlab-modbus.git
cd nlab-modbus
uv run --extra gui nlab-modbus-gui
```

On start-up the GUI scans all serial ports and the digitizer gateways found via
mDNS. Pick a port (or host) and Modbus address and press **Connect**. Press
**F5** to scan again.

## Connecting a board

| Connection | GUI panel | Baud rate | Modbus address |
|---|---|---|---|
| Board MicroUSB | Local | any (the board's UART is fixed at 115200) | always **1** |
| USB-to-RS-485 adapter | Local | board's `rs485_baud`, default **9600** | `rs485_mb_addr`, default 1 |
| Digitizer gateway (ser2net) | Remote, port 5001 or 5002 | set by the gateway: **9600** | `rs485_mb_addr` |

- **Baud rate: Auto** (default) uses the rate found by the scan. If the port
  wasn't scanned, it tries 9600 and then 115200.
- All boards on one RS-485 bus share one baud rate and need distinct addresses.
- **Changing `rs485_baud` or `rs485_mb_addr`:** on RS-485 the tab closes and
  the ports are rescanned; on MicroUSB nothing changes. Behind a gateway, keep
  `rs485_baud` at 9600 unless you also change the gateway's `ser2net.yaml`.

## Using the GUI

- **Help mode:** press **F1** (or use **Help → Help mode**), then click any
  element, table row or column header for a short explanation.
- **Holding registers:** double-click a value to edit it. Edits are checked
  against the firmware limits before they are sent.
- **Units:** values are shown in physical units. **View → Show raw values**
  switches tables and plots to raw register counts.
- **Service password:** grey rows need it; use **Connection → Service mode**.
- **Plots:** tick **Plot** next to an input register. The spin boxes set the
  polling intervals.
- **Debug console:** **View → Debug console** (F12), or double-click the
  status bar, opens the live log in its own window. You can filter it by
  level, source or text, and pause, copy or save it. Tick **Modbus frames**
  to log every request and reply in hex.
- **Theme:** **View → Theme** offers EWT light (default), EWT dark or Classic.
  The change applies at the next start; `NLAB_THEME=dark` overrides it for one launch.

Options: `--baudrate 9600` fixes the serial rate. `--start-id 1 --end-id 16`
sets the scanned address range.

## Python library

```python
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.services.manager import DeviceManager

manager = DeviceManager()
psu = manager.connect_local("COM3", 1, DeviceType.PSU, baudrate=9600)
sipm = manager.connect_remote("192.168.10.128", 5001, 1, DeviceType.SIPM)

print(psu.identify())               # PSU rev 1, fw 0.3
print(psu.read_snapshot())          # all input registers, physical units
sipm.write("vout_set", 45.5)        # volts, checked against the firmware limits
print(sipm.get_vout_set(raw=True))  # 4550: get_/set_<register> exist for every register
manager.close_all()
```

- **Register names, units and limits:** [`src/nlab_modbus/maps/`](src/nlab_modbus/maps/).
- **Discovery:** `scan_local_modbus_devices()`, plus `scan_remote_boards()`
  with `scan_remote_endpoints()`, in `nlab_modbus.discovery.scan`.
- **Errors:** typed, in `nlab_modbus.core.errors`, e.g. `DeviceUnavailable`
  or `PasswordRequired`.

## Development

```bash
uv sync --extra gui --extra dev
uv run python -m unittest discover -s tests
uv run python scripts/gui_compiler.py                            # after editing .ui files
uv run python scripts/firmware_register_fixture.py PATH/modbus_reg.c  # after firmware register changes
```

More: [architecture](docs/ARCHITECTURE.md) · [releasing](docs/RELEASING.md) ·
[changelog](CHANGELOG.md) · [wiki](https://github.com/nucliflare/nlab-modbus/wiki)
(gateway setup, Geiger calibration). Requires Python ≥ 3.12. MIT licence.
