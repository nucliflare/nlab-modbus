from __future__ import annotations

import os
import sys

from pymodbus.client import ModbusSerialClient
from serial.tools import list_ports

from nlab_modbus.devices.geiger import GeigerDevice


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


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def build_status_text(sipm) -> str:
    lines = []

    lines.append("== Status of holding registers ==")
    for i, (key, value) in enumerate(sipm.get_all_holding_registers().items(), start=1):
        lines.append(f"{i}. {key}: {value}")

    lines.append("")
    lines.append("== Status of input registers ==")
    for i, (key, value) in enumerate(sipm.get_all_input_registers().items(), start=1):
        lines.append(f"{i}. {key}: {value}")

    return "\n".join(lines)


def main() -> int:
    from colorama import just_fix_windows_console

    just_fix_windows_console()

    # Attempt to find and select a serial port for communication
    try:
        port = find_serial_port()
        print("Port found:", port)

        # Initialize the Modbus serial client with the selected port and communication parameters
        client = ModbusSerialClient(
            port=port,
            baudrate=115200,
            bytesize=8,
            parity="N",
            stopbits=1,
            timeout=2.0,
        )

        # Create an instance of the SiPM device using the Modbus client
        geiger = GeigerDevice(
            client=client,
            device_id=1,
        )

        # Establish connection to the SiPM device
        geiger.connect()

        try:
            print(build_status_text(geiger))
            # time.sleep(0.1)

        except Exception as e:
            print(str(e))

        except KeyboardInterrupt:
            print("\nStopped.")

        finally:
            # Ensure the connection to the SiPM device is closed
            geiger.close()

    except Exception as exc:
        # Handle any unexpected errors during execution
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Return success status
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
