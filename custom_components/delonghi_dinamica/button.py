"""Explicit user-initiated DeLonghi power-on button."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DinamicaPowerOn(coordinator, entry), DinamicaRecipeSaveUnavailable(coordinator, entry), DinamicaNameSaveProbe(coordinator, entry), DinamicaBLECacheMTUDiagnostic(coordinator, entry)])


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
    """Manual test for coffee, milk-duration, and strength Save. Experimental."""

    _attr_has_entity_name = True
    _attr_name = "Frei 1 – Rezeptwerte speichern (Test)"
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
            "scope": "Nur Sepp / Frei 1; Kaffee, Milchdauer und Stärke",
            "warning": "Rezeptwert-Speicherung wird per A6 kontrolliert; Namensänderung nicht unterstützt",
        })

    async def async_press(self):
        try:
            await self.coordinator.async_experimental_save_test_coffee()
        except Exception as exc:
            raise HomeAssistantError(f"Speichertest gescheitert: {exc}") from exc

class DinamicaNameSaveProbe(CoordinatorEntity, ButtonEntity):
    """A single explicit 0xAB name write, restricted to Sepp/Frei 1."""

    _attr_has_entity_name = True
    _attr_name = "Frei 1 – Getränkenamen speichern (Test)"
    _attr_icon = "mdi:form-textbox"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_test_recipe_name_save"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }

    @property
    def available(self):
        monitor = (self.coordinator.data or {}).get("monitor") or {}
        return (
            super().available
            and monitor.get("state_code") == 7
            and not monitor.get("dispensing", False)
            and (self.coordinator.data or {}).get("recipes", {}).get(1, {}).get(233) is not None
            and len((self.coordinator.data or {}).get("names", [])) == 6
        )

    @property
    def extra_state_attributes(self):
        return dict(getattr(self.coordinator, "last_name_save_result", {}) or {
            "status": "Nicht getestet",
            "scope": "Nur Sepp / Frei 1 (233), nur Name",
            "warning": "0xAB aus offizieller App rekonstruiert; noch kein Hardwaretest",
        })

    async def async_press(self):
        try:
            await self.coordinator.async_experimental_save_test_name()
        except Exception as exc:
            raise HomeAssistantError(f"Namens-Test fehlgeschlagen: {exc}") from exc


class DinamicaBLECacheMTUDiagnostic(CoordinatorEntity, ButtonEntity):
    """Explicit transport-only BLE cache reset and fresh MTU readback."""

    _attr_has_entity_name = True
    _attr_name = "Bluetooth Cache und MTU prüfen (Test)"
    _attr_icon = "mdi:bluetooth-settings"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_ble_cache_mtu_diagnostic"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }

    @property
    def extra_state_attributes(self):
        return dict(getattr(self.coordinator, "last_ble_diagnostic", {}) or {
            "status": "Noch nicht ausgeführt",
            "scope": "Nur Cache löschen, Verbindung erneuern und GATT-/MTU-Metadaten prüfen",
            "writes_recipe_or_name": False,
        })

    async def async_press(self):
        try:
            await self.coordinator.async_diagnose_ble_cache_mtu()
        except Exception as exc:
            raise HomeAssistantError(f"Bluetooth-Diagnose fehlgeschlagen: {exc}") from exc
