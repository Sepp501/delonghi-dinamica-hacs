"""Read-only user interface selectors for profile and stored drink recipe."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN
from .sensor import display_drink_name, display_profiles


def profile_options(data):
    names = display_profiles(data.get("profiles", {}))
    return [f"{profile_id} · {names.get(profile_id, f'Profil {profile_id}')}" for profile_id in (1, 2, 3, 4)]


def drink_options(data):
    return [
        f"{recipe_id} · {display_drink_name(data.get('names', []), recipe_id) or f'Frei {recipe_id - 232}'}"
        for recipe_id in range(230, 236)
    ]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        DinamicaSelect(coordinator, entry, "profile"),
        DinamicaSelect(coordinator, entry, "drink"),
    ])


class DinamicaSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, kind):
        super().__init__(coordinator)
        self._kind = kind
        self._attr_name = "Benutzerprofil auswählen" if kind == "profile" else "Getränk auswählen"
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_selected_{kind}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, mac)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "De'Longhi",
            "model": "Dinamica Plus",
        }

    @property
    def options(self):
        data = self.coordinator.data or {}
        return profile_options(data) if self._kind == "profile" else drink_options(data)

    @property
    def current_option(self):
        key = (
            self.coordinator.selected_profile_id if self._kind == "profile"
            else self.coordinator.selected_recipe_id
        )
        return next((option for option in self.options if option.startswith(f"{key} · ")), None)

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError(f"Invalid selection: {option!r}")
        item_id = int(option.split(" · ", 1)[0])
        if self._kind == "profile":
            self.coordinator.selected_profile_id = item_id
        else:
            self.coordinator.selected_recipe_id = item_id
        # Notify all coordinator-backed sensors without making another BLE request.
        self.coordinator.async_update_listeners()
