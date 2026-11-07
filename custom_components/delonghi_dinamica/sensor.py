"""Read-only sensors for DeLonghi Dinamica Plus."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import CONF_MAC, DEFAULT_NAME, DOMAIN


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
    async_add_entities(entities)


class DinamicaSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, kind, label, recipe_key=None):
        super().__init__(coordinator)
        self._kind = kind
        self._recipe_key = recipe_key
        self._attr_name = label
        mac = entry.data[CONF_MAC]
        suffix = f"{recipe_key[0]}_{recipe_key[1]}" if recipe_key else kind
        self._attr_unique_id = f"{mac}_{suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }
        if kind == "recipe":
            self._attr_native_unit_of_measurement = "mL"

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
        return recipe is not None and recipe.coffee_ml is not None

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return len(data.get("profiles", {}))
        if self._kind == "names":
            return len(data.get("names", []))
        profile_id, recipe_id = self._recipe_key
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        return recipe.coffee_ml if recipe else None

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        if self._kind == "profiles":
            return {"profiles": data.get("profiles", {})}
        if self._kind == "names":
            return {
                "entries": data.get("names", []),
                "profile_mapping_confirmed": False,
            }
        profile_id, recipe_id = self._recipe_key
        recipe = data.get("recipes", {}).get(profile_id, {}).get(recipe_id)
        return {
            "profile_id": profile_id,
            "recipe_id": recipe_id,
            "milk_seconds": recipe.milk_seconds if recipe else None,
            "strength": recipe.strength if recipe else None,
        }
