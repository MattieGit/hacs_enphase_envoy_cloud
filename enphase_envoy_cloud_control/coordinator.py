from __future__ import annotations
from datetime import timedelta, datetime, timezone
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import LOGGER, DEFAULT_POLL_INTERVAL
from .enphase_client import EnphaseClient

_LOGGER = LOGGER


class EnphaseCoordinator(DataUpdateCoordinator):
    """Manages periodic updates from the Enphase Cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.client = EnphaseClient(
            email=entry.data.get("email"),
            password=entry.data.get("password"),
            user_id=entry.data.get("user_id"),
            battery_id=entry.data.get("battery_id"),
        )

        # ✅ Custom polling interval (default 30s)
        poll_interval = entry.options.get("poll_interval", DEFAULT_POLL_INTERVAL)
        self.update_interval = timedelta(seconds=poll_interval)
        _LOGGER.info(f"[Enphase] Polling interval set to {poll_interval}s")

        self.last_refresh = None
        self.last_successful_poll = None

        super().__init__(
            hass,
            _LOGGER,
            name="Enphase Envoy Cloud Control Coordinator",
            update_interval=self.update_interval,
        )

    async def _async_update_data(self):
        """Fetch latest data from Enphase Cloud."""
        try:
            _LOGGER.debug("[Enphase] Starting scheduled data update.")
            data = await self.hass.async_add_executor_job(self._fetch)
            self.last_successful_poll = datetime.now(timezone.utc)
            self.last_refresh = self.last_successful_poll.isoformat()
            return data
        except Exception as err:
            _LOGGER.error("[Enphase] Error updating data: %s", err)
            raise UpdateFailed(err)

    def _fetch(self):
        """Synchronous fetch — runs inside executor."""
        try:
            battery_data = self.client.battery_settings() or {}
            schedules = self.client.get_schedules() or {}

            # Persist the last schedule payload for entities that reference it
            # outside of the coordinator data structure (legacy behaviour).
            setattr(self.client, "_last_schedules", schedules)

            merged = {
                "data": battery_data.get("data", battery_data),
                "schedules": schedules.get("data", schedules),
            }
            _LOGGER.debug("[Enphase] Data fetch complete. Keys: %s", list(merged.keys()))
            return merged
        except Exception as e:
            _LOGGER.warning("[Enphase] Coordinator fetch failed: %s", e)
            raise

    async def async_force_refresh(self):
        """Manually triggered refresh (Force Cloud Refresh button)."""
        _LOGGER.info("[Enphase] Manual cloud refresh requested.")
        await self.async_refresh()
