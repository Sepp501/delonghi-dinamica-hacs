"""Protocol-only tests; require no Home Assistant or Bluetooth hardware."""
import binascii
import importlib.util
from pathlib import Path
import unittest


SOURCE = (
    Path(__file__).resolve().parents[1] /
    "custom_components" / "delonghi_dinamica" / "statistics.py"
)
spec = importlib.util.spec_from_file_location("dinamica_statistics", SOURCE)
statistics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(statistics)


def response(start, first, further=None, marker=0x0F):
    payload = bytearray([0xD0, 0, 0xA2, marker])
    payload += start.to_bytes(2, "big")
    payload += first.to_bytes(4, "big")
    for key, value in (further or {}).items():
        payload += key.to_bytes(2, "big") + value.to_bytes(4, "big")
    payload[1] = len(payload) + 1
    payload += binascii.crc_hqx(payload, 0x1D0F).to_bytes(2, "big")
    return bytes(payload)


class StatisticsProtocolTests(unittest.TestCase):
    def test_request_has_valid_crc(self):
        p = statistics.build_statistics_request(3000, 10)
        self.assertEqual(p[:7], bytes.fromhex("0D 08 A2 0F 0B B8 0A"))
        self.assertEqual(int.from_bytes(p[-2:], "big"), binascii.crc_hqx(p[:-2], 0x1D0F))

    def test_sparse_counters(self):
        p = response(100, 15, {105: 2, 106: 6000, 108: 1})
        self.assertEqual(
            statistics.parse_statistics_response(p, 100),
            {100: 15, 105: 2, 106: 6000, 108: 1},
        )

    def test_both_response_markers(self):
        self.assertEqual(statistics.parse_statistics_response(response(3000, 7, marker=0xF0), 3000), {3000: 7})

    def test_mismatched_or_corrupt_response_is_rejected(self):
        with self.assertRaises(ValueError):
            statistics.parse_statistics_response(response(3000, 7), 3001)
        corrupt = bytearray(response(3000, 7))
        corrupt[8] ^= 1
        with self.assertRaises(ValueError):
            statistics.parse_statistics_response(bytes(corrupt), 3000)

    def test_absent_counters_not_reported_as_zero(self):
        values = statistics.calculated_statistics({3000: 15, 3001: 7, 106: 6000})
        self.assertEqual(values["coffee_total"], 15)
        self.assertEqual(values["milk_coffee_total"], 7)
        self.assertEqual(values["water_liters"], 3)
        self.assertNotIn("descaling_count", values)


if __name__ == "__main__":
    unittest.main()
