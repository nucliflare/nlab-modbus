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

logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FoundModbusDevice:
    type: DeviceType
    device_id: int
    port: str
    description: str | None = None
    hardware_id: int | None = None


def scan_local_modbus_devices(
    device_ids: Iterable[int] = range(1, 17),
    baudrate: int = 115200,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: int = 1,
    timeout: float = 0.25,
    retries: int = 1,
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


def build_status_text(device) -> str:
    lines = []

    print(f"Device {device.device_type.name}:", device.connection_info())
    lines.append("== Status of holding registers ==")
    for i, (key, value) in enumerate(device.get_all_holding_registers().items(), start=1):
        lines.append(f"{i}. {key}: {value}")

    lines.append("")
    lines.append("== Status of input registers ==")
    for i, (key, value) in enumerate(device.get_all_input_registers().items(), start=1):
        lines.append(f"{i}. {key}: {value}")

    return "\n".join(lines) + "\n"


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


def main() -> int:

    HOST = "192.168.10.134"
    PORTS = [5001, 5002]
    print("Testing connections")
    all_devices = []
    for port in PORTS:
        remote_found = scan_remote_modbus_devices(HOST, port=port)
        print("Remote found", remote_found)
        client = ModbusTcpClient(
            host=HOST,
            port=port,
            framer=FramerType.RTU,
            timeout=2.0,
        )
        for parameters in remote_found:
            device_id = parameters["device_id"]
            match parameters["type"]:
                case DeviceType.GEIGER:
                    device = GeigerDevice(client=client, device_id=device_id)
                case DeviceType.SIPM:
                    device = SiPMDevice(client=client, device_id=device_id)
                case DeviceType.PSU:
                    device = PSUDevice(client=client, device_id=device_id)

            device.connect()
            all_devices.append(device)

    local_found = scan_local_modbus_devices(
        device_ids=range(1, 16),
        baudrate=115200,
        timeout=0.1,
    )
    print("Local found", local_found)
    for parameters in local_found:
        client = ModbusSerialClient(
            port=parameters["port"],
            framer=FramerType.RTU,
            baudrate=115200,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=0.1,
            retries=1,
        )
        device_id = parameters["device_id"]
        match parameters["type"]:
            case DeviceType.GEIGER:
                device = GeigerDevice(client=client, device_id=device_id)
            case DeviceType.SIPM:
                device = SiPMDevice(client=client, device_id=device_id)
            case DeviceType.PSU:
                device = PSUDevice(client=client, device_id=device_id)

        device.connect()
        all_devices.append(device)

    for device in all_devices:
        print(build_status_text(device))

    for device in all_devices:
        device.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
