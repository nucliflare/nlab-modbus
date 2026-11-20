from __future__ import annotations

import unittest

from nlab_modbus.core.transport import (
    Link,
    gateway_timeout,
    probe_timeout,
    response_timeout,
    serial_client,
    tcp_client,
)


class TimingTests(unittest.TestCase):
    def test_timeouts_cover_measured_latencies(self):
        # Measured on hardware at 9600 baud: 65 ms for a full input block,
        # up to 78 ms for an EEPROM-backed write through the gateway, 37 ms
        # for a 2-register probe through an FTDI adapter.
        self.assertGreaterEqual(response_timeout(9600), 0.2)
        self.assertGreaterEqual(gateway_timeout(), 0.2)
        self.assertGreaterEqual(probe_timeout(9600), 0.07)
        # Faster buses get proportionally shorter waits.
        self.assertLess(response_timeout(115200), response_timeout(9600))
        self.assertLess(probe_timeout(115200), 0.07)

    def test_clients_never_resend_requests(self):
        self.assertEqual(serial_client("COM_TEST", 9600).retries, 0)
        self.assertEqual(tcp_client("192.0.2.1", 5001).retries, 0)


class LinkTests(unittest.TestCase):
    def test_link_keys_identify_one_transport(self):
        self.assertEqual(Link("serial", "COM3", baudrate=9600).key, ("serial", "COM3"))
        self.assertEqual(Link("tcp", "192.0.2.1", port=5001).key, ("tcp", "192.0.2.1", 5001))
        self.assertEqual(str(Link("serial", "COM3", baudrate=9600)), "COM3 @ 9600")


if __name__ == "__main__":
    unittest.main()
