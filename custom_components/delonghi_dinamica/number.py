"""Three draft fields for the manually triggered, readback-verified Save."""
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN
from .recipe_edit_draft import (
    COFFEE_MIN_ML, COFFEE_MAX_ML, TEST_PROFILE_ID, TEST_RECIPE_ID,
    plan_test_recipe,
)


def get_original(coordinator):
    return ((coordinator.data or {}).get("recipes", {})
            .get(TEST_PROFILE_ID, {}).get(TEST_RECIPE_ID))


def initialize_draft(coordinator):
    if not hasattr(coordinator, "recipe_draft"):
        original = get_original(coordinator)
        coordinator.recipe_draft = {
            "coffee": original.coffee_ml if original and original.coffee_ml else 150,
            "milk": original.milk_seconds if original and original.milk_seconds is not None else 0,
            "strength": original.strength if original and original.strength else 3,
            "name": "Frei 1",
            "pending": False,
        }
    return coordinator.recipe_draft


def validate_draft(coordinator, draft):
    original = get_original(coordinator)
    if original is None:
        raise ValueError("Rezept Sepp / Frei 1 derzeit nicht auslesbar")
    return plan_test_recipe(
        original, int(draft["coffee"]), float(draft["milk"]),
        int(draft["strength"]), str(draft["name"]),
    )


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    initialize_draft(coordinator)
    async_add_entities([
        DinamicaDraftNumber(coordinator, entry, "coffee",
                            "Frei 1 – Kaffeemenge (nur Entwurf)", COFFEE_MIN_ML, COFFEE_MAX_ML, 5, "mL"),
        DinamicaDraftNumber(coordinator, entry, "milk",
                            "Frei 1 – Milchdauer (nur Entwurf)", 0, 90, 0.1, "s"),
        DinamicaDraftNumber(coordinator, entry, "strength",
                            "Frei 1 – Stärke (nur Entwurf)", 1, 5, 1, None),
    ])


class DinamicaDraftNumber(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:coffee"

    def __init__(self, coordinator, entry, kind, label, minimum, maximum, step, unit):
        super().__init__(coordinator)
        self._kind = kind
        self._attr_name = label
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        mac = entry.data[CONF_MAC]
        # Preserve the previous entity ID and history for coffee quantity.
        suffix = "test_coffee_draft_amount" if kind == "coffee" else f"test_coffee_draft_{kind}"
        self._attr_unique_id = f"{mac}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)}, "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi", "model": "Dinamica Plus",
        }

    @property
    def native_value(self):
        return initialize_draft(self.coordinator)[self._kind]

    @property
    def available(self):
        return super().available and get_original(self.coordinator) is not None

    async def async_set_native_value(self, value):
        draft = initialize_draft(self.coordinator)
        if not self._attr_native_min_value <= value <= self._attr_native_max_value:
            raise ValueError("Value out of range")
        if self._kind in ("coffee", "strength") and not float(value).is_integer():
            raise ValueError("Whole numbers required")
        value = round(float(value), 1) if self._kind == "milk" else int(value)
        changed = {**draft, self._kind: value}
        validate_draft(self.coordinator, changed)
        draft.update(changed)
        draft["pending"] = False
        self.coordinator.async_update_listeners()

    @property
    def extra_state_attributes(self):
        draft = initialize_draft(self.coordinator)
        original = get_original(self.coordinator)
        if original is None:
            return {"saved_to_machine": False, "warning": "Original nicht lesbar"}
        try:
            candidate = validate_draft(self.coordinator, draft)
        except ValueError as exc:
            return {"saved_to_machine": False, "warning": str(exc)}
        return {
            "profile_id": TEST_PROFILE_ID, "recipe_id": TEST_RECIPE_ID,
            "original_coffee_ml": candidate.coffee_ml_before,
            "proposed_coffee_ml": candidate.coffee_ml_after,
            "proposed_milk_seconds": candidate.milk_seconds_after,
            "proposed_strength": candidate.strength_after,
            "proposed_name": candidate.name_after,
            "original_parameters": str(candidate.original_parameters),
            "proposed_parameters": str(candidate.proposed_parameters),
            "saved_to_machine": bool(
                getattr(self.coordinator, "last_save_result", {}).get("verified")
                and candidate.coffee_ml_after == original.coffee_ml
                and candidate.milk_seconds_after == (original.milk_seconds or 0)
                and candidate.strength_after == original.strength
            ),
            "save_requested": draft.get("pending", False),
            "note": "Änderungen erst nach manuellem Speichern und A6-Rücklesung aktiv. "
                    "Der Name wird noch nicht zur Maschine übertragen.",
        }
