import asyncio
import threading
from contextlib import contextmanager
from typing import Iterable

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.framer import FramerType

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.discovery.factory import create_device
from nlab_modbus.discovery.scan import (
    scan_local_modbus_devices,
    scan_remote_boards,
    scan_remote_modbus_devices,
)


class _ClientHandle:
    """Owns one Modbus client and the lock serializing access to it.

    Every device sharing a transport (one serial bus, or one TCP socket)
    shares one handle, hence one RLock. Concurrency is serialized per-bus:
    distinct buses run in parallel from separate threads, devices on the same
    bus never interleave frames.
    """

    __slots__ = ("client", "lock", "key", "_refcount")

    def __init__(self, client, key: tuple):
        self.client = client
        self.key = key
        self.lock = threading.RLock()
        self._refcount = 0

    def acquire_ref(self) -> None:
        self._refcount += 1

    def release_ref(self) -> int:
        self._refcount -= 1
        return self._refcount


class DeviceManager:
    """Manages discovered local and remote Modbus devices with per-bus
    concurrency control.

    Devices sharing a transport (same serial port, or same host:port) share a
    single client and a single lock. The lock is injected into each device as
    ``device.bus_lock`` so every Modbus transaction serializes against others
    on the same bus, while distinct buses remain free to run concurrently.
    """

    def __init__(self):
        self.local: list[BaseModbusDevice] = []
        self.remote: list[BaseModbusDevice] = []
        self._handles: dict[tuple, _ClientHandle] = {}  # transport key -> handle
        self._registry_lock = threading.Lock()  # protects _handles + device lists
        self._devices_by_key: dict[tuple, BaseModbusDevice] = {}

    # ---- handle / client lifecycle -------------------------------------

    def _get_or_create_serial_handle(
        self,
        port: str,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 0.15,
        retries: int = 0,
    ) -> _ClientHandle:
        """Return the cached handle for this serial port, creating it if needed.

        Multiple devices on the same RS-485 bus share one client and one lock
        so their frames never interleave.  The handle is not yet connected here;
        pymodbus connects lazily on the first transaction.
        """
        key = ("serial", port)
        handle = self._handles.get(key)
        if handle is None:
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
            handle = _ClientHandle(client, key)
            self._handles[key] = handle
        return handle

    def _get_or_create_tcp_handle(self, host: str, port: int) -> _ClientHandle:
        """Return the cached handle for this host:port, creating it if needed.

        Uses RTU framing over TCP to talk to a ser2net bridge; the framer
        wraps raw RTU frames in a TCP stream rather than using Modbus TCP PDUs.
        """
        key = ("tcp", host, port)
        handle = self._handles.get(key)
        if handle is None:
            client = ModbusTcpClient(
                host=host,
                port=port,
                framer=FramerType.RTU,
                timeout=0.15,
            )
            handle = _ClientHandle(client, key)
            self._handles[key] = handle
        return handle

    def _attach(self, handle, device_id, device_type, collection):
        """Create a device instance, inject the shared bus lock, and register it.

        If the same (transport, device_id) combination is already registered the
        existing device is returned without creating a duplicate — safe to call
        multiple times with the same arguments.
        """
        key = (handle.key, device_id)  # e.g. (("serial", "COM3"), 4)
        existing = self._devices_by_key.get(key)
        if existing is not None:
            return existing  # genuinely the same object, every time
        device = create_device(handle.client, device_id, device_type)
        device.bus_lock = handle.lock
        self._devices_by_key[key] = device
        collection.append(device)
        handle.acquire_ref()
        return device

    # ---- views ----------------------------------------------------------

    @property
    def all_devices(self) -> list[BaseModbusDevice]:
        """All registered devices, local first then remote."""
        return [*self.local, *self.remote]

    def by_type(self, device_type: DeviceType) -> list[BaseModbusDevice]:
        """Filter registered devices by DeviceType."""
        return [d for d in self.all_devices if d.device_type == device_type]

    def get_all_devices(self):
        """Alias for all_devices; retained for backwards compatibility."""
        return [*self.local, *self.remote]

    # ---- local ----------------------------------------------------------

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
        """Auto-discover and register all devices found on local serial ports."""
        found_local = scan_local_modbus_devices(
            device_ids=device_ids,
            baudrate=baudrate,
            bytesize=bytesize,
            parity=parity,
            stopbits=stopbits,
            timeout=timeout,
            retries=retries,
        )
        with self._registry_lock:
            for params in found_local:
                handle = self._get_or_create_serial_handle(
                    params["port"],
                    baudrate=baudrate,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                )
                self._attach(handle, params["device_id"], params["type"], self.local)

    def connect_local(
        self,
        port: str,
        device_id: int,
        device_type: DeviceType,
        baudrate: int = 115200,
        parity: str = "N",
        stopbits: int = 1,
        bytesize: int = 8,
    ):
        """Manually connect one device by serial port and Modbus address.

        Returns the device instance (possibly a cached one if already registered).
        """
        with self._registry_lock:
            handle = self._get_or_create_serial_handle(port, baudrate=baudrate, parity=parity, stopbits=stopbits, bytesize=bytesize)
            return self._attach(handle, device_id, device_type, self.local)

    # ---- remote ---------------------------------------------------------

    def connect_remote(self, host: str, port: int, device_id: int, device_type: DeviceType):
        """Manually connect one device over TCP (ser2net bridge).

        Returns the device instance (possibly cached if already registered).
        """
        with self._registry_lock:
            handle = self._get_or_create_tcp_handle(host, port)
            return self._attach(handle, device_id, device_type, self.remote)

    def scan_remote(self, host: str, ports: int | list):
        """Auto-discover and register all devices on the given TCP host and port(s)."""
        if isinstance(ports, int):
            ports = [ports]
        for port in ports:
            found = scan_remote_modbus_devices(host, port)
            with self._registry_lock:
                for params in found:
                    handle = self._get_or_create_tcp_handle(host, port)
                    self._attach(handle, params["device_id"], params["type"], self.remote)

    def scan_remote_ips(self, name="nucliflare"):
        """Discover boards via mDNS and return their IP addresses (synchronous).

        Raises RuntimeError if called from inside a running asyncio event loop;
        use scan_remote_ips_async() in that context instead.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return scan_remote_boards(name_filter=name)
        raise RuntimeError("Running loop detected — use `await self.scan_remote_ips_async(name)`.")

    async def scan_remote_ips_async(self, name="nucliflare"):
        """Async wrapper around the blocking mDNS scan."""
        return await asyncio.to_thread(scan_remote_boards, name_filter=name)

    # ---- teardown -------------------------------------------------------

    def disconnect(self, device: BaseModbusDevice) -> None:
        """Remove one device; close its client only when the last device on
        that bus is gone (refcount hits zero)."""
        with self._registry_lock:
            for collection in (self.local, self.remote):
                if device in collection:
                    collection.remove(device)
                    break
            else:
                return
            # find the handle this device belonged to
            for handle in self._handles.values():
                if handle.lock is device.bus_lock:
                    if handle.release_ref() <= 0:
                        with handle.lock:
                            handle.client.close()
                        self._handles.pop(handle.key, None)
                    break

    def close_all(self):
        """Close every Modbus client and clear all device registrations."""
        with self._registry_lock:
            for handle in self._handles.values():
                with handle.lock:
                    handle.client.close()
            self._handles.clear()
            self.local.clear()
            self.remote.clear()
