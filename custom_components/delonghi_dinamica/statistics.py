"""Read-only 0xA2 statistics protocol, based on the established DeLonghi BLE integration."""
import binascii


def build_statistics_request(start: int, count: int) -> bytes:
    if not (0 <= start <= 65535 and 1 <= count <= 10):
        raise ValueError("Invalid statistics range")
    payload = bytes((0x0D, 0x08, 0xA2, 0x0F, start >> 8, start & 0xFF, count))
    return payload + binascii.crc_hqx(payload, 0x1D0F).to_bytes(2, "big")


def parse_statistics_response(packet: bytes, expected_start: int) -> dict[int, int]:
    """Validate framing, CRC and first counter before decoding the sparse records."""
    if len(packet) < 12 or packet[0] != 0xD0 or packet[1] + 1 != len(packet):
        raise ValueError("Invalid 0xA2 frame")
    if packet[2] != 0xA2 or packet[3] not in (0x0F, 0xF0):
        raise ValueError("Not a statistics response")
    if binascii.crc_hqx(packet[:-2], 0x1D0F) != int.from_bytes(packet[-2:], "big"):
        raise ValueError("Invalid 0xA2 CRC")
    first_id = int.from_bytes(packet[4:6], "big")
    if first_id != expected_start:
        raise ValueError(f"Wrong statistics start {first_id}, expected {expected_start}")
    data = packet[6:-2]
    if len(data) < 4 or (len(data) - 4) % 6:
        raise ValueError("Malformed statistics fields")
    counters = {first_id: int.from_bytes(data[:4], "big")}
    for pos in range(4, len(data), 6):
        key = int.from_bytes(data[pos:pos + 2], "big")
        value = int.from_bytes(data[pos + 2:pos + 6], "big")
        if key in counters:
            raise ValueError(f"Duplicate statistics ID {key}")
        counters[key] = value
    return counters


STATISTICS_RANGES = ((100, 10), (110, 10), (3000, 10), (3077, 4))


def calculated_statistics(values: dict[int, int]) -> dict[str, int | float]:
    """Derived values require at least one actual reported source counter."""
    result: dict[str, int | float] = {}
    keys = {
        "coffee_total": (3000, 3077),
        "milk_coffee_total": (3001, 3003),
    }
    for name, ids in keys.items():
        present = [values[i] for i in ids if i in values]
        if present:
            result[name] = sum(present)
    for name, key in (
        ("descaling_count", 105),
        ("filter_change_count", 108),
        ("milk_cleaning_count", 111),
    ):
        if key in values:
            result[name] = values[key]
    if 106 in values:
        # Verified scale in the original integration.
        result["water_liters"] = round(values[106] / 2000.0, 2)
    return result
