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
    timeout: float = 0.25,
    retries: int = 0,
) -> list[dict]:
    found: list[dict] = []

    for port_info in list_ports.comports():
        port = port_info.device

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
                continue

            for device_id in device_ids:
                try:
                    result = client.read_input_registers(
                        address=0,
                        count=1,
                        device_id=device_id,
                    )

                    if result.isError():
                        continue

                    hardware_id = int(result.registers[0])

                    found.append(
                        {
                            "type": DeviceType(hardware_id),
                            "device_id": device_id,
                            "host": None,
                            "port": port,
                            "description": port_info.description,
                            "hardware_id": hardware_id,
                        }
                    )
                    logger.info("Register found:", result.registers[0])

                except (ModbusException, OSError, ValueError):
                    continue

        finally:
            client.close()

    return found


def scan_remote_modbus_devices(
    host: str,
    port: int,
    candidate_ids: range | None = None,
    scan_timeout: float = 0.02,  # 50 ms
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

    found: list[dict] = []

    for device_id in candidate_ids:
        client = ModbusTcpClient(
            host=host,
            port=port,
            framer=FramerType.RTU,
            timeout=scan_timeout,
        )
        try:
            client.connect()
            # Probe the hardware_version input register (address 0)
            result = client.read_input_registers(
                address=0,
                count=1,
                device_id=device_id,
            )
            if not result.isError():
                logger.info("Register found:", result.registers[0])
                found.append({"type": DeviceType(int(result.registers[0])), "device_id": device_id, "host": host, "port": port})
        except Exception:
            pass  # silently skip unresponsive IDs
        finally:
            client.close()

    return found


def scan_remote_boards(
    timeout: float = 1.0,
    name_filter: str | None = "nucliflare",
    service_type: str | None = None,
) -> dict:
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

    return found


if __name__ == "__main__":
    for name, d in scan_remote_boards().items():
        print(name, d["addresses"], d["port"])
