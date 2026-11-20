"""Device discovery on local serial ports and digitizer ser2net gateways.

Every probe reads input registers 0-1 (hardware/firmware version). Serial
ports are tried at each candidate baud rate in turn (all devices on one RS-485
bus share a baud rate, so the first rate that answers wins). Ports and gateway
endpoints are probed in parallel because they are independent buses.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from ipaddress import ip_address

from serial.tools import list_ports
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes

from nlab_modbus.core.enums import DeviceType
from nlab_modbus.core.transport import (
    DEFAULT_BAUDRATES,
    GATEWAY_PORTS,
    MDNS_NAME,
    gateway_timeout,
    probe_timeout,
    serial_client,
    tcp_client,
)

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

StopPredicate = Callable[[], bool]


def _normalise_device_ids(device_ids: Iterable[int]) -> list[int]:
    """Materialise, validate (1..254, as the firmware accepts) and de-duplicate IDs."""
    normalised: list[int] = []
    for value in device_ids:
        device_id = int(value)
        if not 1 <= device_id <= 254:
            raise ValueError(f"Modbus device ID must be in the range 1..254, got {device_id}")
        if device_id not in normalised:
            normalised.append(device_id)
    return normalised


def _stopped(should_stop: StopPredicate | None) -> bool:
    return should_stop is not None and should_stop()


def _usable_discovery_address(address: str) -> bool:
    """Reject IPv6 link-local addresses that lack an interface scope."""
    try:
        parsed = ip_address(address)
    except ValueError:
        return False
    return not (parsed.version == 6 and parsed.is_link_local)


def _keep_client_open_during_scan(client, probe_count: int) -> None:
    """Stop pymodbus from dropping the connection after a run of expected timeouts."""
    try:
        client.transaction.count_until_disconnect = probe_count + 5
        client.transaction.max_until_disconnect = probe_count + 5
    except AttributeError:
        pass  # pymodbus internals changed; the scan still works, it may just reconnect


def _probe_ids(client, endpoint: str, device_ids: list[int], should_stop) -> list[dict]:
    """Probe each ID's identity registers; return the devices that answered."""
    found = []
    for device_id in device_ids:
        if _stopped(should_stop):
            break
        try:
            result = client.read_input_registers(address=0, count=1, device_id=device_id)
        except Exception as exc:  # timeouts are the normal case for absent IDs
            logger.debug("No response from %s id=%d: %s", endpoint, device_id, exc)
            continue
        if result.isError() or not getattr(result, "registers", None):
            continue
        hardware_id = int(result.registers[0])
        try:
            device_type = DeviceType(hardware_id >> 8)
        except ValueError:
            logger.warning("%s id=%d: unknown hardware_version=0x%04X - skipped", endpoint, device_id, hardware_id)
            continue
        logger.info("Found %s id=%d type=%s", endpoint, device_id, device_type.name)
        found.append({"type": device_type, "device_id": device_id, "hardware_id": hardware_id})
    return found


def scan_serial_port(
    port: str,
    device_ids: Iterable[int] = range(1, 17),
    baudrates: Iterable[int] = DEFAULT_BAUDRATES,
    *,
    timeout: float | None = None,
    description: str = "",
    should_stop: StopPredicate | None = None,
) -> list[dict]:
    """Probe one serial port, trying each baud rate until devices answer."""
    ids = _normalise_device_ids(device_ids)
    for baudrate in baudrates:
        if _stopped(should_stop):
            return []
        client = serial_client(port, baudrate, timeout=timeout or probe_timeout(baudrate))
        try:
            if not client.connect():
                logger.warning("Could not open %s - skipping", port)
                return []
            time.sleep(0.05)  # adapters may drop a frame sent right after opening
            _keep_client_open_during_scan(client, len(ids))
            found = _probe_ids(client, f"{port}@{baudrate}", ids, should_stop)
        except Exception:
            logger.warning("Could not scan serial port %s at %d baud", port, baudrate, exc_info=True)
            found = []
        finally:
            client.close()
        if found:
            return [
                {**item, "host": None, "port": port, "baudrate": baudrate, "description": description}
                for item in found
            ]
    return []


def scan_local_modbus_devices(
    device_ids: Iterable[int] = range(1, 17),
    baudrate: int | None = None,
    *,
    baudrates: Iterable[int] | None = None,
    timeout: float | None = None,
    exclude_ports: Iterable[str] = (),
    should_stop: StopPredicate | None = None,
    **_legacy_serial_options,
) -> list[dict]:
    """Probe all serial ports (except ``exclude_ports``) in parallel.

    ``baudrate`` scans at one rate; otherwise ``baudrates`` (default 9600 then
    115200) are tried per port. Each result carries the baud rate that answered.
    """
    if timeout is not None and timeout <= 0:
        raise ValueError("Serial scan timeout must be greater than zero")
    ids = _normalise_device_ids(device_ids)
    rates = (baudrate,) if baudrate else tuple(baudrates or DEFAULT_BAUDRATES)
    excluded = set(exclude_ports)
    ports = [p for p in list_ports.comports() if p.device not in excluded]
    logger.info("Local scan of %s at %s baud", [p.device for p in ports], "/".join(map(str, rates)))
    if excluded:
        logger.info("Local scan skips ports in use: %s", sorted(excluded))
    if not ports:
        return []

    def scan(port_info):
        return scan_serial_port(
            port_info.device, ids, rates, timeout=timeout,
            description=port_info.description, should_stop=should_stop,
        )

    with ThreadPoolExecutor(max_workers=len(ports), thread_name_prefix="serial-scan") as pool:
        found = [item for result in pool.map(scan, ports) for item in result]
    logger.info("Local scan complete: %d device(s) found", len(found))
    return found


