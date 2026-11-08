"""Manual MAC setup for DeLonghi Dinamica Plus (Bluetooth discovery later)."""

import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import CONF_MAC, DEFAULT_NAME, DOMAIN

_MAC_RE = re.compile(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}")


class DinamicaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a machine by Bluetooth MAC address."""

    VERSION = 2

    async def async_step_user(self, user_input=None):
        """Show manual setup; no BLE connection during form validation."""
        errors = {}
        if user_input is not None:
            mac = str(user_input[CONF_MAC]).strip().upper().replace("-", ":")
            if _MAC_RE.fullmatch(mac) is None:
                errors["base"] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                name = str(user_input.get(CONF_NAME, DEFAULT_NAME)).strip() or DEFAULT_NAME
                return self.async_create_entry(title=name, data={CONF_MAC: mac})

        schema = vol.Schema({
            vol.Required(CONF_MAC): str,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
