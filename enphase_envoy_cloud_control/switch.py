from __future__ import annotations
import asyncio
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data.get("data", {}) if coordinator.data else {}
    switches = []

    for key in ["cfgControl", "dtgControl", "rbdControl"]:
        if key in data:
            switches.append(EnphaseModeSwitch(coordinator, key))

    async_add_entities(switches, True)


class EnphaseModeSwitch(CoordinatorEntity, SwitchEntity):
    """Switch representing an Enphase battery control mode."""

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self.short_mode = key.replace("Control", "")
        self._attr_name = f"Enphase {self.short_mode.upper()} Mode"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{self.short_mode.lower()}"

    # ------------------------------------------------------------------

    @property
    def is_on(self):
        """Return True if the control mode is enabled."""
        try:
            return self.coordinator.data["data"][self.key]["enabled"]
        except Exception:
            return False

    async def async_turn_on(self):
        """Enable the mode in Enphase Cloud."""
        _LOGGER.info("[Enphase] Turning ON %s", self.short_mode)
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.client.set_mode, self.key, True
        )
        # Wait 5 s for cloud propagation, then force refresh
        await asyncio.sleep(5)
        await self.coordinator.async_force_refresh()

    async def async_turn_off(self):
        """Disable the mode in Enphase Cloud."""
        _LOGGER.info("[Enphase] Turning OFF %s", self.short_mode)
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator.client.set_mode, self.key, False
        )
        await asyncio.sleep(5)
        await self.coordinator.async_force_refresh()

    # ------------------------------------------------------------------

    @property
    def device_info(self):
        """Attach to Enphase Envoy Cloud device."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }
