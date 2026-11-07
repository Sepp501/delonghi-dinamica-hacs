import binascii


def build_recipe_name_request(start=0, end=2):
    """Erstellt eine BLE-Leseanfrage für Getränkenamen."""
    payload = bytes([
        0x0D, 0x07,
        0xAA, 0xF0,
        start, end,
    ])

    crc = binascii.crc_hqx(payload, 0x1D0F)
    return payload + crc.to_bytes(2, "big")


def decode_recipe_names(packet: bytes):
    """Liest Namen und Icon-IDs aus einer 0xAA-Antwort."""
    if len(packet) < 6 or packet[0] != 0xD0 or packet[2] != 0xAA:
        raise ValueError("Ungueltiges Rezeptnamen-Paket")

    if packet[1] + 1 != len(packet):
        raise ValueError("Ungueltige Paketlaenge")

    expected_crc = binascii.crc_hqx(packet[:-2], 0x1D0F)
    received_crc = int.from_bytes(packet[-2:], "big")

    if expected_crc != received_crc:
        raise ValueError("CRC ungueltig")

    data = packet[4:-2]

    if len(data) % 21:
        raise ValueError("Unerwartete Laenge der Namensdaten")

    names = []

    for offset in range(0, len(data), 21):
        entry = data[offset:offset + 21]

        names.append({
            "name": entry[:20].decode("utf-16-be").rstrip("\x00"),
            "icon": entry[20],
        })

    return names