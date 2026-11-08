"""Read-only machine power state from the DeLonghi status telegram."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN


WARNING_SENSORS = (
    ("water_empty", "Wassertank leer", 0),
    ("grounds_full", "Kaffeesatzbehälter voll", 1),
    ("descale_needed", "Entkalkung erforderlich", 2),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [DinamicaPowerState(coordinator, entry)]
    for key, name, bit in WARNING_SENSORS:
        entities.append(DinamicaMonitorFlag(coordinator, entry, key, name, bit))
    entities.append(DinamicaMonitorFlag(coordinator, entry, "dispensing", "Getränkezubereitung läuft", None))
    async_add_entities(entities)


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


class DinamicaMonitorFlag(CoordinatorEntity, BinarySensorEntity):
    """Read-only warning/dispensing from a valid 0x70/0x75 monitor frame."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, kind, label, alarm_bit):
        super().__init__(coordinator)
        self._kind = kind
        self._bit = alarm_bit
        self._attr_name = label
        if alarm_bit is not None:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        else:
            self._attr_device_class = BinarySensorDeviceClass.RUNNING
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_monitor_{kind}"
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
        if monitor is None:
            return None
        if self._bit is None:
            return bool(monitor.get("dispensing"))
        return bool(monitor["alarms"] & (1 << self._bit))

    @property
    def extra_state_attributes(self):
        monitor = (self.coordinator.data or {}).get("monitor")
        if self._kind == "dispensing" and monitor:
            return {"progress_percent": monitor.get("progress_percent")}
        return {}
