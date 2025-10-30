from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, DEFAULT_POLL_INTERVAL


class EnphaseOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Enphase Envoy Cloud Control."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the Enphase options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                "poll_interval",
                default=self.config_entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL)
            ): int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            description_placeholders={"interval": DEFAULT_POLL_INTERVAL},
        )
