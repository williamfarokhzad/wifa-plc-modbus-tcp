"""Read-only Modbus TCP frame replay. No sockets, writes, or PLC required."""
import argparse
import json
import struct
from pathlib import Path

HEADER = struct.Struct(">HHHB")


class FrameError(ValueError):
    """The byte stream violates this lab's frame or pairing rules."""


class DeviceException(FrameError):
    def __init__(self, code):
        self.code = code
        super().__init__(f"Modbus exception 0x{code:02x}")


def make_request(transaction, unit, start, quantity):
    for name, number, high in (
        ("transaction", transaction, 65535), ("unit", unit, 255),
        ("start", start, 65535), ("quantity", quantity, 125),
    ):
        if type(number) is not int or not 0 <= number <= high:
            raise FrameError(f"{name} must be an integer from 0 to {high}")
    if quantity == 0 or start + quantity > 65536:
        raise FrameError("invalid holding-register range")
    return HEADER.pack(transaction, 0, 6, unit) + struct.pack(">BHH", 3, start, quantity)


class FrameReader:
    """Split a TCP byte stream into (transaction, unit, PDU) tuples."""

    def __init__(self):
        self.pending = bytearray()

    def feed(self, chunk):
        self.pending.extend(chunk)
        frames = []
        while len(self.pending) >= HEADER.size:
            transaction, protocol, length, unit = HEADER.unpack_from(self.pending)
            if protocol != 0 or not 2 <= length <= 254:
                raise FrameError("invalid MBAP protocol or length")
            end = 6 + length
            if len(self.pending) < end:
                break
            frames.append((transaction, unit, bytes(self.pending[7:end])))
            del self.pending[:end]
        return frames

    def finish(self):
        if self.pending:
            raise FrameError("incomplete frame at end of stream")


def decode_response(frame, transaction, unit, quantity):
    actual_transaction, actual_unit, pdu = frame
    if actual_transaction != transaction or actual_unit != unit:
        raise FrameError("response transaction or unit does not match request")
    if pdu[0] == 0x83:
        if len(pdu) != 2:
            raise FrameError("malformed exception response")
        raise DeviceException(pdu[1])
    if (pdu[0] != 3 or len(pdu) < 2 or pdu[1] != 2 * quantity
            or len(pdu) != 2 + pdu[1]):
        raise FrameError("unexpected function or register byte count")
    return list(struct.unpack(f">{quantity}H", pdu[2:]))


def replay(case):
    transaction, unit, start, quantity = (case[key] for key in
                                          ("transaction", "unit", "start", "quantity"))
    request = make_request(transaction, unit, start, quantity)
    reader = FrameReader()
    frames = []
    for chunk in case["response_chunks"]:
        frames.extend(reader.feed(bytes.fromhex(chunk)))
    reader.finish()
    if len(frames) != 1:
        raise FrameError("this replay expects exactly one response frame")
    return {"request_hex": request.hex(" "),
            "registers": decode_response(frames[0], transaction, unit, quantity)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="offline JSON capture fixture")
    args = parser.parse_args()
    try:
        result = replay(json.loads(args.fixture.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"Replay failed: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
