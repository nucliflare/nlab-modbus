from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterable
from ipaddress import ip_address

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType
from serial.tools import list_ports
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes

from nlab_modbus.core.enums import DeviceType

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

StopPredicate = Callable[[], bool]


def _normalise_device_ids(device_ids: Iterable[int]) -> list[int]:
    """Materialise, validate, and de-duplicate Modbus server addresses."""
    normalised: list[int] = []
    seen: set[int] = set()
    for value in device_ids:
        device_id = int(value)
        # Firmware accepts 1..254 (the holding-register map exposes the same
        # range), even though the upper addresses are reserved by Modbus.org.
        if not 1 <= device_id <= 254:
            raise ValueError(f"Modbus device ID must be in the range 1..254, got {device_id}")
        if device_id not in seen:
            normalised.append(device_id)
            seen.add(device_id)
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
    """Raise pymodbus' consecutive-timeout limit for a finite address scan."""
    try:
        threshold = probe_count + 5
        client.transaction.count_until_disconnect = threshold
        client.transaction.max_until_disconnect = threshold
    except AttributeError:
        # These are pymodbus implementation details and may not exist in a
        # future version. Scanning still works, but the client may reconnect.
        pass


def _identify_response(
    result,
    *,
    endpoint: str,
    device_id: int,
) -> tuple[DeviceType, int] | None:
    """Return the device type and hardware ID for a successful probe response."""
    if result.isError():
        return None

    try:
        hardware_id = int(result.registers[0])
    except (AttributeError, IndexError, TypeError, ValueError):
        logger.debug("%s id=%d returned no hardware_version register", endpoint, device_id)
        return None

    try:
        device_type = DeviceType(hardware_id >> 8)
    except ValueError:
        logger.warning(
            "%s id=%d: unknown hardware_version=0x%04X - skipped",
            endpoint,
            device_id,
            hardware_id,
        )
        return None
    return device_type, hardware_id


def scan_local_modbus_devices(
    device_ids: Iterable[int] = range(1, 17),
    baudrate: int = 115200,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: int = 1,
    timeout: float = 0.1,
    retries: int = 0,
    exclude_ports: Iterable[str] = (),
    should_stop: StopPredicate | None = None,
) -> list[dict]:
    """Probe available serial ports for responding Modbus devices.

    Ports in ``exclude_ports`` are not opened. This is useful while the GUI is
    already polling a serial transport, since many operating systems do not
    allow a second process handle for the same port. ``should_stop`` is checked
    between probes so a background scan can be cancelled during application
    shutdown.
    """
    if timeout <= 0:
        raise ValueError("Serial scan timeout must be greater than zero")
    found: list[dict] = []
    device_ids_list = _normalise_device_ids(device_ids)
    excluded = set(exclude_ports)
    all_ports = [port for port in list_ports.comports() if port.device not in excluded]
    logger.info(
        "Local scan: found %d unused serial port(s): %s",
        len(all_ports),
        [port.device for port in all_ports],
    )
    if excluded:
        logger.info("Local scan: skipping ports already in use: %s", sorted(excluded))

    for port_info in all_ports:
        if _stopped(should_stop):
            logger.info("Local scan cancelled")
            break

        port = port_info.device
        logger.debug("Probing %s (%s) at %d baud", port, port_info.description, baudrate)
        client = None
        try:
            client = ModbusSerialClient(
                port=port,
                framer=FramerType.RTU,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=timeout,
                retries=retries,
            )
            if not client.connect():
                logger.warning("Could not open %s - skipping", port)
                continue

            # USB-CDC and RS-485 direction-control hardware may discard the
            # first frame if it is sent immediately after opening the port.
            time.sleep(0.05)
            _keep_client_open_during_scan(client, len(device_ids_list))

            for device_id in device_ids_list:
                if _stopped(should_stop):
                    break
                try:
                    result = client.read_input_registers(
                        address=0,
                        count=1,
                        device_id=device_id,
                    )
                    identity = _identify_response(result, endpoint=port, device_id=device_id)
                    if identity is None:
                        continue
                    device_type, hardware_id = identity
                    found.append(
                        {
                            "type": device_type,
                            "device_id": device_id,
                            "host": None,
                            "port": port,
                            "description": port_info.description,
                            "hardware_id": hardware_id,
                        }
                    )
                    logger.info(
                        "Found %s id=%d type=%s on %s",
                        port,
                        device_id,
                        device_type.name,
                        port_info.description,
                    )
                except Exception as exc:
                    logger.debug("No response from %s id=%d: %s", port, device_id, exc)
        except Exception:
            logger.warning("Could not scan serial port %s", port, exc_info=True)
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    logger.debug("Failed to close scan client for %s", port, exc_info=True)

    logger.info("Local scan complete: %d device(s) found", len(found))
    return found


