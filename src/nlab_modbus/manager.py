import asyncio
from typing import Iterable

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.factory import create_device
from nlab_modbus.discovery.scan import scan_local_modbus_devices, scan_remote_boards, scan_remote_modbus_devices


class DeviceManager:
    """Manages discovered local and remote Modbus devices.

    Provides functionality to scan for Modbus devices on local serial ports
    and remote TCP connections, organize them by type, and manage their lifecycle.
    """

    def __init__(self):
        """Initialize an empty DeviceManager with no discovered devices."""
        self.local: list[BaseModbusDevice] = []
        self.remote: list[BaseModbusDevice] = []

    @property
    def all_devices(self) -> list[BaseModbusDevice]:
        """Return a combined list of all local and remote devices.

        Returns:
            A list containing all devices from both local and remote collections.
        """
        return [*self.local, *self.remote]

    def by_type(self, device_type: DeviceType) -> list[BaseModbusDevice]:
        """Filter devices by their device type.

        Args:
            device_type: The type of device to filter by.

        Returns:
            A list of devices matching the specified device type.
        """
        return [device for device in self.all_devices if device.device_type == device_type]

    def scan_local_ports(
        self,
        device_ids: Iterable[int] = range(1, 17),
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 0.25,
        retries: int = 0,
    ):
        """Scan local serial ports for Modbus devices and add them to the local collection.

        Args:
            device_ids: Range of device IDs to scan for. Defaults to 1-16.
            baudrate: Serial communication baud rate. Defaults to 115200.
            bytesize: Number of data bits. Defaults to 8.
            parity: Parity setting ('N', 'E', 'O'). Defaults to 'N'.
            stopbits: Number of stop bits. Defaults to 1.
            timeout: Timeout in seconds for each scan attempt. Defaults to 0.25.
            retries: Number of retry attempts per scan. Defaults to 1.
        """
        found_local = scan_local_modbus_devices(
            device_ids=device_ids, baudrate=baudrate, bytesize=bytesize, parity=parity, stopbits=stopbits, timeout=timeout, retries=retries
        )
        # print(found_local)
        ports = list({item["port"] for item in found_local})

        for port in ports:
            client = ModbusSerialClient(
                port=port,
                framer=FramerType.RTU,
                baudrate=115200,
                bytesize=8,
                parity="N",
                stopbits=1,
                timeout=0.15,
                retries=0,
            )
            for parameters in found_local:
                if parameters["port"] == port:
                    device = create_device(client, parameters["device_id"], parameters["type"])
                    self.local.append(device)

    def scan_remote(self, host: str, ports: int | list):
        """Scan a remote host on specified port(s) for Modbus devices and add them to the remote collection.

        Args:
            host: The IP address or hostname of the remote device.
            ports: A single port number or list of port numbers to scan.
        """
        if isinstance(ports, int):
            ports = [ports]

        for port in ports:
            found_remote = scan_remote_modbus_devices(host, port)
            for parameters in found_remote:
                client = ModbusTcpClient(
                    host=host,
                    port=port,
                    framer=FramerType.RTU,
                    timeout=0.15,
                )
                device = create_device(client, parameters["device_id"], parameters["type"])
                self.remote.append(device)

    def scan_remote_ips(self, name="nucliflare"):
        """Sync-callable everywhere. Returns dict directly."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            running_loop = False
        else:
            running_loop = True

        if running_loop:
            # Jupyter or qasync: can't block; caller should use the async variant.
            raise RuntimeError("Running loop detected — use `await self.scan_remote_ips_async(name)`.")
        # plain script / Qt worker thread: no loop, just run it
        return scan_remote_boards(name_filter=name)

    async def scan_remote_ips_async(self, name="nucliflare"):
        return await asyncio.to_thread(scan_remote_boards, name_filter=name)

    def get_all_devices(self):
        """Return a combined list of all managed devices.

        Returns:
            A list containing all local and remote Modbus devices.
        """
        return [*self.local, *self.remote]

    def close_all(self):
        """Close connections for all managed devices."""
        for device in self.get_all_devices():
            device.close()
