from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterable

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.enums import DeviceType
from nlab_modbus.core.transport import Link, serial_client, tcp_client
from nlab_modbus.discovery.factory import create_device
from nlab_modbus.discovery.scan import (
    scan_local_modbus_devices,
    scan_remote_boards,
    scan_remote_modbus_devices,
)


class _ClientHandle:
    """One Modbus client, its link and the lock shared by every device on it."""

    __slots__ = ("client", "link", "lock", "refcount")

    def __init__(self, client, link: Link):
        self.client = client
        self.link = link
        self.lock = threading.RLock()
        self.refcount = 0


class DeviceManager:
    """Owns all Modbus clients and the devices attached to them.

    Devices on the same serial port or TCP endpoint share one client and one
    bus lock, so frames never interleave; different buses run concurrently.
    A client is closed when its last device is disconnected.
    """

    def __init__(self):
        self.local: list[BaseModbusDevice] = []
        self.remote: list[BaseModbusDevice] = []
        self._handles: dict[tuple, _ClientHandle] = {}
        self._registry_lock = threading.Lock()
        self._devices_by_key: dict[tuple, BaseModbusDevice] = {}

    # ---- handles ---------------------------------------------------------

    def _serial_handle(self, port: str, baudrate: int) -> _ClientHandle:
        link = Link("serial", port, baudrate=baudrate)
        handle = self._handles.get(link.key)
        if handle is None:
            client = serial_client(port, baudrate)
            if not client.connect():
                raise ConnectionError(f"Could not open serial port {port!r}")
            # USB adapters and RS-485 transceivers may drop a frame sent
            # immediately after the port opens.
            time.sleep(0.05)
            handle = self._handles[link.key] = _ClientHandle(client, link)
        elif handle.link.baudrate != baudrate:
            raise ValueError(
                f"Serial port {port!r} is already open at {handle.link.baudrate} baud; "
                f"disconnect its devices before using {baudrate} baud"
            )
        return handle

    def _tcp_handle(self, host: str, port: int) -> _ClientHandle:
        link = Link("tcp", host, port=port)
        handle = self._handles.get(link.key)
        if handle is None:
            handle = self._handles[link.key] = _ClientHandle(tcp_client(host, port), link)
        return handle

    def _attach(self, handle: _ClientHandle, device_id: int, device_type: DeviceType, collection: list):
        """Return the registered device for (transport, id), creating it if needed."""
        key = (handle.link.key, device_id)
        existing = self._devices_by_key.get(key)
        if existing is not None:
            if existing.device_type != device_type:
                registered = existing.device_type.name if existing.device_type else "unknown"
                raise ValueError(
                    f"Device {device_id} on {handle.link} is already registered as "
                    f"{registered}, not {device_type.name}"
                )
            return existing
        device = create_device(handle.client, device_id, device_type)
        device.bus_lock = handle.lock
        device.link = handle.link
        self._devices_by_key[key] = device
        collection.append(device)
        handle.refcount += 1
        return device

    # ---- views -----------------------------------------------------------

    @property
    def all_devices(self) -> list[BaseModbusDevice]:
        return [*self.local, *self.remote]

    get_all_devices = all_devices.fget  # backwards-compatible method form

    def by_type(self, device_type: DeviceType) -> list[BaseModbusDevice]:
        return [d for d in self.all_devices if d.device_type == device_type]

    def find_device(self, transport: tuple, device_id: int) -> BaseModbusDevice | None:
        """Registered device for a transport key (``("serial", port)`` / ``("tcp", host, port)``)."""
        with self._registry_lock:
            return self._devices_by_key.get((transport, device_id))

    def open_links(self) -> list[Link]:
        """Links that currently have an open client."""
        with self._registry_lock:
            return [handle.link for handle in self._handles.values()]

    def discovery_snapshot(self) -> dict[str, list[dict]]:
        """Registered devices in the same shape as scan results (used by the GUI)."""
        snapshot: dict[str, list[dict]] = {"local": [], "remote": []}
        with self._registry_lock:
            for (_key, device_id), device in self._devices_by_key.items():
                link = device.link
                entry = {"type": device.device_type, "device_id": device_id}
                if link.kind == "serial":
                    snapshot["local"].append({**entry, "host": None, "port": link.address, "baudrate": link.baudrate})
                else:
                    snapshot["remote"].append({**entry, "host": link.address, "port": link.port})
        return snapshot

    # ---- connect ---------------------------------------------------------

    def connect_local(
        self,
        port: str,
        device_id: int,
        device_type: DeviceType,
        baudrate: int = 9600,
        parity: str = "N",
        stopbits: int = 1,
        bytesize: int = 8,
    ) -> BaseModbusDevice:
        """Attach one device on a serial port (8N1 only; the firmware supports nothing else)."""
        if (bytesize, parity.upper(), stopbits) != (8, "N", 1):
            raise ValueError("The boards only support 8N1 serial framing")
        with self._registry_lock:
            return self._attach(self._serial_handle(port, baudrate), device_id, device_type, self.local)

    def connect_remote(self, host: str, port: int, device_id: int, device_type: DeviceType) -> BaseModbusDevice:
        """Attach one device behind a ser2net gateway (RTU over TCP)."""
        with self._registry_lock:
            return self._attach(self._tcp_handle(host, port), device_id, device_type, self.remote)

    # ---- discovery ---------------------------------------------------------

    def scan_local_ports(self, device_ids: Iterable[int] = range(1, 17), baudrate: int | None = None, **_ignored):
        """Discover devices on all serial ports and attach them.

        Without ``baudrate`` each port is tried at 9600 and then 115200 baud.
        """
        for found in scan_local_modbus_devices(device_ids=device_ids, baudrate=baudrate):
            self.connect_local(found["port"], found["device_id"], found["type"], found["baudrate"])

    def scan_remote(self, host: str, ports: int | list, candidate_ids: Iterable[int] = range(1, 17)):
        """Discover devices on gateway port(s) of ``host`` and attach them."""
        for port in [ports] if isinstance(ports, int) else ports:
            for found in scan_remote_modbus_devices(host, port, candidate_ids=candidate_ids):
                self.connect_remote(host, port, found["device_id"], found["type"])

    def scan_remote_ips(self, name: str = "nucliflare") -> list[str]:
        """Gateway IP addresses found via mDNS (blocking; not for use inside an event loop)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return scan_remote_boards(name_filter=name)
        raise RuntimeError("Running loop detected; use `await manager.scan_remote_ips_async(name)`")

    async def scan_remote_ips_async(self, name: str = "nucliflare") -> list[str]:
        return await asyncio.to_thread(scan_remote_boards, name_filter=name)

    # ---- teardown ----------------------------------------------------------

    def disconnect(self, device: BaseModbusDevice) -> None:
        """Detach one device; close its client when no other device uses it."""
        with self._registry_lock:
            for collection in (self.local, self.remote):
                if device in collection:
                    collection.remove(device)
                    break
            else:
                return
            for key in [k for k, v in self._devices_by_key.items() if v is device]:
                del self._devices_by_key[key]
            handle = self._handles.get(device.link.key) if device.link else None
            if handle is not None:
                handle.refcount -= 1
                if handle.refcount <= 0:
                    with handle.lock:
                        handle.client.close()
                    del self._handles[device.link.key]

    def close_all(self) -> None:
        """Close every client and forget all devices."""
        with self._registry_lock:
            for handle in self._handles.values():
                with handle.lock:
                    handle.client.close()
            self._handles.clear()
            self.local.clear()
            self.remote.clear()
            self._devices_by_key.clear()
