import json
import subprocess
import sys
import unittest
from pathlib import Path

from modbus_lab import DeviceException, FrameError, FrameReader, decode_response, make_request, replay

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
RESPONSE = bytes.fromhex("00 2a 00 00 00 07 ff 03 04 01 2c ff fe")


class ModbusTests(unittest.TestCase):
    def case(self, name):
        return json.loads((EXAMPLES / f"{name}.json").read_text())

    def test_request_manual_bytes(self):
        self.assertEqual(make_request(42, 255, 10, 2),
                         bytes.fromhex("00 2a 00 00 00 06 ff 03 00 0a 00 02"))

    def test_register_range_boundary(self):
        self.assertEqual(make_request(0, 1, 65535, 1)[8:10], b"\xff\xff")
        for start, quantity in [(65535, 2), (0, 0), (0, 126), (-1, 1), (True, 1)]:
            with self.subTest(start=start, quantity=quantity), self.assertRaises(FrameError):
                make_request(0, 1, start, quantity)

    def test_all_pairs_of_cut_points(self):
        for a in range(len(RESPONSE) + 1):
            for b in range(a, len(RESPONSE) + 1):
                reader = FrameReader()
                frames = reader.feed(RESPONSE[:a]) + reader.feed(RESPONSE[a:b])
                frames += reader.feed(RESPONSE[b:])
                reader.finish()
                self.assertEqual(len(frames), 1)
                self.assertEqual(decode_response(frames[0], 42, 255, 2), [300, 65534])

    def test_combined_and_partial_frames(self):
        reader = FrameReader()
        self.assertEqual(len(reader.feed(RESPONSE + RESPONSE + RESPONSE[:4])), 2)
        self.assertEqual(len(reader.feed(RESPONSE[4:])), 1)
        reader.finish()

    def test_truncated_tail(self):
        for end in range(1, len(RESPONSE)):
            reader = FrameReader()
            self.assertFalse(reader.feed(RESPONSE[:end]))
            with self.assertRaisesRegex(FrameError, "incomplete"):
                reader.finish()

    def test_invalid_header(self):
        for wire in ("00 2a 00 01 00 02 ff", "00 2a 00 00 00 01 ff", "00 2a 00 00 00 ff ff"):
            with self.assertRaisesRegex(FrameError, "MBAP"):
                FrameReader().feed(bytes.fromhex(wire))

    def test_inconsistent_payload_and_unit(self):
        for unit, pdu in [(1, "03 04 01 2c ff fe"), (255, "03 02 01 2c ff fe"),
                          (255, "03 04 01 2c"), (255, "04 04 01 2c ff fe"),
                          (255, "83 02 00")]:
            with self.assertRaises(FrameError):
                decode_response((42, unit, bytes.fromhex(pdu)), 42, 255, 2)

    def test_maximum_quantity(self):
        wire = bytes.fromhex("00 2a 00 00 00 fd ff 03 fa") + bytes(range(250))
        frame, = FrameReader().feed(wire)
        values = decode_response(frame, 42, 255, 125)
        self.assertEqual((len(values), values[0], values[-1]), (125, 1, 248 * 256 + 249))

    def test_examples(self):
        self.assertEqual(replay(self.case("split"))["registers"], [300, 65534])
        with self.assertRaises(DeviceException) as exc:
            replay(self.case("exception"))
        self.assertEqual(exc.exception.code, 2)
        with self.assertRaisesRegex(FrameError, "does not match"):
            replay(self.case("stale"))

    def test_cli_error_does_not_emit_values(self):
        result = subprocess.run([sys.executable, "modbus_lab.py", "examples/stale.json"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("does not match", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
