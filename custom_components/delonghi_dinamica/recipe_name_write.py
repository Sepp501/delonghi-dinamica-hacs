"""DeLonghi Coffee Link 4.9.6 APK-derived single-name 0xAB Save.

Recovered from classes2.dex:
  Lj6/d;->f0(II[Ljava/lang/String;[I)[B
  Lit/delonghi/service/DeLonghiWifiConnectService;->f0(ILjava/lang/String;I)V
For a recipe ID, the service passes (id-229, id-229, [name], [icon]).
Each name is ten UTF-16BE code units (20 bytes), then its existing icon.
The packet includes a standard DeLonghi CRC-16 (CCITT init 0x1D0F).
This code does not transmit: the coordinator is the only write path.
"""
import binascii

from .recipe_edit_draft import TEST_PROFILE_ID, TEST_RECIPE_ID, _valid_name


def build_name_write(name: str, icon: int, profile_id: int = 1,
                     recipe_id: int = 233) -> bytes:
    """Build ONLY the Sepp/Frei 1 single-name write packet."""
    if (profile_id, recipe_id) != (TEST_PROFILE_ID, TEST_RECIPE_ID):
        raise ValueError("Namens-Test nur für Sepp / Frei 1 erlaubt")
    name = _valid_name(name)
    if not isinstance(icon, int) or isinstance(icon, bool) or not 0 <= icon <= 255:
        raise ValueError("Ungültige Icon-ID")
    # EXPERIMENT ONLY: 04 04 was transmitted and had no visible effect.
    # Try 03 03 once, with explicit user permission to affect another custom slot.
    slot = recipe_id - 230
    utf16 = name.encode("utf-16-be")
    if len(utf16) > 20:
        raise ValueError("Name überschreitet zehn UTF-16-Codeeinheiten")
    padded = utf16.ljust(20, b"\x00")
    # Experimental 29 bytes: 0D 1C AB F0 03 03 [name:20] [icon:1] [CRC:2].
    body = bytes((0xAB, 0xF0, slot, slot)) + padded + bytes((icon,))
    prefix = bytes((0x0D, len(body) + 3)) + body
    packet = prefix + binascii.crc_hqx(prefix, 0x1D0F).to_bytes(2, "big")
    if len(packet) != 29:
        raise ValueError("Unexpected name-write packet length")
    return packet


def get_test_name(names: list[dict]) -> dict:
    """Select the fourth of six custom-name slots (230..235)."""
    index = TEST_RECIPE_ID - 230
    if len(names) != 6:
        raise ValueError(f"Erwartet sechs benutzerdefinierte Namen, erhalten: {len(names)}")
    item = names[index]
    if not isinstance(item, dict) or not isinstance(item.get("name"), str):
        raise ValueError("Namenseintrag unvollständig")
    if not isinstance(item.get("icon"), int):
        raise ValueError("Icon des Testrezepts nicht lesbar")
    return item
