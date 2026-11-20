# Architecture

```
nlab_modbus/
├── core/          register specs and codec, BaseModbusDevice, transport policy, errors, identity
├── maps/          one register table per board, mirroring the firmware's modbus_reg.c
├── devices/       SiPMDevice, GeigerDevice, PSUDevice (map + type; accessors are generated)
├── discovery/     serial/mDNS/gateway scans, DeviceType → class factory
├── services/      DeviceManager (owns clients), DevicePollingThread (QThread)
├── calibration.py Geiger dose-curve fit and coefficient upload
└── gui/           PySide6 controllers, table models, generated .ui code
```

## Data flow

- **`DeviceManager`** creates one client per serial port or gateway endpoint.
  It hands that client's lock to every device on the bus, so frames never
  interleave. Separate buses run concurrently.
- **`BaseModbusDevice`** reads a whole input or holding table in one
  transaction. On first use it detects how many registers the firmware
  actually has, because older boards have shorter tables.
- **GUI tabs:** each owns a `DevicePollingThread`. A cycle runs queued writes
  (at most 8), reads the input table, and reads the holding table at its own
  interval. Results reach the GUI through Qt signals. The GUI thread does no
  bus I/O.
- **Display:** values travel as raw counts. Tables and plots convert them to
  physical units with the register map (`value = raw × scale`).

## Transport and timeouts

All clients come from `core/transport.py` with `retries=0`. A timed-out write
may already have been applied, so it must never be resent silently.

| Link | Response timeout | Probe timeout |
|---|---|---|
| Serial 9600 | 0.24 s | 0.08 s |
| Serial 115200 | 0.16 s | 0.05 s |
| Gateway (RTU over TCP, 9600 behind ser2net) | 0.26 s | 0.10 s |

Measured at 9600 baud:
- full input-table read: 65 ms;
- write to a RAM-only register: 22–33 ms;
- write to an EEPROM-backed register: 46–78 ms.

## Firmware behaviour the code relies on

Firmware source: `D:\work\firmware` (`modbus_reg.c`, `modbus_protocol.c`,
`modbus_uart.c`). `tests/fixtures/firmware_registers.json` is generated from
`modbus_reg.c`, and the tests compare every map entry against it.

- **MicroUSB:** answers only at address 1. `rs485_*` settings don't affect it.
- **Unknown registers:** reading past the end of a table returns exception 2.
  That's how shorter tables are detected.
- **Locked writes:** a write to a protected register while locked returns
  exception 4 (`PasswordRequired`).
- **Service password:** `pass_static` accepts any value, so a password is
  verified with a no-op write to a protected register.
- **RS-485 settings writes:** after a write to `rs485_*` over RS-485, the
  board applies the value but sends no reply and drops the next two frames.
  The poller therefore re-checks the link three times before closing it.
- **Missing temperature sensors:** they report -30000, shown as `n/a` (NaN).
