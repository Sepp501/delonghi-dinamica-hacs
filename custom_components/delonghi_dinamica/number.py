"""Three draft fields for the manually triggered, readback-verified Save."""
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN
from .recipe_edit_draft import (
    COFFEE_MIN_ML, COFFEE_MAX_ML, TEST_PROFILE_ID, TEST_RECIPE_ID,
    plan_test_recipe, _valid_name,
)


def get_original(coordinator):
    """Recipe data for the selected drink in profile 1 (shared names)."""
    recipe_id = coordinator.selected_recipe_id
    profile_id = coordinator.selected_profile_id
    return ((coordinator.data or {}).get("recipes", {})
            .get(profile_id, {}).get(recipe_id))


def initialize_draft(coordinator):
    """Load selected slot from cached readback; switching discards old draft."""
    recipe_id = coordinator.selected_recipe_id
    profile_id = coordinator.selected_profile_id
    if (getattr(coordinator, "recipe_draft_profile_id", None) != profile_id
            or getattr(coordinator, "recipe_draft_recipe_id", None) != recipe_id
            or not hasattr(coordinator, "recipe_draft")):
        original = get_original(coordinator)
        names = (coordinator.data or {}).get("names", [])
        index = recipe_id - 230
        raw_name = (names[index].get("name", "")
                    if 0 <= index < len(names) and isinstance(names[index], dict)
                    else "")
        display_name = raw_name or f"Frei {recipe_id - 232}"
        coordinator.recipe_draft = {
            "coffee": original.coffee_ml if original and original.coffee_ml is not None else 150,
            "milk": original.milk_seconds if original and original.milk_seconds is not None else 0,
            "strength": original.strength if original and original.strength is not None else 3,
            "name": display_name,
            "name_initial": display_name,
            "raw_name_initial": raw_name,
            "pending": False,
        }
        coordinator.recipe_draft_recipe_id = recipe_id
        coordinator.recipe_draft_profile_id = profile_id
    return coordinator.recipe_draft


def validate_draft(coordinator, draft):
    """Validate local entry; only recipe 233 has a tested value-write path."""
    original = get_original(coordinator)
    if original is None:
        raise ValueError("Ausgewähltes Rezept derzeit nicht auslesbar")
    _valid_name(str(draft["name"]))
    if (coordinator.selected_recipe_id != TEST_RECIPE_ID
            or coordinator.selected_profile_id != TEST_PROFILE_ID):
        # Display values for all, but only proven 233/profile 1 is writable.
        return None
    return plan_test_recipe(
        original, int(draft["coffee"]), float(draft["milk"]),
        int(draft["strength"]), str(draft["name"]),
    )


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    initialize_draft(coordinator)
    async_add_entities([
        DinamicaDraftNumber(coordinator, entry, "coffee",
                            "Kaffeemenge (Entwurf)", COFFEE_MIN_ML, COFFEE_MAX_ML, 5, "mL"),
        DinamicaDraftNumber(coordinator, entry, "milk",
                            "Milchdauer (Entwurf)", 0, 90, 0.1, "s"),
        DinamicaDraftNumber(coordinator, entry, "strength",
                            "Stärke (Entwurf)", 1, 5, 1, None),
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
        # Keep the measured values visible for EVERY selected drink.
        return super().available and get_original(self.coordinator) is not None

    async def async_set_native_value(self, value):
        if (self.coordinator.selected_recipe_id != TEST_RECIPE_ID
                or self.coordinator.selected_profile_id != TEST_PROFILE_ID):
            raise ValueError(
                "Rezeptwerte sind aktuell nur für Profil 1 / Rezept 233 schreibbar; "
                "andere Getränke werden mit ihren echten Werten angezeigt"
            )
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
        if candidate is None:
            return {
                "saved_to_machine": False,
                "profile_id": self.coordinator.selected_profile_id,
                "recipe_id": self.coordinator.selected_recipe_id,
                "read_only_values": True,
                "warning": "Kaffeemenge, Milchdauer und Stärke werden ausgelesen; "
                           "Speichern dieser Werte bisher nur für Profil 1 / Rezept 233 bestätigt",
            }
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
                    "Der Name kann für alle sechs Slots gespeichert werden.",
        }
