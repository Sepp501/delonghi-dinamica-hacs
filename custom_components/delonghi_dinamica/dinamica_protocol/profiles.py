"""Read-only DeLonghi Dinamica Plus profile protocol."""

import binascii

from .recipes import packet_crc_ok


def build_profile_read(profile_count: int) -> bytes:
    """Build a 0xA4 request for profile names."""

    if not 1 <= profile_count <= 255:
        raise ValueError("Invalid profile count")

    payload = bytes([
        0x0D, 0x07,
        0xA4, 0xF0,
        0x01, profile_count,
    ])

    crc = binascii.crc_hqx(payload, 0x1D0F)
    return payload + crc.to_bytes(2, "big")


def decode_profile_response(
    packet: bytes,
    profile_count: int,
) -> dict[int, str]:
    """Decode profile names from a 0xA4 response."""

    if len(packet) < 6:
        raise ValueError("Profile response too short")

    if packet[0] != 0xD0:
        raise ValueError("Invalid response header")

    if packet[1] + 1 != len(packet):
        raise ValueError("Invalid response length")

    if packet[2:4] != bytes([0xA4, 0xF0]):
        raise ValueError("Not an A4 profile response")

    if not packet_crc_ok(packet):
        raise ValueError("Invalid CRC")

    data = packet[4:-2]
    profiles = {}

    for index in range(profile_count):
        offset = index * 21

        if offset + 21 > len(data):
            break

        raw = data[offset:offset + 20]

        name = (
            raw.decode("utf-16-be", errors="replace")
            .split("\x00", 1)[0]
            .strip()
        )

        if name:
            profiles[index + 1] = name

    return profiles