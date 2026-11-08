"""DeLonghi Dinamica Plus – experimental read-only Home Assistant integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_MAC, DOMAIN
from .coordinator import DinamicaCoordinator

PLATFORMS = ["sensor", "select", "binary_sensor", "button", "number", "text"]



async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Hide old detail sensors during the one-time 0.1.8 upgrade.

    Hiding keeps sensor state/history and existing entity IDs intact. Explicit
    user-hidden entries are left alone. Migration runs once (v1 -> v2), so
    subsequent user decisions to unhide are respected.
    """
    if entry.version > 2:
        return False
    if entry.version == 1:
        registry = er.async_get(hass)
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id):
            if registered.domain != "sensor" or registered.platform != DOMAIN:
                continue
            # Only the three new selected-value sensors remain visible.
            # All 54 raw recipe sensors and 2 metadata sensors are tucked away.
            if registered.unique_id.endswith((
                "_selected_coffee", "_selected_milk", "_selected_strength"
            )):
                continue
            if registered.hidden_by is None:
                registry.async_update_entity(
                    registered.entity_id, hidden_by=er.RegistryEntryHider.INTEGRATION
                )
        hass.config_entries.async_update_entry(entry, version=2)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration; let HA handle retryable first-refresh errors."""
    coordinator = DinamicaCoordinator(hass, entry.data[CONF_MAC])
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        # Retired duplicate name-save test button: keep only one Save control.
        registry = er.async_get(hass)
        old_unique_id = f"{entry.data[CONF_MAC]}_test_recipe_name_save"
        old_id = registry.async_get_entity_id("button", DOMAIN, old_unique_id)
        if old_id is not None:
            registry.async_remove(old_id)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload entities and release stored coordinator."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