def scan_remote_modbus_devices(
    host: str,
    port: int,
    candidate_ids: Iterable[int] | None = None,
    scan_timeout: float = 0.05,
    should_stop: StopPredicate | None = None,
) -> list[dict]:
    """Probe Modbus addresses on an RTU-over-TCP endpoint."""
    if candidate_ids is None:
        candidate_ids = range(1, 17)
    if not host.strip():
        raise ValueError("Remote host cannot be empty")
    if not 1 <= int(port) <= 65535:
        raise ValueError(f"TCP port must be in the range 1..65535, got {port}")
    if scan_timeout <= 0:
        raise ValueError("Remote scan timeout must be greater than zero")

    candidate_ids_list = _normalise_device_ids(candidate_ids)
    found: list[dict] = []
    logger.info("Remote scan: probing %s:%s for device IDs %s", host, port, candidate_ids_list)

    client = None
    try:
        client = ModbusTcpClient(
            host=host,
            port=port,
            framer=FramerType.RTU,
            timeout=scan_timeout,
            retries=0,
        )
        if _stopped(should_stop):
            return found
        if not client.connect():
            logger.warning("Could not connect to %s:%s - skipping", host, port)
            return found

        _keep_client_open_during_scan(client, len(candidate_ids_list))
        endpoint = f"{host}:{port}"

        for device_id in candidate_ids_list:
            if _stopped(should_stop):
                logger.info("Remote scan %s cancelled", endpoint)
                break
            try:
                result = client.read_input_registers(
                    address=0,
                    count=1,
                    device_id=device_id,
                )
                identity = _identify_response(result, endpoint=endpoint, device_id=device_id)
                if identity is None:
                    continue
                device_type, hardware_id = identity
                found.append(
                    {
                        "type": device_type,
                        "device_id": device_id,
                        "host": host,
                        "port": port,
                        "hardware_id": hardware_id,
                    }
                )
                logger.info("Found %s id=%d type=%s", endpoint, device_id, device_type.name)
            except Exception as exc:
                logger.debug("No response from %s id=%d: %s", endpoint, device_id, exc)
    except Exception:
        logger.warning("Could not scan remote endpoint %s:%s", host, port, exc_info=True)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                logger.debug("Failed to close scan client for %s:%s", host, port, exc_info=True)

    logger.info("Remote scan %s:%s complete: %d device(s) found", host, port, len(found))
    return found


def scan_remote_boards(
    timeout: float = 0.4,
    name_filter: str | None = "nucliflare",
    service_type: str | None = None,
    should_stop: StopPredicate | None = None,
) -> list[str]:
    """Perform a bounded mDNS scan and return unique advertised IP addresses."""
    if timeout <= 0:
        raise ValueError("mDNS scan timeout must be greater than zero")
    zc = Zeroconf()
    found: dict = {}
    found_lock = threading.Lock()

    class _Collector(ServiceListener):
        def add_service(self, zc_, type_, name):
            if _stopped(should_stop):
                return
            if name_filter is not None and name_filter.casefold() not in name.casefold():
                return
            info = zc_.get_service_info(type_, name, timeout=int(timeout * 1000))
            if not info:
                return
            with found_lock:
                found[name] = {
                    "type": type_,
                    "addresses": info.parsed_addresses(),
                    "port": info.port,
                    "server": info.server,
                    "properties": {
                        (key.decode() if isinstance(key, bytes) else key): (
                            value.decode() if isinstance(value, bytes) else value
                        )
                        for key, value in info.properties.items()
                    },
                }

        update_service = add_service

        def remove_service(self, *args):
            pass

    try:
        if _stopped(should_stop):
            return []
        if service_type:
            types = [service_type]
        else:
            types = list(ZeroconfServiceTypes.find(zc=zc, timeout=timeout))

        if not _stopped(should_stop):
            # Keep browser objects alive until the discovery window closes.
            browsers = [ServiceBrowser(zc, item, _Collector()) for item in types]
            if browsers:
                deadline = time.monotonic() + timeout
                while not _stopped(should_stop):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    time.sleep(min(0.05, remaining))
    finally:
        zc.close()

    with found_lock:
        ips = sorted(
            {
                address
                for item in found.values()
                for address in item["addresses"]
                if address and _usable_discovery_address(address)
            }
        )
    if ips:
        logger.info("mDNS scan found %d board(s): %s", len(ips), ips)
    else:
        logger.info("mDNS scan found no boards (filter=%r, timeout=%.1fs)", name_filter, timeout)
    return ips
