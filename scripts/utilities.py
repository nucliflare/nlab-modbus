from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Iterable

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.framer import FramerType
from serial.tools import list_ports

from nlab_modbus.core.enums import DeviceType
from nlab_modbus.devices.geiger import GeigerDevice
from nlab_modbus.devices.psu import PSUDevice
from nlab_modbus.devices.sipm import SiPMDevice

logging.getLogger("pymodbus").setLevel(logging.INFO)

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
                logger.debug("Could not connect to port %s", port)
                continue
            logger.debug("Connected to port %s", port)
            for device_id in device_ids:
                try:
                    result = client.read_input_registers(
                        address=0,
                        count=1,
                        device_id=device_id,
                    )

                    if result.isError():
                        logger.debug("No valid response from device_id=%s on %s", device_id, port)
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
                    logger.info(
                        "Register found: hardware_id=%s device_id=%s port=%s",
                        hardware_id,
                        device_id,
                        port,
                    )

                except (ModbusException, OSError, ValueError) as exc:
                    logger.debug(
                        "Scan failed for device_id=%s on port=%s: %s",
                        device_id,
                        port,
                        exc,
                    )
                    continue

        finally:
            client.close()

    return found


def scan_remote_modbus_devices(
    host: str,
    port: int,
    device_ids: range | None = None,
    timeout: float = 0.02,  # 20 ms
    retries: int = 1,
) -> list[dict]:
    """
    Scan for Modbus devices on the given TCP host:port by reading the
    ``hardware_version`` input register (address 0, count 1) from each
    candidate device_id.

    Returns a dict mapping ``device_id -> hardware_version`` for every
    device that responded successfully.  Devices that don't answer or
    return an error are silently skipped.
    """
    if device_ids is None:
        device_ids = range(1, 17)  # 1 .. 16

    found: list[dict] = []

    for device_id in device_ids:
        client = ModbusTcpClient(host=host, port=port, framer=FramerType.RTU, timeout=timeout, retries=retries)
        try:
            client.connect()
            # Probe the hardware_version input register (address 0)
            result = client.read_input_registers(
                address=0,
                count=1,
                device_id=device_id,
            )
            hardware_id = int(result.registers[0])
            if not result.isError():
                logger.info(
                    "Register found: hardware_id=%s device_id=%s port=%s",
                    hardware_id,
                    device_id,
                    port,
                )
                found.append({"type": DeviceType(hardware_id), "device_id": device_id, "host": host, "port": port})
        except Exception:
            pass  # silently skip unresponsive IDs
        finally:
            client.close()

    return found
