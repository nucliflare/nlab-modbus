from __future__ import annotations

import logging
import time
from typing import Iterable

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer import FramerType
from serial.tools import list_ports
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ZeroconfServiceTypes

from nlab_modbus.core.enums import DeviceType

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


def scan_local_modbus_devices(
    device_ids: Iterable[int] = range(1, 17),
    baudrate: int = 115200,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: int = 1,
    timeout: float = 0.1,
    retries: int = 0,
) -> list[dict]:
    """Probe every serial port for responding Modbus devices.

    Opens each available COM/tty port in turn, then walks device_ids 1–16
    and reads the hardware_version input register (address 0) from each.
    A successful response identifies both the device type and its Modbus
    address.  Each port is closed before moving to the next.

    Returns a list of dicts with keys:
        type (DeviceType), device_id (int), host (None), port (str),
        description (str), hardware_id (int).

    The 100 ms timeout and zero retries are chosen for speed: a missing device
    silently times out in one slot rather than blocking the scan for seconds.
    RTU devices respond in <10 ms on a healthy bus so 100 ms is still 10× headroom.
    """
    found: list[dict] = []
    device_ids_list = list(device_ids)
    all_ports = list(list_ports.comports())
    logger.info("Local scan: found %d serial port(s): %s", len(all_ports), [p.device for p in all_ports])

    for port_info in all_ports:
        port = port_info.device
        logger.debug("Probing %s (%s) at %d baud", port, port_info.description, baudrate)

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

        try:
            if not client.connect():
                logger.warning("Could not open %s — skipping", port)
                continue

            # USB-CDC and RS-485 direction-control hardware needs a moment to
            # settle after the port is opened; the first request fails silently
            # without this delay.
            time.sleep(0.05)

            # pymodbus closes the connection after (retries+3+1) consecutive
            # timeouts.  With retries=0 that is 4 misses — fewer than the
            # number of IDs we probe.  Raise the limit so the connection stays
            # open for the full scan and no close/reopen cycle disturbs the bus.
            try:
                n = len(device_ids_list) + 5
                client.transaction.count_until_disconnect = n
                client.transaction.max_until_disconnect = n
            except AttributeError:
                pass

            for device_id in device_ids_list:
                try:
                    result = client.read_input_registers(
                        address=0,
                        count=1,
                        device_id=device_id,
                    )

                    if result.isError():
                        continue

                    hardware_id = int(result.registers[0])
                    try:
                        device_type = DeviceType(hardware_id >> 8)
                    except ValueError:
                        logger.warning("%s id=%d: unknown hardware_version=0x%04X — skipped", port, device_id, hardware_id)
                        continue

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
                    logger.info("Found %s id=%d type=%s on %s", port, device_id, device_type.name, port_info.description)

                except (ModbusException, OSError, ValueError):
                    continue

        finally:
            client.close()

    logger.info("Local scan complete: %d device(s) found", len(found))
    return found


def scan_remote_modbus_devices(
    host: str,
    port: int,
    candidate_ids: range | None = None,
    scan_timeout: float = 0.02,
) -> list[dict]:
    """
    Scan for Modbus devices on the given TCP host:port by reading the
    ``hardware_version`` input register (address 0, count 1) from each
    candidate device_id.

    Returns a dict mapping ``device_id -> hardware_version`` for every
    device that responded successfully.  Devices that don't answer or
    return an error are silently skipped.
    """
    if candidate_ids is None:
        candidate_ids = range(1, 17)  # 1 .. 16

    candidate_ids_list = list(candidate_ids)
    found: list[dict] = []
    logger.info("Remote scan: probing %s:%s for device IDs %s", host, port, candidate_ids_list)

    client = ModbusTcpClient(
        host=host,
        port=port,
        framer=FramerType.RTU,
        timeout=scan_timeout,
        retries=0,
    )
    try:
        if not client.connect():
            logger.warning("Could not connect to %s:%s — skipping", host, port)
            return found

        # Prevent pymodbus from closing the connection after a few consecutive
        # timeouts (default count_until_disconnect = retries+3 = 3).
        try:
            n = len(candidate_ids_list) + 5
            client.transaction.count_until_disconnect = n
            client.transaction.max_until_disconnect = n
        except AttributeError:
            pass

        for device_id in candidate_ids_list:
            try:
                result = client.read_input_registers(
                    address=0,
                    count=1,
                    device_id=device_id,
                )
                if not result.isError():
                    hardware_id = int(result.registers[0])
                    try:
                        device_type = DeviceType(hardware_id >> 8)
                    except ValueError:
                        logger.warning("%s:%s id=%d: unknown hardware_version=0x%04X — skipped", host, port, device_id, hardware_id)
                        continue
                    found.append({"type": device_type, "device_id": device_id, "host": host, "port": port})
                    logger.info("Found %s:%s id=%d type=%s", host, port, device_id, device_type.name)
            except Exception:
                continue
    finally:
        client.close()

    logger.info("Remote scan %s:%s complete: %d device(s) found", host, port, len(found))
    return found


def scan_remote_boards(
    timeout: float = 0.4,
    name_filter: str | None = "nucliflare",
    service_type: str | None = None,
) -> list:
    """One-shot mDNS scan. Returns {name: {...}} and cleans up before returning.

    If name_filter is given, only devices whose service name contains that
    substring are collected. If None, every device is collected.
    """
    zc = Zeroconf()
    found: dict = {}

    class _Collector(ServiceListener):
        def add_service(self, zc_, type_, name):
            if name_filter is not None and name_filter not in name:
                return  # skip resolving entirely — cheaper than filtering after
            info = zc_.get_service_info(type_, name, timeout=int(timeout * 1000))
            if not info:
                return
            found[name] = {
                "type": type_,
                "addresses": info.parsed_addresses(),
                "port": info.port,
                "server": info.server,
                "properties": {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v) for k, v in info.properties.items()},
            }

        update_service = add_service

        def remove_service(self, *a):
            pass

    try:
        if service_type:
            types = [service_type]
        else:
            types = list(ZeroconfServiceTypes.find(zc=zc, timeout=timeout))

        browsers = [ServiceBrowser(zc, t, _Collector()) for t in types]
        time.sleep(timeout)
    finally:
        zc.close()

    ips = [items["addresses"][0] for name, items in found.items()]
    if ips:
        logger.info("mDNS scan found %d board(s): %s", len(ips), ips)
    else:
        logger.info("mDNS scan found no boards (filter=%r, timeout=%.1fs)", name_filter, timeout)
    return ips
