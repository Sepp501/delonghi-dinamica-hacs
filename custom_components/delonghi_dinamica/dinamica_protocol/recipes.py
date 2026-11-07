"""Pure Python, read-only DeLonghi Dinamica Plus recipe protocol.

No Windows, ESPHome, Bleak or Home Assistant imports.
"""
from dataclasses import dataclass
import binascii


@dataclass(frozen=True)
class Recipe:
    profile_id: int
    recipe_id: int
    coffee_ml: int | None
    milk_seconds: float | None
    strength: int | None
    parameters: tuple[tuple[int, int], ...]
    raw_hex: str


def packet_crc_ok(packet: bytes) -> bool:
    return len(packet) >= 4 and binascii.crc_hqx(packet[:-2], 0x1D0F) == int.from_bytes(packet[-2:], 'big')


def build_recipe_read(profile_id: int, recipe_id: int) -> bytes:
    if not 0 <= profile_id <= 255 or not 0 <= recipe_id <= 255:
        raise ValueError('Profile and recipe IDs must fit in one byte')
    prefix = bytes([0x0D, 0x07, 0xA6, 0xF0, profile_id, recipe_id])
    return prefix + binascii.crc_hqx(prefix, 0x1D0F).to_bytes(2, 'big')


def decode_recipe_response(packet: bytes) -> Recipe:
    if len(packet) < 8 or packet[0] != 0xD0 or packet[1] + 1 != len(packet):
        raise ValueError('Invalid frame or length')
    if not packet_crc_ok(packet):
        raise ValueError('Invalid CRC')
    if packet[2:4] != bytes([0xA6, 0xF0]):
        raise ValueError('Not an A6 recipe response')
    # Observed 0xA6 parameters. Known tags have distinct lengths.
    # Unrecognized tags are NOT guessed; keep raw bytes for further research.
    data = packet[6:-2]
    widths = {0x01: 2, 0x09: 2, 0x02: 1, 0x0C: 1, 0x1B: 1, 0x19: 1, 0x1C: 1}
    params = []
    pos = 0
    while pos < len(data):
        tag = data[pos]
        if tag not in widths or pos + 1 + widths[tag] > len(data):
            raise ValueError(f'Unknown or incomplete parameter at offset {pos}: {data[pos:].hex(" ")}')
        width = widths[tag]
        value = int.from_bytes(data[pos+1:pos+1+width], 'big')
        params.append((tag, value))
        pos += width + 1
    values = dict(params)
    return Recipe(
        profile_id=packet[4], recipe_id=packet[5],
        coffee_ml=values.get(0x01),
        milk_seconds=(values[0x09] / 10) if 0x09 in values else None,
        strength=values.get(0x02),
        parameters=tuple(params), raw_hex=packet.hex(' ').upper(),
    )
