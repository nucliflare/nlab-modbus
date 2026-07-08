# nlab-modbus-devices

A PySide6 desktop application and Python library for monitoring and controlling three scientific instruments over Modbus RTU: a **SiPM bias voltage board**, a **Geiger-Mueller radiation probe**, and a **photomultiplier HV power supply**. Devices are reachable either directly over a local serial (RS-485) port or remotely through a [ser2net](https://github.com/cminyard/ser2net) TCP bridge, auto-discovered via mDNS.

---

## Supported devices

| Device | `DeviceType` | Hardware version | Description |
|---|---|---|---|
| SiPM board | `SIPM` | 257 | Bias voltage (15.0–78.0 V), temperature compensation, LED driver |
| Geiger-Mueller probe | `GEIGER` | 513 | HV generation (50–650 V), pulse counting, dose rate (mSv/h), dose calibration |
| PMT HV supply | `PSU` | 769 | High-voltage bias for photomultiplier tubes, current monitoring |

---

## Installation

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/).

### Install uv

**Ubuntu / macOS**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
> Restart the terminal after `uv` installation.


**Windows**
```powershell
winget install --id=astral-sh.uv -e
```

### Clone and install

**Library only** (no GUI — use via Python API or CLI scripts):
```bash
git clone https://github.com/nucliflare/nlab-modbus.git
cd nlab-modbus-devices
uv sync
```

> Without the `gui` extra, PySide6 and pyqtgraph are not installed. The library API, device drivers, and discovery utilities are fully functional, but running `nlab-modbus-gui` will fail with an import error.

**With the desktop GUI:**
```bash
uv sync --extra gui
```

**With Jupyter development notebooks:**
```bash
uv sync --extra gui --extra dev
```

### Dependencies

| Package | Extra | Purpose |
|---|---|---|
| `pymodbus` | *(base)* | Modbus RTU client (serial and TCP) |
| `pyserial` | *(base)* | Serial port enumeration |
| `zeroconf` | *(base)* | mDNS auto-discovery of remote boards |
| `PySide6` | `gui` | Qt6 GUI framework |
| `pyqtgraph` | `gui` | Real-time live plots |
| `matplotlib`, `jupyter` | `dev` | Calibration notebooks |

---

## Running the GUI

```bash
uv run nlab-modbus-gui
```

The application window opens with an auto-scan of all available serial ports and mDNS-announced remote boards.

### Startup options

| Option | Default | Description |
|---|---|---|
| `--baudrate BAUD` | `115200` | Baud rate used for the initial serial scan |
| `--start-id ID` | `1` | First Modbus device ID to probe |
| `--end-id ID` | `16` | Last Modbus device ID to probe |

Example — scan at 9600 baud for IDs 1–4:
```bash
uv run nlab-modbus-gui --baudrate 9600 --start-id 1 --end-id 4
```

---

## GUI walkthrough

### Connection panel

**Local (serial)**

1. Select a COM port from the *Port* dropdown (populated by scan on startup, or type one manually).
2. Adjust the *Bandwidth* combo if the device runs at a non-default baud rate (e.g. 9600).
3. Select (or type) a device ID. If the ID was found during the scan, the *Type* field is auto-filled.
4. Confirm or change the device type (SIPM / GEIGER / PSU), then click **Connect**.

Serial framing is fixed at **8N1** (8 data bits, no parity, 1 stop bit) — the hardware does not support other configurations.

Click **Scan…** next to the Connect button to re-probe all local serial ports using the current baud rate, without restarting the application. Use this after changing the baud rate combo or plugging in a new device.

**Remote (TCP / ser2net)**

1. Remote boards advertising via mDNS (`nucliflare` service name) are discovered automatically at startup.
2. Select (or type) a host IP, then pick or type the TCP port (5001 or 5002).
3. Select (or type) a device ID. If the combination was found during the scan, the *Type* field is auto-filled.
4. Confirm or change the device type, then click **Connect**.

Click **Scan…** next to the remote Connect button to re-run mDNS discovery and re-probe all found hosts without restarting.

Use **Connection → Scan for available devices** (or press **F5**) to run both a local and a remote scan at once.

Multiple devices can be connected simultaneously. Each gets its own tab.

**Hardware version check**

After a successful connection the application reads the device's `hardware_version` register and compares it to the selected type. If they do not match a dialog asks whether to open the tab anyway — the register map may not match the physical hardware, so the default answer is *No*.

### Device tab

Each connected device opens a tab labelled with its connection string (e.g. `serial://COM3:1` or `192.168.1.42:5001:2`).

