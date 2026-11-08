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
    """Manual test for the coffee-quantity-only Save mode. Experimental."""

    _attr_has_entity_name = True
    _attr_name = "Frei 1 – Kaffeemenge testen (experimentell)"
    _attr_icon = "mdi:content-save-alert"

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
        monitor = (self.coordinator.data or {}).get("monitor") or {}
        return (
            super().available
            and monitor.get("state_code") == 7
            and not monitor.get("dispensing", False)
            and (self.coordinator.data or {}).get("recipes", {}).get(1, {}).get(233) is not None
        )

    @property
    def extra_state_attributes(self):
        return dict(getattr(self.coordinator, "last_save_result", {}) or {
            "status": "Noch kein Test durchgeführt",
            "scope": "Nur Sepp / Frei 1; Kaffeemenge",
            "warning": "Experimenteller Speicherbefehl; eine ungewollte Zubereitung ist nicht ausgeschlossen",
        })

    async def async_press(self):
        try:
            await self.coordinator.async_experimental_save_test_coffee()
        except Exception as exc:
            raise HomeAssistantError(f"Speichertest gescheitert: {exc}") from exc
