"""Read-only Dinamica polling through Home Assistant Bluetooth.

Development preview: do not enable alongside another active BLE client for
this coffee machine. No brewing or configuration writes are performed.
"""
import asyncio
import logging
from datetime import timedelta

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CHAR_UUID, SCAN_INTERVAL
from .protocol import (
    name_request, parse_names, parse_profiles, parse_recipe,
    profile_request, recipe_request, valid,
)

_LOGGER = logging.getLogger(__name__)


class DinamicaCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, mac):
        super().__init__(
            hass, _LOGGER, name="DeLonghi Dinamica",
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.mac = mac

    async def _async_update_data(self):
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.mac, connectable=True,
        )
        if device is None:
            raise UpdateFailed("Machine not found through Home Assistant Bluetooth")

        frames = asyncio.Queue()
        buffer = bytearray()

        def notification(_sender, data):
            buffer.extend(data)
            while buffer:
                if buffer[0] != 0xD0:
                    del buffer[0]
                    continue
                if len(buffer) < 2:
                    return
                length = buffer[1] + 1
                if not 6 <= length <= 255:
                    del buffer[0]
                    continue
                if len(buffer) < length:
                    return
                frames.put_nowait(bytes(buffer[:length]))
                del buffer[:length]

        async def request(client, command, opcode, profile=None, recipe=None):
            while not frames.empty():
                frames.get_nowait()
            await client.write_gatt_char(CHAR_UUID, command, response=True)
            deadline = asyncio.get_running_loop().time() + 10
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise TimeoutError(f"No reply for 0x{opcode:02X}")
                packet = await asyncio.wait_for(frames.get(), timeout=remaining)
                if not valid(packet, opcode):
                    continue
                if profile is not None and (
                    len(packet) < 8 or packet[4] != profile or packet[5] != recipe
                ):
                    continue
                return packet

        result = {"profiles": {}, "names": [], "recipes": {}, "connected": False}
        try:
            client = await establish_connection(
                client_class=BleakClient,
                device=device,
                name="DeLonghi Dinamica Plus",
                max_attempts=3,
            )
            try:
                await client.start_notify(CHAR_UUID, notification)
                try:
                    # These are independent read-only operations. A failure in
                    # one must not hide successful responses from the others.
                    try:
                        packet = await request(client, profile_request(), 0xA4)
                        result["profiles"] = parse_profiles(packet)
                    except (TimeoutError, ValueError) as exc:
                        _LOGGER.warning("Profile read failed: %s", exc)

                    try:
                        packet = await request(client, name_request(), 0xAA)
                        result["names"] = parse_names(packet)
                    except (TimeoutError, ValueError) as exc:
                        _LOGGER.warning("Drink name read failed: %s", exc)

                    for profile in (1, 2, 3):
                        result["recipes"][profile] = {}
                        for recipe_id in range(230, 236):
                            try:
                                packet = await request(
                                    client, recipe_request(profile, recipe_id),
                                    0xA6, profile, recipe_id,
                                )
                                result["recipes"][profile][recipe_id] = parse_recipe(packet)
                            except (TimeoutError, ValueError) as exc:
                                _LOGGER.warning(
                                    "Recipe %s / profile %s unavailable: %s",
                                    recipe_id, profile, exc,
                                )
                finally:
                    try:
                        await client.stop_notify(CHAR_UUID)
                    except BleakError as exc:
                        _LOGGER.debug("Could not stop notifications: %s", exc)
                # Connected means the read session succeeded, not that a
                # permanent BLE connection is being held between updates.
                result["connected"] = True
            finally:
                await client.disconnect()
        except (BleakError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            raise UpdateFailed(f"Bluetooth communication failed: {exc}") from exc

        if not result["profiles"] and not result["names"] and not any(result["recipes"].values()):
            raise UpdateFailed("No valid Dinamica responses received")
        return result
