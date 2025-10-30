"""
Enphase Envoy Cloud Control – Integration setup
Version: 1.5.4
"""

from __future__ import annotations
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from .const import DOMAIN
from .coordinator import EnphaseCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enphase Envoy Cloud Control from a config entry."""
    _LOGGER.info("Setting up Enphase Envoy Cloud Control integration.")

    coordinator = EnphaseCoordinator(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Run initial refresh (non-blocking)
    await coordinator.async_config_entry_first_refresh()

    # Register manual service for scripts/automations
    async def async_force_refresh_service(call):
        """Manually trigger a cloud data refresh."""
        _LOGGER.debug("[Enphase] Manual force refresh service called.")
        try:
            await coordinator.async_request_refresh()
            _LOGGER.info("[Enphase] Cloud data refreshed via service.")
        except Exception as e:
            _LOGGER.error("[Enphase] Manual refresh failed: %s", e)

    hass.services.async_register(DOMAIN, "force_refresh", async_force_refresh_service)

    # Forward to all supported platforms (includes Force Cloud Refresh button)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("[Enphase] Forwarded platforms: %s", PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Enphase integration when entry is removed."""
    _LOGGER.info("Unloading Enphase Envoy Cloud Control integration.")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        _LOGGER.debug("[Enphase] Integration data cleared from memory.")

    return unload_ok
