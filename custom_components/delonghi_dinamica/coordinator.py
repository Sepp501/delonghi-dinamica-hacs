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
from .monitor import build_power_on, build_status_request, parse_monitor
from .recipe_save_probe import make_save_probe, make_profile_select
from .recipe_name_write import build_name_write, get_test_name
from .number import initialize_draft
from .statistics import (
    STATISTICS_RANGES, build_statistics_request,
    calculated_statistics, parse_statistics_response,
)
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
        self._ble_lock = asyncio.Lock()
        # UI-only selection; never sent to the coffee machine.
        self.selected_profile_id = 1
        self.selected_recipe_id = 230

    async def _async_update_data(self):
        # Protect the ESPHome connection against overlapping writes and polls.
        async with self._ble_lock:
            return await self._async_poll_data()

    async def async_power_on(self):
        """Only send the power-on command when the HA button is pressed."""
        async with self._ble_lock:
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.mac, connectable=True,
            )
            if device is None:
                raise BleakError("Machine not found through Home Assistant Bluetooth")
            client = await establish_connection(
                client_class=BleakClient, device=device,
                name="DeLonghi Dinamica Plus", max_attempts=3,
            )
            try:
                await client.write_gatt_char(CHAR_UUID, build_power_on(), response=True)
            finally:
                await client.disconnect()
        # A successful write does not imply the machine is already ready.
        await self.async_request_refresh()

    async def async_experimental_save_test_coffee(self):
        """Explicit user-triggered, single-slot experimental Save, verified via A6.

        This updates only coffee amount, milk seconds and strength.
        The name-write format 0xAB is not known and MUST NOT be sent.
        """
        draft = dict(initialize_draft(self))
        probe_details = {
            "notifications_after_save": [], "packet_hex": None,
            "before_ml": None, "after_ml": None,
            "before_milk_seconds": None, "after_milk_seconds": None,
            "before_strength": None, "after_strength": None,
            "name_saved": False,
        }
        self.last_save_result = {
            "result": "In Bearbeitung", "target": "Sepp / Frei 1",
            "requested_coffee_ml": draft["coffee"], "verified": False,
        }
        self.async_update_listeners()
        try:
            async with self._ble_lock:
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.mac, connectable=True,
                )
                if device is None:
                    raise ValueError("Kaffeemaschine nicht über Bluetooth erreichbar")
                client = await establish_connection(
                    client_class=BleakClient, device=device,
                    name="DeLonghi Dinamica Plus", max_attempts=3,
                )
                queue = asyncio.Queue()
                buffer = bytearray()

                def notification(_sender, data):
                    buffer.extend(data)
                    while buffer:
                        if buffer[0] != 0xD0:
                            del buffer[0]
                            continue
                        if len(buffer) < 2:
                            return
                        size = buffer[1] + 1
                        if size < 6 or size > 255:
                            del buffer[0]
                            continue
                        if len(buffer) < size:
                            return
                        queue.put_nowait(bytes(buffer[:size]))
                        del buffer[:size]

                async def matched(command, opcode, timeout=8):
                    while not queue.empty():
                        queue.get_nowait()
                    await client.write_gatt_char(CHAR_UUID, command, response=True)
                    deadline = asyncio.get_running_loop().time() + timeout
                    while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
                        try:
                            packet = await asyncio.wait_for(queue.get(), remaining)
                        except asyncio.TimeoutError:
                            break
                        if valid(packet, opcode):
                            if opcode != 0xA6 or packet[4:6] == bytes((1, 233)):
                                return packet
                    raise TimeoutError(f"Keine passende Antwort auf 0x{opcode:02X}")

                try:
                    await client.start_notify(CHAR_UUID, notification)
                    # Require fresh status, not just the coordinator's old cache.
                    while not queue.empty():
                        queue.get_nowait()
                    await client.write_gatt_char(
                        CHAR_UUID, build_status_request(), response=True,
                    )
                    status = None
                    deadline = asyncio.get_running_loop().time() + 5
                    while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
                        try:
                            packet = await asyncio.wait_for(queue.get(), remaining)
                        except asyncio.TimeoutError:
                            break
                        if len(packet) > 3 and packet[2] in (0x70, 0x75):
                            try:
                                status = parse_monitor(packet)
                            except ValueError:
                                pass
                            if status:
                                break
                    if status is None or status["state_code"] != 7 or status["dispensing"]:
                        raise ValueError("Maschine muss eingeschaltet und bereit sein")

                    # Explicitly choose profile 1; HA's dropdown does NOT do this.
                    await client.write_gatt_char(
                        CHAR_UUID, make_profile_select(), response=True,
                    )
                    await asyncio.sleep(0.6)
                    before = parse_recipe(await matched(
                        recipe_request(1, 233), 0xA6
                    ))
                    payload = make_save_probe(before, draft)
                    probe_details["before_ml"] = before.coffee_ml
                    probe_details["before_milk_seconds"] = before.milk_seconds
                    probe_details["before_strength"] = before.strength
                    probe_details["packet_hex"] = payload.hex(" ").upper()

                    _LOGGER.warning(
                        "EXPERIMENTAL ECAM SAVE Sepp/Frei1 before=%s proposed_ml=%s "
                        "payload=%s",
                        before.coffee_ml, draft["coffee"], payload.hex(" "),
                    )
                    while not queue.empty():
                        queue.get_nowait()
                    await client.write_gatt_char(CHAR_UUID, payload, response=True)
                    # Gather unsolicited replies without treating them as success.
                    # They are kept for troubleshooting; A6 readback remains authoritative.
                    try:
                        while len(probe_details["notifications_after_save"]) < 15:
                            packet = await asyncio.wait_for(queue.get(), timeout=0.35)
                            probe_details["notifications_after_save"].append(
                                packet.hex(" ").upper()
                            )
                    except asyncio.TimeoutError:
                        pass
                    _LOGGER.warning(
                        "EXPERIMENTAL SAVE replies after 0x83: %s",
                        probe_details["notifications_after_save"],
                    )
                    # Save-mode acknowledgement is insufficient: verify readback.
                    await asyncio.sleep(0.65)
                    after = parse_recipe(await matched(
                        recipe_request(1, 233), 0xA6, timeout=10
                    ))
                    probe_details["after_ml"] = after.coffee_ml
                    probe_details["after_milk_seconds"] = after.milk_seconds
                    probe_details["after_strength"] = after.strength
                    requested_milk = float(draft["milk"])
                    milk_ok = (
                        (after.milk_seconds is None and requested_milk == 0)
                        or after.milk_seconds == requested_milk
                    )
                    if (
                        after.coffee_ml != int(draft["coffee"])
                        or not milk_ok
                        or after.strength != int(draft["strength"])
                    ):
                        raise ValueError(
                            "Speicherung nicht vollständig bestätigt: Soll=%s ml / %s s / Stärke %s; "
                            "Ist=%s ml / %s s / Stärke %s" %
                            (draft["coffee"], draft["milk"], draft["strength"],
                             after.coffee_ml, after.milk_seconds, after.strength)
                        )
                    self.last_save_result = {
                        "result": "Kaffee, Milchdauer und Stärke per A6 bestätigt",
                        "target": "Sepp / Frei 1", "before_ml": before.coffee_ml,
                        "after_ml": after.coffee_ml, "verified": True,
                        "name_saved": False, "milk_saved": True,
                        "strength_saved": True,
                        **probe_details,
                    }
                    self.recipe_draft["pending"] = False
                finally:
                    try:
                        await client.stop_notify(CHAR_UUID)
                    except BleakError:
                        pass
                    await client.disconnect()
            await self.async_request_refresh()
        except Exception as exc:
            self.last_save_result = {
                "result": "Test nicht bestätigt", "verified": False,
                "detail": str(exc),
                **probe_details,
            }
            _LOGGER.error("Experimental recipe save not confirmed: %s", exc)
            raise
        finally:
            self.async_update_listeners()

    async def async_experimental_save_test_name(self):
        """Manually save only the name of Sepp/Frei 1 with APK-derived 0xAB.

        Preserve the icon from a fresh 0xAA read, and accept success ONLY
        after a second 0xAA read gives exactly the requested name.
        """
        draft = dict(initialize_draft(self))
        new_name = str(draft["name"])
        report = {
            "result": "Namens-Test läuft", "verified": False,
            "target": "Sepp / Frei 1 (233)",
            "requested_name": new_name, "packet_hex": None,
            "notifications_after_write": [],
        }
        self.last_name_save_result = report
        self.async_update_listeners()
        try:
            async with self._ble_lock:
                device = bluetooth.async_ble_device_from_address(
                    self.hass, self.mac, connectable=True,
                )
                if device is None:
                    raise ValueError("Maschine nicht über Bluetooth erreichbar")
                client = await establish_connection(
                    client_class=BleakClient, device=device,
                    name="DeLonghi Dinamica Plus", max_attempts=3,
                )
                frames = asyncio.Queue()
                buf = bytearray()

                def notification(_sender, data):
                    buf.extend(data)
                    while buf:
                        if buf[0] != 0xD0:
                            del buf[0]
                            continue
                        if len(buf) < 2:
                            return
                        packet_size = buf[1] + 1
                        if not 6 <= packet_size <= 255:
                            del buf[0]
                            continue
                        if len(buf) < packet_size:
                            return
                        frames.put_nowait(bytes(buf[:packet_size]))
                        del buf[:packet_size]

                async def read_names():
                    while not frames.empty():
                        frames.get_nowait()
                    await client.write_gatt_char(
                        CHAR_UUID, name_request(), response=True,
                    )
                    deadline = asyncio.get_running_loop().time() + 10
                    while (time_left := deadline - asyncio.get_running_loop().time()) > 0:
                        try:
                            frame = await asyncio.wait_for(frames.get(), time_left)
                        except asyncio.TimeoutError:
                            break
                        if valid(frame, 0xAA):
                            return parse_names(frame)
                    raise TimeoutError("Keine gültige 0xAA-Namensantwort")

                try:
                    await client.start_notify(CHAR_UUID, notification)
                    # Fresh monitor status gates the unverified name write.
                    while not frames.empty():
                        frames.get_nowait()
                    await client.write_gatt_char(
                        CHAR_UUID, build_status_request(), response=True,
                    )
                    status = None
                    deadline = asyncio.get_running_loop().time() + 5
                    while (time_left := deadline - asyncio.get_running_loop().time()) > 0:
                        try:
                            frame = await asyncio.wait_for(frames.get(), time_left)
                        except asyncio.TimeoutError:
                            break
                        if len(frame) > 3 and frame[2] in (0x70, 0x75):
                            try:
                                status = parse_monitor(frame)
                            except ValueError:
                                continue
                            break
                    if status is None or status["state_code"] != 7 or status["dispensing"]:
                        raise ValueError("Maschine muss eingeschaltet und bereit sein")

                    await client.write_gatt_char(
                        CHAR_UUID, make_profile_select(), response=True,
                    )
                    await asyncio.sleep(0.6)
                    original_names = await read_names()
                    original = get_test_name(original_names)
                    report["previous_name"] = original["name"]
                    report["icon"] = original["icon"]
                    # Unconfigured custom slots can have an empty real name.
                    # "Frei 1" is only a Home Assistant display fallback.
                    # Never overwrite an unexpected existing custom name.
                    if original["name"] not in ("", "Frei 1", "CUSTOM 4"):
                        raise ValueError(
                            "Abbruch: unerwarteter gespeicherter Name im Zielslot: "
                            f"'{original['name']}'"
                        )
                    if new_name == original["name"]:
                        raise ValueError("Bitte einen neuen Getränkenamen eingeben")

                    payload = build_name_write(new_name, original["icon"])
                    report["packet_hex"] = payload.hex(" ").upper()
                    _LOGGER.warning(
                        "EXPERIMENTAL 0xAB NAME WRITE Sepp/Frei1: %s",
                        report["packet_hex"],
                    )
                    while not frames.empty():
                        frames.get_nowait()
                    await client.write_gatt_char(CHAR_UUID, payload, response=True)
                    try:
                        while len(report["notifications_after_write"]) < 12:
                            frame = await asyncio.wait_for(frames.get(), timeout=0.35)
                            report["notifications_after_write"].append(
                                frame.hex(" ").upper()
                            )
                    except asyncio.TimeoutError:
                        pass
                    await asyncio.sleep(0.7)
                    updated_names = await read_names()
                    new = get_test_name(updated_names)
                    report["actual_name"] = new["name"]
                    report["actual_icon"] = new["icon"]
                    if new["name"] != new_name or new["icon"] != original["icon"]:
                        raise ValueError(
                            "Namensspeicherung nicht bestätigt: "
                            f"Soll '{new_name}', Ist '{new['name']}' "
                            f"(Icon vorher {original['icon']}, nachher {new['icon']})"
                        )
                    report["verified"] = True
                    report["result"] = "Getränkename über 0xAA bestätigt"
                finally:
                    try:
                        await client.stop_notify(CHAR_UUID)
                    except BleakError:
                        pass
                    await client.disconnect()
            await self.async_request_refresh()
        except Exception as exc:
            report["result"] = "Namens-Test nicht bestätigt"
            report["detail"] = str(exc)
            _LOGGER.error("Experimental 0xAB name save failed: %s", exc)
            raise
        finally:
            self.async_update_listeners()

    async def _async_poll_data(self):
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.mac, connectable=True,
        )
        if device is None:
            raise UpdateFailed("Machine not found through Home Assistant Bluetooth")

        frames = asyncio.Queue()
        buffer = bytearray()
        result = {"profiles": {}, "names": [], "recipes": {}, "connected": False, "monitor": None, "statistics": {}, "statistics_raw": {}}

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
                packet = bytes(buffer[:length])
                if len(packet) > 3 and packet[2] in (0x70, 0x75):
                    try:
                        result["monitor"] = parse_monitor(packet)
                    except ValueError as exc:
                        _LOGGER.debug("Ignoring monitor notification: %s", exc)
                frames.put_nowait(packet)
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
                    # Status query is independent of the recipe polling.
                    try:
                        await client.write_gatt_char(
                            CHAR_UUID, build_status_request(), response=True
                        )
                        deadline = asyncio.get_running_loop().time() + 4
                        while result["monitor"] is None:
                            remaining = deadline - asyncio.get_running_loop().time()
                            if remaining <= 0:
                                break
                            try:
                                await asyncio.wait_for(frames.get(), timeout=remaining)
                            except asyncio.TimeoutError:
                                break
                    except (BleakError, OSError, asyncio.TimeoutError) as exc:
                        _LOGGER.debug("Monitor query unavailable: %s", exc)
                    # Statistics uses a separate 0xA2/0x0F response, not
                    # the 0xA4/0xAA/0xA6 recipe-response protocol.
                    # Fetch sparse ranges independently; a failed range
                    # must not erase counters decoded from other ranges.
                    counters = {}
                    for start, count in STATISTICS_RANGES:
                        try:
                            while not frames.empty():
                                frames.get_nowait()
                            await client.write_gatt_char(
                                CHAR_UUID, build_statistics_request(start, count),
                                response=True,
                            )
                            deadline = asyncio.get_running_loop().time() + 3
                            while True:
                                remaining = deadline - asyncio.get_running_loop().time()
                                if remaining <= 0:
                                    raise TimeoutError(f"No statistics reply for {start}")
                                packet = await asyncio.wait_for(frames.get(), remaining)
                                if len(packet) < 4 or packet[2] != 0xA2:
                                    continue
                                try:
                                    decoded = parse_statistics_response(packet, start)
                                except ValueError as exc:
                                    _LOGGER.debug("Invalid 0xA2 response for %s: %s", start, exc)
                                    continue
                                counters.update(decoded)
                                break
                        except (BleakError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
                            _LOGGER.debug("Statistics range %s unavailable: %s", start, exc)
                    result["statistics_raw"] = counters
                    result["statistics"] = calculated_statistics(counters)

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

        if not result["profiles"] and not result["names"] and not any(result["recipes"].values()) and result["monitor"] is None:
            raise UpdateFailed("No valid Dinamica responses received")
        return result
