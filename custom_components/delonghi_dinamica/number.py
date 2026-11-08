"""Offline-only test coffee amount. Does not send Bluetooth writes."""
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN
from .recipe_edit_draft import (
    COFFEE_MAX_ML, COFFEE_MIN_ML, TEST_PROFILE_ID, TEST_RECIPE_ID,
    plan_test_coffee,
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DinamicaTestCoffeeAmount(coordinator, entry)])


class DinamicaTestCoffeeAmount(CoordinatorEntity, NumberEntity):
    """Edit a local proposed coffee quantity, not the physical machine."""

    _attr_has_entity_name = True
    _attr_name = "Frei 1 – Kaffeemenge (nur Entwurf)"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = COFFEE_MIN_ML
    _attr_native_max_value = COFFEE_MAX_ML
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "mL"
    _attr_icon = "mdi:coffee"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_native_value = 150
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_test_coffee_draft_amount"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }

    @property
    def available(self):
        if not super().available:
            return False
        original = (
            (self.coordinator.data or {}).get("recipes", {})
            .get(TEST_PROFILE_ID, {}).get(TEST_RECIPE_ID)
        )
        if original is None:
            return False
        try:
            plan_test_coffee(original, int(self._attr_native_value))
        except ValueError:
            return False
        return True

    async def async_set_native_value(self, value):
        original = (
            (self.coordinator.data or {}).get("recipes", {})
            .get(TEST_PROFILE_ID, {}).get(TEST_RECIPE_ID)
        )
        if original is None:
            raise ValueError("Test recipe Sepp/Frei 1 not available")
        # Validate. No client connection and no BLE commands are invoked.
        plan_test_coffee(original, value)
        self._attr_native_value = value
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        original = (
            (self.coordinator.data or {}).get("recipes", {})
            .get(TEST_PROFILE_ID, {}).get(TEST_RECIPE_ID)
        )
        if original is None:
            return {"warning": "Originalrezept nicht auslesbar"}
        try:
            planned = plan_test_coffee(original, int(self._attr_native_value))
        except ValueError as exc:
            return {"warning": str(exc)}
        return {
            "profile_id": TEST_PROFILE_ID,
            "recipe_id": TEST_RECIPE_ID,
            "original_coffee_ml": planned.coffee_ml_before,
            "proposed_coffee_ml": planned.coffee_ml_after,
            "original_parameters": str(planned.original_parameters),
            "proposed_parameters": str(planned.proposed_parameters),
            "removed_milk_parameters": str(planned.removed_milk_parameters),
            "saved_to_machine": False,
            "note": "Nur lokaler Entwurf. Bluetooth-Schreibprotokoll noch nicht verifiziert.",
        }
