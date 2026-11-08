"""Explicit user-initiated DeLonghi power-on button."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DinamicaPowerOn(coordinator, entry), DinamicaRecipeSaveUnavailable(coordinator, entry)])


class DinamicaPowerOn(CoordinatorEntity, ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Maschine einschalten"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_power_on"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }

    async def async_press(self):
        await self.coordinator.async_power_on()


class DinamicaRecipeSaveUnavailable(CoordinatorEntity, ButtonEntity):
    """Visible but deliberately unavailable until save + name protocol is verified."""

    _attr_has_entity_name = True
    _attr_name = "Frei 1 – In Maschine speichern (noch gesperrt)"
    _attr_icon = "mdi:content-save-lock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_test_recipe_save"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi", "model": "Dinamica Plus",
        }

    @property
    def available(self):
        # The 0x83 save-mode data and 0xAB naming format are NOT yet validated
        # on the user's machine. Do not issue unsafe experimental BLE commands.
        return False

    async def async_press(self):
        raise HomeAssistantError(
            "Speichern ist noch gesperrt: Rezept- und Namens-Schreibprotokoll "
            "für ECAM370.95.T muss erst bestätigt werden."
        )
