"""Explicit user-initiated DeLonghi power and recipe save controls."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DinamicaPowerOn(coordinator, entry), DinamicaRecipeSave(coordinator, entry)])


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


class DinamicaRecipeSave(CoordinatorEntity, ButtonEntity):
    """One manual Save for selected slot; validated changes only."""

    _attr_has_entity_name = True
    _attr_name = "Rezept speichern"
    _attr_entity_category = EntityCategory.CONFIG
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
            and (self.coordinator.data or {}).get("recipes", {}).get(1, {}).get(
                self.coordinator.selected_recipe_id) is not None
            and len((self.coordinator.data or {}).get("names", [])) == 6
        )

    @property
    def extra_state_attributes(self):
        return dict(getattr(self.coordinator, "last_save_result", {}) or {
            "status": "Noch keine Speicherung durchgeführt",
            "scope": "Sechs gemeinsame Rezepte; explizites Speichern mit Rücklesekontrolle",
            "warning": "Änderungen an Rezeptwerten nur bei bereiter Maschine speichern.",
        })

    async def async_press(self):
        try:
            await self.coordinator.async_save_selected_recipe()
        except Exception as exc:
            raise HomeAssistantError(f"Rezept speichern fehlgeschlagen: {exc}") from exc
