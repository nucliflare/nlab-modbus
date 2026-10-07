# Refactoring plan and device-lifecycle review

## Current assessment

The register maps, device classes, and per-bus locking form a useful core, but
transport ownership, discovery, polling, and GUI state are still coupled. The
highest-risk paths are hardware lifecycle transitions rather than normal
register reads: a device disappearing, an address or baud-rate change, a scan
over an already-open bus, and application shutdown during I/O.

The first two reliability passes are implemented:

- local and remote discovery run outside the GUI thread;
- duplicate scans are suppressed and scans are cancellable during shutdown;
- the configured ID range is used for both serial and TCP probes;
- open transports are not probed using a second client;
- scan input and connection fields are validated;
- failed version verification releases the newly created manager entry;
- a block-read Modbus error is reported explicitly;
- three consecutive input-poll failures mark a device disconnected, stop its
  worker, close its tab/client, and remove its stale discovery entry.
- connection/version probing, initial snapshots, and service-password writes
  run outside the GUI thread;
- the library codec enforces the declared register limits;
- serial handles reject incompatible baud/framing requests;
- live polling uses contiguous snapshots while retaining static values;
- write batches are bounded so polling cannot be starved; and
- address or baud changes stop and release the now-stale connection.

## Proposed phases

### 1. Typed discovery and errors

Replace discovery dictionaries with immutable `Endpoint`, `DiscoveredDevice`,
and `ScanResult` dataclasses. Introduce a small error hierarchy such as
`DeviceUnavailable`, `ProtocolError`, `DeviceMismatch`, and `ValueOutOfRange`.
This removes string matching (for example, checking `exception_code=4`) and
makes partial scan failures reportable per endpoint. Register limits are now
enforced in both the library codec and GUI model.

### 2. Explicit connection state machine

Give each managed device a state (`CONNECTING`, `ONLINE`, `DEGRADED`,
`OFFLINE`, `CLOSING`) and keep retry/backoff policy in one service. A transient
timeout should enter `DEGRADED`; a configurable threshold should enter
`OFFLINE`. Optional reconnect should use bounded exponential backoff and must
re-verify hardware identity before re-enabling writes.

### 3. One transport owner

Make `DeviceManager` the only component that creates, scans through, or closes
a Modbus client. Discovery on an already-open multi-drop bus should borrow the
existing handle under its bus lock instead of skipping it. Serial handle
configuration is now retained and incompatible reuse is rejected.

### 4. Remove all GUI-thread I/O

Completed: connection/version checks, initial table snapshots,
service-password writes, polling, and ordinary writes run on worker threads.
`DeviceTab` now requires its initial snapshots and performs no setup I/O.

### 5. Snapshot-oriented polling

Live polling now uses each device's contiguous `read_snapshot()` and retains
the connect-time values for static fields, keeping plot buffers aligned. Write
processing is capped per cycle. A later optimization may coalesce multiple
queued writes to the same register.

### 6. Testable transport boundary

Define a narrow client protocol and add a scripted fake transport for timeout,
CRC error, exception response, reconnect, and hot-unplug scenarios. Add Qt
integration tests for scan completion, close-during-scan, and lost-device tab
cleanup. Hardware-in-the-loop tests should remain a separate opt-in suite.

## Edge-case matrix

| Scenario | Current behavior | Follow-up |
|---|---|---|
| Device unplugged while polling | Three consecutive input failures stop polling and detach the device | Make threshold/backoff user-configurable; optionally reconnect |
| Shared adapter/bridge disappears with several tabs open | Each device reaches its failure threshold and detaches independently | Promote loss to the transport handle and show one bus-level notification |
| Device disappears after scan but before Connect | Version check fails and the temporary manager entry is released | Surface a distinct `DeviceUnavailable` error |
| Device appears after startup | Manual/F5 scan finds it without freezing the GUI | Add optional periodic discovery |
| Scan requested twice | The already-running scan is retained; duplicate request is ignored | Show progress/cancel control if scans become longer |
| Scan while a tab owns the same transport | Active endpoint is skipped and its known entries are preserved | Probe the bus through the manager-owned client |
| Application closes during scan | Scan is interrupted between probes and joined before Qt teardown | Add deadlines around any library call not honoring its timeout |
| One port/host fails during a scan | Other serial ports and endpoints continue | Return endpoint-specific warnings in `ScanResult` |
| Unknown hardware type responds | Response is logged and skipped | Offer raw/diagnostic mode if required |
| Library caller writes outside a register's declared limits | The codec rejects the write before touching the wire | Add register names to structured validation errors |
| Device briefly resets | Successful polls reset the failure counter | State machine should show `DEGRADED` before disconnecting |
| Modbus address changes | The successful write stops polling and closes/removes the stale connection | Offer guided reconnect to the new address |
| Serial baud changes | The successful write closes the old transport; incompatible reuse is rejected | Offer guided reconnect at the new baud |
| Unplug with writes queued | At most eight writes run per cycle, then input polling checks connectivity | Consider coalescing writes to the same register |
| mDNS advertises no usable address | Service is ignored safely | Record a diagnostic warning per service |
| High-voltage device loses communications | Deliberately deferred for a separate safety review | Enforce fail-safe output behavior in device firmware/hardware watchdog |

The high-voltage fail-safe item cannot be guaranteed by desktop software: an
unplugged or partitioned link prevents the application from sending a shutdown
command. The device firmware should define the safe behavior on watchdog or
communications timeout.
