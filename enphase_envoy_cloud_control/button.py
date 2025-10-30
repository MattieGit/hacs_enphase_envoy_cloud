from __future__ import annotations
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Enphase Force Cloud Refresh button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnphaseForceCloudRefreshButton(coordinator)], True)

class EnphaseForceCloudRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to manually force data refresh from the cloud."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Force Cloud Refresh"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_force_refresh"
        self._attr_icon = "mdi:refresh"

    @property
    def available(self) -> bool:
        return True  # Always available

    async def async_press(self):
        """Handle button press."""
        _LOGGER.info("[Enphase] Force Cloud Refresh button pressed.")
        try:
            await self.coordinator.async_request_refresh()
            _LOGGER.info("[Enphase] Data refresh completed successfully.")
        except Exception as e:
            _LOGGER.error("[Enphase] Data refresh failed: %s", e)

    @property
    def device_info(self):
        """Attach this button to the Enphase device."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }
