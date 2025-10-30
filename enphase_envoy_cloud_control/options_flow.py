from __future__ import annotations
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 30
DEFAULT_LOGGING_LEVEL = "info"

class EnphaseOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Enphase Envoy Cloud Control options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            _LOGGER.info(
                "[Enphase] Options updated: interval=%s, log=%s",
                user_input["poll_interval"],
                user_input["logging_level"],
            )
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            "poll_interval", DEFAULT_POLL_INTERVAL
        )
        current_logging = self.config_entry.options.get(
            "logging_level", DEFAULT_LOGGING_LEVEL
        )

        schema = vol.Schema(
            {
                vol.Required(
                    "poll_interval", default=current_interval
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10,
                        max=600,
                        step=10,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    "logging_level", default=current_logging
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["debug", "info", "warning", "error"],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
