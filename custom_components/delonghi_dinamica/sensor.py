"""Read-only sensors for DeLonghi Dinamica Plus."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN

# Confirmed against Coffee Link app quantities for the ECAM370.95.
# The remaining 0xAA entries (CUSTOM 4-6) are not yet identified.
CONFIRMED_RECIPE_IDS = frozenset({230, 231, 232})

STATISTICS = {
    "coffee_total": ("Kaffeegetränke gesamt", None),
    "milk_coffee_total": ("Milchkaffee gesamt", None),
    "water_liters": ("Wasserverbrauch gesamt", "L"),
    "descaling_count": ("Entkalkungen gesamt", None),
    "filter_change_count": ("Filterwechsel gesamt", None),
    "milk_cleaning_count": ("Milchsystem-Reinigungen gesamt", None),
    "tea_total": ("Tee gesamt", None),
    "chocolate_total": ("Schokolade gesamt", None),
    "cold_milk_total": ("Kalte Milch gesamt", None),
}


def display_profiles(raw_profiles):
    """Keep regular profile names but normalize the guest slot."""
    profiles = dict(raw_profiles)
    if 4 in profiles:
        # Profile 4 is the guest account on this machine. The BLE name
        # bytes are not a regular user name and can decode as garbage.
        profiles[4] = "Gast"
    return profiles


def display_drink_name(names, recipe_id):
    """Get a confirmed drink name from the current 0xAA name response."""
    if recipe_id not in range(230, 236):
        return None
    index = recipe_id - 230
    if index >= len(names):
        return f"Frei {recipe_id - 232}" if recipe_id > 232 else None
    entry = names[index]
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    if recipe_id > 232:
        # These slots have not been mapped against the app. Only display
        # generic CUSTOM placeholders as free; retain future custom names.
        if not name or name.upper() == f"CUSTOM {recipe_id - 229}":
            return f"Frei {recipe_id - 232}"
    return name or None


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        DinamicaSensor(coordinator, entry, "profiles", "Benutzerprofile"),
        DinamicaSensor(coordinator, entry, "names", "Getränkenamen"),
    ]
    for profile_id in (1, 2, 3):
        for recipe_id in range(230, 236):
            entities.append(
                DinamicaSensor(
                    coordinator, entry, "recipe",
                    f"Profil {profile_id} Rezept {recipe_id} Kaffee",
                    (profile_id, recipe_id),
                )
            )
            # Extra read-only entities use the same cached recipe response.
            for kind, label in (("milk", "Milchdauer"), ("strength", "Stärke")):
                entities.append(
                    DinamicaSensor(
                        coordinator, entry, kind,
                        f"Profil {profile_id} Rezept {recipe_id} {label}",
                        (profile_id, recipe_id),
                    )
                )
    for kind, label in (
        ("selected_coffee", "Ausgewähltes Getränk Kaffee"),
        ("selected_milk", "Ausgewähltes Getränk Milchdauer"),
        ("selected_strength", "Ausgewähltes Getränk Stärke"),
    ):
        entities.append(DinamicaSensor(coordinator, entry, kind, label))
    entities.append(DinamicaSensor(coordinator, entry, "machine_status", "Maschinenstatus"))
    for key, (label, _unit) in STATISTICS.items():
        entities.append(DinamicaSensor(coordinator, entry, "statistic", label, key))
    async_add_entities(entities)


class DinamicaSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, kind, label, recipe_key=None):
        super().__init__(coordinator)
        self._kind = kind
        # Only the 3 selected-value sensors appear on the device page.
        # Historical per-recipe sensors remain active for automations/history.
        self._attr_entity_registry_visible_default = kind.startswith("selected_") or kind == "statistic"
        self._recipe_key = recipe_key
        self._attr_name = label
        mac = entry.data[CONF_MAC]
        suffix = f"statistics_{recipe_key}" if kind == "statistic" else (
            f"{recipe_key[0]}_{recipe_key[1]}"
            if kind == "recipe" else
            f"{recipe_key[0]}_{recipe_key[1]}_{kind}"
            if recipe_key else kind
        )
        # Never change existing unique IDs: dashboards and automations depend on them.
        self._attr_unique_id = f"{mac}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }
        if kind == "recipe":
            self._attr_native_unit_of_measurement = "mL"
        elif kind == "milk":
            self._attr_native_unit_of_measurement = "s"
        elif kind == "selected_coffee":
            self._attr_native_unit_of_measurement = "mL"
        elif kind == "selected_milk":
            self._attr_native_unit_of_measurement = "s"
        elif kind == "statistic":
            self._attr_native_unit_of_measurement = STATISTICS[recipe_key][1]
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def name(self):
        """Present live profile/recipe labels without changing entity IDs."""
        if self._kind in ("profiles", "names", "machine_status", "statistic") or self._kind.startswith("selected_"):
            return self._attr_name
        data = self.coordinator.data or {}
        profile_id, recipe_id = self._recipe_key
        profile = display_profiles(data.get("profiles", {})).get(
            profile_id, f"Profil {profile_id}"
        )
        drink = display_drink_name(data.get("names", []), recipe_id)
        measurement = {"recipe": "Kaffee", "milk": "Milchdauer", "strength": "Stärke"}[self._kind]
        return f"{profile} {drink or f'Rezept {recipe_id}'} {measurement}"

    @property
    def available(self):
        if not super().available:
            return False
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return "profiles" in data
        if self._kind == "names":
            return "names" in data
        if self._kind == "machine_status":
            return data.get("monitor") is not None
        if self._kind == "statistic":
            return self._recipe_key in data.get("statistics", {})
        if self._kind.startswith("selected_"):
            profile_id = self.coordinator.selected_profile_id
            recipe_id = self.coordinator.selected_recipe_id
            field = {
                "selected_coffee": "coffee_ml",
                "selected_milk": "milk_seconds",
                "selected_strength": "strength",
            }[self._kind]
        else:
            profile_id, recipe_id = self._recipe_key
            field = {"recipe": "coffee_ml", "milk": "milk_seconds", "strength": "strength"}[self._kind]
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        return recipe is not None and getattr(recipe, field) is not None

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return len(data.get("profiles", {}))
        if self._kind == "names":
            return len(data.get("names", []))
        if self._kind == "machine_status":
            monitor = data.get("monitor")
            return monitor["state"] if monitor else None
        if self._kind == "statistic":
            return data.get("statistics", {}).get(self._recipe_key)
        if self._kind.startswith("selected_"):
            profile_id = self.coordinator.selected_profile_id
            recipe_id = self.coordinator.selected_recipe_id
            field = {
                "selected_coffee": "coffee_ml",
                "selected_milk": "milk_seconds",
                "selected_strength": "strength",
            }[self._kind]
        else:
            profile_id, recipe_id = self._recipe_key
            field = {"recipe": "coffee_ml", "milk": "milk_seconds", "strength": "strength"}[self._kind]
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        return getattr(recipe, field) if recipe else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return {"profiles": display_profiles(data.get("profiles", {}))}
        if self._kind == "machine_status":
            return dict(data.get("monitor") or {})
        if self._kind == "statistic":
            return {"source": "DeLonghi A2 statistics"}
        if self._kind == "names":
            return {
                "entries": data.get("names", []),
                "profile_mapping_confirmed": False,
                "confirmed_recipe_ids": sorted(CONFIRMED_RECIPE_IDS),
            }
        if self._kind.startswith("selected_"):
            profile_id = self.coordinator.selected_profile_id
            recipe_id = self.coordinator.selected_recipe_id
        else:
            profile_id, recipe_id = self._recipe_key
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        return {
            "profile_id": profile_id,
            "profile_name": display_profiles(data.get("profiles", {})).get(
                profile_id, f"Profil {profile_id}"
            ),
            "recipe_id": recipe_id,
            "drink_name": display_drink_name(data.get("names", []), recipe_id),
            "milk_seconds": recipe.milk_seconds if recipe else None,
            "strength": recipe.strength if recipe else None,
        }
