from __future__ import annotations
import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from .const import DOMAIN
from .enphase_client import EnphaseClient   #  add this import

_LOGGER = logging.getLogger(__name__)


class EnphaseCoordinator(DataUpdateCoordinator):
    """Central coordinator for Enphase Cloud data and state."""

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry

        #  FIX: construct EnphaseClient directly
        self.client = EnphaseClient(
            email=entry.data.get("email"),
            password=entry.data.get("password"),
            user_id=entry.data.get("user_id"),
            battery_id=entry.data.get("battery_id"),
        )

        self.last_refresh = None
        self.last_successful_poll = None

        super().__init__(
            hass,
            _LOGGER,
            name="Enphase Envoy Cloud Control Coordinator",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch latest data asynchronously."""
        try:
            _LOGGER.debug("[Coordinator] Fetching new data from Enphase Cloud")
            data = await self.hass.async_add_executor_job(self._fetch)
            self.last_refresh = dt_util.utcnow().isoformat()
            self.last_successful_poll = self.last_refresh
            return data
        except Exception as err:
            raise UpdateFailed(f"Error fetching Enphase data: {err}") from err

    def _fetch(self):
        """Blocking HTTP calls run in executor."""
        battery_data = self.client.battery_settings() or {}
        schedules = self.client.get_schedules() or {}
        inner_data = battery_data.get("data", battery_data)
        return {"data": inner_data, "schedules": schedules}

    async def async_force_refresh(self):
        """Force an immediate refresh (used by button/switch)."""
        _LOGGER.info("[Coordinator] Manual cloud refresh triggered")
        await self.async_request_refresh()
