"""Monitor (0x75/0x70) read-only status support."""
import binascii

STATE_NAMES = {
    0: "Aus",
    1: "Heizt auf",
    2: "Schaltet aus",
    3: "Heizt auf",
    4: "Entkalkung",
    5: "Dampfbezug",
    6: "Bereitet Getränk zu",
    7: "Bereit",
    8: "Spült",
    10: "Bereitet vor",
    11: "Heißwasser",
    12: "Reinigt Milchauslauf",
}

ALARM_NAMES = {
    0: "Wassertank leer", 1: "Kaffeesatzbehälter voll",
    2: "Entkalkung erforderlich",
    4: "Mahlgrad zu fein",
    6: "Service erforderlich", 7: "Temperatursensorfehler",
    11: "Abtropfschale leer", 12: "Hydraulikfehler",
}


def build_status_request() -> bytes:
    """Non-mutating request used by the earlier Delonghi BLE integration."""
    # 0x75/0x0F status query is a fixed command in the established integration.
    return bytes.fromhex("0D 05 75 0F DA 25")


def build_power_on() -> bytes:
    """Power-on request from the previous integration (no power-off counterpart)."""
    payload = bytes((0x0D, 0x07, 0x84, 0x0F, 0x02, 0x01))
    return payload + binascii.crc_hqx(payload, 0x1D0F).to_bytes(2, "big")


def parse_monitor(packet: bytes) -> dict:
    """Decode only known fields; don't infer power from BLE connectivity."""
    if len(packet) < 13 or packet[0] != 0xD0 or packet[1] + 1 != len(packet):
        raise ValueError("Invalid monitor frame length")
    if binascii.crc_hqx(packet[:-2], 0x1D0F) != int.from_bytes(packet[-2:], "big"):
        raise ValueError("Invalid monitor CRC")

    if packet[2] == 0x75 and packet[3] == 0x0F:
        if len(packet) < 19:
            raise ValueError("Monitor v2 frame incomplete")
        state = packet[9]
        alarms = packet[7] | packet[8] << 8 | packet[12] << 16 | packet[13] << 24
    elif packet[2] == 0x70 and packet[3] == 0x0F:
        if len(packet) < 13:
            raise ValueError("Monitor v1 frame incomplete")
        state = packet[8]
        alarms = packet[4] | packet[5] << 8
    else:
        raise ValueError("Not a supported monitor frame")

    warning_names = [
        ALARM_NAMES[i] for i in ALARM_NAMES
        if alarms & (1 << i)
    ]
    return {
        "is_on": state != 0,
        "state_code": state,
        "dispensing": state in (5, 6, 11),
        "progress_percent": packet[11] if packet[2] == 0x75 else None,
        "sub_status": packet[10] if packet[2] == 0x75 else packet[9],
        "state": STATE_NAMES.get(state, f"Status {state}"),
        "alarms": alarms,
        "warnings": warning_names,
        "raw_hex": packet.hex(" ").upper(),
    }
