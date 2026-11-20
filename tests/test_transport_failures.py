from __future__ import annotations

import unittest
import time

from nlab_modbus.core.base_modbus_device import BaseModbusDevice
from nlab_modbus.core.register_specs import RegisterSpec, RegisterType
from nlab_modbus.devices.psu import PSUDevice
from nlab_modbus.services.polling_worker import DevicePollingThread

from fake_firmware import PASSWORD, FakeFirmwareClient


class _ErrorResponse:
    def isError(self) -> bool:
        return True

    def __str__(self) -> str:
        return "simulated Modbus timeout"


class _BlockReadClient:
    def read_input_registers(self, **_kwargs):
        return _ErrorResponse()


class _FailingDevice:
    def __init__(self) -> None:
        self.calls = 0

    def read_snapshot(self, *, raw=False):
        self.calls += 1
        raise OSError("USB device was unplugged")

    def get_all_holding_registers(self, *, raw=False):
        raise AssertionError("holding registers must not be polled after an input failure")

    def __str__(self) -> str:
        return "fake-device"


class _SnapshotDevice:
    def __init__(self) -> None:
        self.writes: list[tuple[str, float, bool]] = []

    def read_snapshot(self, *, raw=False):
        return {"hardware_version": 0x0101, "live": 42}

    def get_all_holding_registers(self, *, raw=False):
        return {"setting": 1}

    def write(self, name, value, *, raw=False):
        self.writes.append((name, value, raw))


class TransportFailureTests(unittest.TestCase):
    def test_block_read_raises_descriptive_error_response(self) -> None:
        device = BaseModbusDevice(_BlockReadClient(), device_id=1)

        with self.assertRaisesRegex(RuntimeError, "address=3 count=4"):
            device.read_raw_block(3, 4)

    def test_polling_stops_after_consecutive_failures(self) -> None:
        device = _FailingDevice()
        worker = DevicePollingThread(
            device,
            refresh_rate_ms=0,
            holding_refresh_rate_ms=0,
            max_consecutive_failures=3,
        )
        lost_messages: list[str] = []
        worker.connection_lost.connect(lost_messages.append)

        # Calling run directly makes this deterministic without starting a
        # native thread; signal delivery is direct in the current thread.
        worker.run()

        self.assertEqual(device.calls, 3)
        self.assertEqual(len(lost_messages), 1)
        self.assertIn("3 consecutive polls", lost_messages[0])

    def test_codec_enforces_declared_register_limits(self) -> None:
        device = BaseModbusDevice(_BlockReadClient(), device_id=1)
        spec = RegisterSpec(
            reg_type=RegisterType.HOLDING,
            address=0,
            dtype="int16",
            min=10,
            max=20,
            scale=0.1,
        )

        self.assertEqual(device.encode(1.5, spec), [15])
        with self.assertRaisesRegex(ValueError, "register limits 10..20"):
            device.encode(0.9, spec)
        with self.assertRaisesRegex(ValueError, "register limits 10..20"):
            device.encode(21, spec, raw_mode=True)

    def test_snapshot_polling_emits_the_block_read(self) -> None:
        device = _SnapshotDevice()
        worker = DevicePollingThread(device)
        updates: list[dict] = []
        worker.input_registers_updated.connect(lambda _elapsed, values: updates.append(values))
        worker._t0 = time.perf_counter()

        self.assertTrue(worker._poll_device_once())

        self.assertEqual(
            updates,
            [{"hardware_version": 0x0101, "live": 42}],
        )

    def test_write_batch_is_bounded_and_transport_change_stops_worker(self) -> None:
        device = _SnapshotDevice()
        worker = DevicePollingThread(device, max_writes_per_cycle=2)
        for value in range(5):
            worker.enqueue_write_command(value, "setting", value)

        worker._process_pending_writes()

        self.assertEqual(len(device.writes), 2)
        self.assertEqual(worker._write_queue.qsize(), 3)

    def test_rs485_change_closes_a_link_that_stops_answering(self) -> None:
        client = FakeFirmwareClient([0x0301, 3], [1, 96, 0])
        device = PSUDevice(client, 1)
        worker = DevicePollingThread(device)
        changed: list[tuple[str, int]] = []
        worker.transport_changed.connect(lambda name, value: changed.append((name, value)))
        worker.enqueue_write_command(0, "rs485_mb_addr", 7)
        client.offline = True  # board now answers elsewhere (RS-485 link)

        worker._process_pending_writes()

        self.assertEqual(changed, [("rs485_mb_addr", 7)])
        self.assertTrue(worker._stop_event.is_set())

    def test_rs485_change_keeps_a_link_that_still_answers(self) -> None:
        client = FakeFirmwareClient([0x0301, 3], [1, 96, 0])
        worker = DevicePollingThread(PSUDevice(client, 1))
        changed: list = []
        worker.transport_changed.connect(lambda *args: changed.append(args))
        worker.enqueue_write_command(1, "rs485_baud", 192)

        worker._process_pending_writes()  # MicroUSB: the board keeps answering

        self.assertEqual(changed, [])
        self.assertEqual(client.holdings[1], 192)
        self.assertFalse(worker._stop_event.is_set())

    def test_service_unlock_is_verified_on_the_device(self) -> None:
        holdings = [1, 96, 0, 800, 40, 40, 0, 20, 200, 10, 10, 0]
        client = FakeFirmwareClient([0x0301, 3], holdings, protected={4, 5, 6, 7, 8, 9, 10}, password_address=11)
        worker = DevicePollingThread(PSUDevice(client, 1))
        results: list[bool] = []
        worker.service_unlock_finished.connect(results.append)

        worker.enqueue_service_unlock(1234)
        worker._process_pending_writes()
        worker.enqueue_service_unlock(PASSWORD)
        worker._process_pending_writes()

        self.assertEqual(results, [False, True])


if __name__ == "__main__":
    unittest.main()
