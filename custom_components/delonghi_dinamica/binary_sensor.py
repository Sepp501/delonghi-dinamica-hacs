"""Read-only machine power state from the DeLonghi status telegram."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DinamicaPowerState(coordinator, entry)])


class DinamicaPowerState(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Maschine eingeschaltet"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_machine_power_state"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }

    @property
    def available(self):
        return super().available and (self.coordinator.data or {}).get("monitor") is not None

    @property
    def is_on(self):
        monitor = (self.coordinator.data or {}).get("monitor")
        return monitor["is_on"] if monitor else None
