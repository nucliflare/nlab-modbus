# Changelog

All notable changes to this project are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
