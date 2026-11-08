"""Read-only sensors for DeLonghi Dinamica Plus."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN

# Confirmed against Coffee Link app quantities for the ECAM370.95.
# The remaining 0xAA entries (CUSTOM 4-6) are not yet identified.
CONFIRMED_RECIPE_IDS = frozenset({230, 231, 232})


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
    if recipe_id not in CONFIRMED_RECIPE_IDS:
        return None
    index = recipe_id - 230
    if index >= len(names):
        return None
    entry = names[index]
    if not isinstance(entry, dict):
        return None
    name = entry.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else None


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
    async_add_entities(entities)


class DinamicaSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, kind, label, recipe_key=None):
        super().__init__(coordinator)
        self._kind = kind
        self._recipe_key = recipe_key
        self._attr_name = label
        mac = entry.data[CONF_MAC]
        suffix = (
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

    @property
    def name(self):
        """Present live profile/recipe labels without changing entity IDs."""
        if self._kind in ("profiles", "names"):
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
        profile_id, recipe_id = self._recipe_key
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        field = {"recipe": "coffee_ml", "milk": "milk_seconds", "strength": "strength"}[self._kind]
        return recipe is not None and getattr(recipe, field) is not None

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return len(data.get("profiles", {}))
        if self._kind == "names":
            return len(data.get("names", []))
        profile_id, recipe_id = self._recipe_key
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        if recipe is None:
            return None
        field = {"recipe": "coffee_ml", "milk": "milk_seconds", "strength": "strength"}[self._kind]
        return getattr(recipe, field)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return {"profiles": display_profiles(data.get("profiles", {}))}
        if self._kind == "names":
            return {
                "entries": data.get("names", []),
                "profile_mapping_confirmed": False,
                "confirmed_recipe_ids": sorted(CONFIRMED_RECIPE_IDS),
            }
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
