from __future__ import annotations

import sys

from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports

from nlab_modbus.devices.sipm import SiPMDevice


def find_serial_port() -> str:
    ports = list(list_ports.comports())

    if not ports:
        raise RuntimeError("No serial ports found.")

    print("Available serial ports:")
    for idx, port in enumerate(ports, start=1):
        print(f"{idx}. {port.device} - {port.description}")

    if len(ports) == 1:
        selected = ports[0].device
        print(f"Using only available port: {selected}")
        return selected

    while True:
        choice = input("Select port number: ").strip()

        try:
            index = int(choice) - 1
        except ValueError:
            print("Please enter a number.")
            continue

        if 0 <= index < len(ports):
            selected = ports[index].device
            print(f"Using port: {selected}")
            return selected

        print(f"Please choose a number between 1 and {len(ports)}.")


def main() -> int:
    try:
        port = find_serial_port()
        print("Port found:", port)

        client = ModbusSerialClient(
            port=port,
            baudrate=115200,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=2.0,
        )

        sipm = SiPMDevice(
            client=client,
            device_id=1,
        )

        sipm.connect()

        try:
            hardware_ver = sipm.get_hardware_version()
            firmware_ver = sipm.get_firmware_version()

            print(f"Hardware version: {hardware_ver}")
            print(f"Firmware version: {firmware_ver}")

        finally:
            sipm.close()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
