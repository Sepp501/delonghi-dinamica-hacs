"""Compatibility facade for the validated, bundled read-only protocol library.

Keep protocol parsing in dinamica_protocol; coordinator imports remain stable.
"""
from .dinamica_protocol.recipes import (
    Recipe,
    build_recipe_read,
    decode_recipe_response,
    packet_crc_ok,
)
from .dinamica_protocol.names import build_recipe_name_request, decode_recipe_names
from .dinamica_protocol.profiles import build_profile_read, decode_profile_response


def profile_request(count: int = 4) -> bytes:
    return build_profile_read(count)


def name_request() -> bytes:
    return build_recipe_name_request(0, 2)


def recipe_request(profile: int, recipe: int) -> bytes:
    return build_recipe_read(profile, recipe)


def valid(packet: bytes, opcode: int) -> bool:
    return (
        len(packet) >= 6
        and packet[0] == 0xD0
        and packet[1] + 1 == len(packet)
        and packet[2:4] == bytes((opcode, 0xF0))
        and packet_crc_ok(packet)
    )


def parse_profiles(packet: bytes, count: int = 4) -> dict[int, str]:
    return decode_profile_response(packet, count)


def parse_names(packet: bytes) -> list[dict]:
    return decode_recipe_names(packet)


def parse_recipe(packet: bytes) -> Recipe:
    return decode_recipe_response(packet)