def scan_remote_modbus_devices(
    host: str,
    port: int,
    candidate_ids: Iterable[int] | None = None,
    scan_timeout: float | None = None,
    should_stop: StopPredicate | None = None,
) -> list[dict]:
    """Probe Modbus IDs on one RTU-over-TCP gateway endpoint."""
    if not host.strip():
        raise ValueError("Remote host cannot be empty")
    if not 1 <= int(port) <= 65535:
        raise ValueError(f"TCP port must be in the range 1..65535, got {port}")
    if scan_timeout is not None and scan_timeout <= 0:
        raise ValueError("Remote scan timeout must be greater than zero")
    ids = _normalise_device_ids(range(1, 17) if candidate_ids is None else candidate_ids)
    endpoint = f"{host}:{port}"
    client = tcp_client(host, port, timeout=scan_timeout or gateway_timeout(probe=True))
    found: list[dict] = []
    try:
        if _stopped(should_stop):
            return found
        if not client.connect():
            logger.warning("Could not connect to %s - skipping", endpoint)
            return found
        _keep_client_open_during_scan(client, len(ids))
        found = [{**item, "host": host, "port": port} for item in _probe_ids(client, endpoint, ids, should_stop)]
    except Exception:
        logger.warning("Could not scan remote endpoint %s", endpoint, exc_info=True)
    finally:
        client.close()
    logger.info("Remote scan %s complete: %d device(s) found", endpoint, len(found))
    return found


def scan_remote_endpoints(
    hosts: Iterable[str],
    ports: Iterable[int] = GATEWAY_PORTS,
    candidate_ids: Iterable[int] = range(1, 17),
    *,
    skip: Iterable[tuple[str, int]] = (),
    should_stop: StopPredicate | None = None,
) -> list[dict]:
    """Probe every (host, port) gateway endpoint in parallel, except those in ``skip``.

    ser2net drops its current client when a new one connects (``kickolduser``),
    so endpoints that already have an open connection must be skipped.
    """
    ids = _normalise_device_ids(candidate_ids)
    skipped = set(skip)
    endpoints = [(h, p) for h in hosts for p in ports if (h, p) not in skipped]
    if not endpoints:
        return []
    with ThreadPoolExecutor(max_workers=len(endpoints), thread_name_prefix="tcp-scan") as pool:
        results = pool.map(lambda ep: scan_remote_modbus_devices(ep[0], ep[1], ids, should_stop=should_stop), endpoints)
        return [item for result in results for item in result]


def _preferred_address(addresses: list[str]) -> str | None:
    """One usable address per board: IPv4 first, then routable IPv6."""
    usable = [a for a in addresses if _usable_discovery_address(a)]
    usable.sort(key=lambda a: (ip_address(a).version, a))
    return usable[0] if usable else None


def scan_remote_boards(
    timeout: float = 0.4,
    name_filter: str | None = MDNS_NAME,
    service_type: str | None = None,
    should_stop: StopPredicate | None = None,
) -> list[str]:
    """Bounded mDNS scan; returns one IP address per advertising board.

    Services are grouped by host name, so a board advertising several
    services or addresses is reported once.
    """
    if timeout <= 0:
        raise ValueError("mDNS scan timeout must be greater than zero")
    zc = Zeroconf()
    addresses_by_host: dict[str, set[str]] = {}
    lock = threading.Lock()

    class _Collector(ServiceListener):
        def add_service(self, zc_, type_, name):
            if _stopped(should_stop):
                return
            if name_filter is not None and name_filter.casefold() not in name.casefold():
                return
            info = zc_.get_service_info(type_, name, timeout=int(timeout * 1000))
            if info:
                with lock:
                    addresses_by_host.setdefault(info.server or name, set()).update(info.parsed_addresses())

        update_service = add_service

        def remove_service(self, *args):
            pass

    try:
        if _stopped(should_stop):
            return []
        types = [service_type] if service_type else list(ZeroconfServiceTypes.find(zc=zc, timeout=timeout))
        browsers = [ServiceBrowser(zc, item, _Collector()) for item in types]  # noqa: F841 - keep alive
        deadline = time.monotonic() + timeout
        while browsers and not _stopped(should_stop) and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        zc.close()

    with lock:
        ips = sorted({ip for addrs in addresses_by_host.values() if (ip := _preferred_address(list(addrs)))})
    logger.info("mDNS scan found %d board(s): %s", len(ips), ips)
    return ips
