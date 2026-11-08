"""Editable local draft name for the selected custom drink slot."""
from homeassistant.components.text import TextEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN
from .number import initialize_draft, validate_draft


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([DinamicaDraftName(hass.data[DOMAIN][entry.entry_id], entry)])


class DinamicaDraftName(CoordinatorEntity, TextEntity):
    _attr_has_entity_name = True
    _attr_name = "Getränkename (Entwurf)"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min = 1
    _attr_native_max = 10
    _attr_icon = "mdi:form-textbox"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_test_coffee_draft_name"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi", "model": "Dinamica Plus",
        }

    @property
    def native_value(self):
        return initialize_draft(self.coordinator)["name"]

    async def async_set_value(self, value):
        draft = initialize_draft(self.coordinator)
        changed = {**draft, "name": value}
        validate_draft(self.coordinator, changed)
        draft.update(changed)
        draft["pending"] = False
        self.coordinator.async_update_listeners()