| Panel | Description |
|---|---|
| **Holding registers** | Read/write configuration table. Click a value cell to edit it; the entered value is validated against the register's min/max before being sent to the device. Hover over a register name for a description tooltip. Password-protected registers are greyed out until service mode is unlocked. |
| **Input registers** | Live read-only telemetry table, updated at the configured refresh rate. Hover over a register name for a description tooltip. |
| **Plot** column | Check the *Plot* box next to any input register to add a live time-series trace to the chart. Multiple registers can be plotted simultaneously. |
| **Clear Plot** button | Resets all ring buffers and the time axis. |
| **Disconnect** button | Stops the polling thread and removes the tab. |
| **Refresh rate** spinner | Adjusts the polling interval in milliseconds (100–10 000 ms). Changes take effect immediately without reconnecting. |

### Status bar

Poll errors and write failures are reported in the main window status bar with the connection string prepended for easy identification when multiple tabs are open.

---

## Architecture overview

```
nlab_modbus/
├── core/                  # Register spec, codec, and base device class
│   ├── enums.py           # DeviceType enum (SIPM, GEIGER, PSU)
│   ├── register_specs.py  # RegisterSpec dataclass, encode/decode helpers
│   └── base_modbus_device.py  # Protocol-agnostic base: read/write/lock
├── maps/                  # Per-device register catalogs
│   ├── sipm_map.py
│   ├── geiger_map.py
│   └── psu_map.py
├── devices/               # Concrete device subclasses with typed getters/setters
│   ├── sipm.py
│   ├── geiger.py
│   └── psu.py
├── discovery/
│   ├── factory.py         # Device factory (DeviceType → class)
│   └── scan.py            # Serial port scan, TCP scan, mDNS discovery
├── services/
│   ├── manager.py         # DeviceManager: per-bus locking, client pooling
│   └── polling_worker.py  # QThread that reads input regs and drains write queue
└── gui/
    ├── main_app.py        # Entry point: QApplication + ModbusMainWindow
    ├── controller/
    │   ├── main_controller.py  # Main window: connection panel, tab management
    │   └── tab_controller.py   # Per-device tab: tables, plots, polling thread
    ├── model/
    │   ├── register_tables.py  # QAbstractTableModel for holding and input regs
    │   └── ring_buffer.py      # Fixed-size numpy circular buffer for plot data
    └── generated/              # UI files generated from Qt Designer
```

### Concurrency model

- The GUI thread never touches Modbus directly.
- Each device tab owns one `DevicePollingThread` (a `QThread`) that reads input registers on a configurable interval.
- Write requests from the GUI are put on a `queue.Queue`; the polling thread drains the queue between read cycles, then does one holding-register readback to confirm.
- All Modbus transactions are serialized with a **per-bus `RLock`** injected by `DeviceManager`. Devices on different buses run concurrently; devices sharing a bus take turns.
- Qt `Signal`/`Slot` connections cross the thread boundary safely for all data updates and error notifications.

### Register codec

`RegisterSpec` stores each register's address, Modbus function type (`HOLDING` / `INPUT`), wire dtype (`int16`), min/max bounds, scale factor, engineering unit, and a human-readable description. `BaseModbusDevice.encode()` / `decode()` apply two's-complement sign extension and the scale factor in both directions. Pass `raw=True` to skip scaling and work directly with raw register counts. Contiguous input register ranges are read in a single FC04 block transaction (`read_snapshot()`) to minimise bus traffic.

---

## Using the library without the GUI

```python
from pymodbus.client import ModbusSerialClient
from pymodbus.framer import FramerType
from nlab_modbus.devices.sipm import SiPMDevice

client = ModbusSerialClient(port="COM3", framer=FramerType.RTU, baudrate=115200)
device = SiPMDevice(client, device_id=1)
device.connect()

print(device.get_vout_set())        # read bias voltage setpoint (V)
device.set_vout_set(54.50)          # write new setpoint
device.set_vout_pwr_en(True)        # enable output

status = device.get_status()        # formatted string of all registers
print(status)

device.disconnect()
```

### Auto-discovery

```python
from nlab_modbus.services.manager import DeviceManager

manager = DeviceManager()
manager.scan_local_ports()          # find all devices on all serial ports
manager.scan_remote_ips()           # mDNS → list of IPs
# manager.scan_remote(ip, [5001, 5002])

for device in manager.all_devices:
    print(device.connection_info(), device.get_status())

manager.close_all()
```

---

## Hardware ecosystem

The mDNS auto-discovery uses the service name `nucliflare` — this is specific to [Eastern Wall Technologies](https://ewt.tech) ser2net bridge boards. If your hardware advertises a different service name, pass `name_filter` to `scan_remote_boards()` or set it to `None` to discover all mDNS services.

The three device types (SiPM, Geiger, PMT PSU) are identified by their `hardware_version` register (input register 0). Adding support for a new device type requires a register map in `maps/`, a device subclass in `devices/`, and an entry in the `DeviceType` enum.

## Project information

- **Python**: ≥ 3.11  
- **License**: MIT
