# Changelog

All notable changes to this project are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Discovery tries each serial port at 9600 and then 115200 baud and reports
  the rate that answered. Before, ports were scanned at one baud rate
  (default 115200), so boards on RS-485 adapters at the firmware default of
  9600 were never found.
- Serial ports and gateway endpoints are scanned in parallel
  (`scan_remote_endpoints`). mDNS results list each digitizer once (IPv4
  preferred), so a board is never probed through two addresses that would
  evict each other's ser2net session.

- Register maps cover the full firmware tables: `reset_device_command`,
  `pwm_max_width_ns`, `modbus_reg_version`, `serial_number_hi/lo` and
  `pwm_pulse_width_ns`. Specs record firmware defaults and whether a register
  is saved to EEPROM. `scripts/firmware_register_fixture.py` regenerates the
  test fixture from `modbus_reg.c`, and the tests now compare every address,
  scale, unit, limit, default and flag against it.

### Changed

- Transport: all clients are built in `nlab_modbus.core.transport` with
  timeouts derived from the baud rate (0.24 s at 9600, 0.16 s at 115200,
  0.26 s through the digitizer gateway) and no automatic retries. The
  gateway client previously used 0.15 s with three silent retries, so slow
  EEPROM-backed writes could be sent up to four times.
- `DeviceManager.connect_local()` defaults to 9600 baud (the firmware's
  RS-485 default) and rejects framings other than 8N1. Each device records
  its `link` (port and baud rate, or gateway endpoint).
- Device core: whole register tables are read in one FC04/FC03 transaction
  (holding polls go from up to 29 frames to one). The table length each
  board's firmware implements is detected on first use, so older firmware
  with shorter tables keeps working.
- `get_<register>()`/`set_<register>()` accessors are generated from the
  register maps instead of ~650 lines of hand-written wrappers; names are
  unchanged.
- I/O failures raise typed errors (`DeviceUnavailable`, `PasswordRequired`,
  `IllegalDataAddress`, …, all `RuntimeError` subclasses) instead of
  string-matched pymodbus messages. `DeviceIdentity` decodes the
  hardware/firmware version words.
- Missing I2C temperature sensors (raw -30000) decode as NaN instead of
  -300 degC; raw reads are unchanged.

### Fixed

- SiPM `vout_overload` (and the PSU frame counter) were never refreshed after
  connecting because live polling skipped their addresses.
- Version words, Modbus frame counters and the Geiger pulse counters decode as
  unsigned, so they no longer turn negative above 32767.

### Removed

- Unused `scripts/utilities.py` scan helpers.

## [0.2.7] - 2026-11-05

### Fixed

- Align SiPM, Geiger and PMT-HV engineering units and scale factors with the
  supplied `modbus_reg.c` metadata/comments: SiPM voltage in V, current in uA,
  temperatures in degC, compensation in mV/degC, corrections in %, and baud
  rate in bps. Reserved registers remain unitless.
- Apply the missing 0.01 factor to PMT temperature and preserve fractional
  engineering values in bulk holding-register reads. Raw register counts and
  raw-mode I/O are unchanged. Covered by simulated codec/snapshot tests; no
  live hardware validation.

## [0.2.6] - 2026-10-07

### Added

- Background local serial and remote mDNS/RTU-over-TCP discovery with
  cancellation, configurable Modbus address ranges, and preservation of active
  transports.
- Matching EWT startup splash and focused regression coverage for discovery,
  GUI I/O threading, transport failures, manager configuration, and startup.

### Changed

- Connection probing, initial register reads, service-password writes, polling,
  and ordinary writes now execute outside the GUI thread.
- Polling uses contiguous device snapshots, retains static values, and processes
  bounded write batches so telemetry cannot be starved.
- GitHub and Gitea release workflows now run tests, publish named Windows/Linux
  archives, fail on missing artifacts, and use the sister project's current
  compatible Actions revisions.

### Fixed

- Device unplug events stop polling after three consecutive failures, release
  the transport, close the stale tab, and remove the stale discovery entry.
- Modbus address or baud-rate changes close the invalid connection instead of
  continuing to poll it.
- Register writes enforce declared limits, incompatible serial configurations
  are rejected, and failed setup/version checks release temporary connections.
- Startup discovery no longer overlaps the always-on-top splash with the main
  connection window or prints a traceback for every unanswered Modbus address.
- Unscoped link-local IPv6 mDNS addresses are excluded from remote scan targets.

[Unreleased]: https://github.com/nucliflare/nlab-modbus/compare/v0.2.7...HEAD
[0.2.7]: https://github.com/nucliflare/nlab-modbus/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/nucliflare/nlab-modbus/compare/v0.2.5...v0.2.6
