from __future__ import annotations
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Enphase Force Cloud Refresh button."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            EnphaseForceCloudRefreshButton(coordinator),
            EnphaseAddScheduleButton(coordinator),
            EnphaseDeleteScheduleButton(coordinator),
        ],
        True,
    )

class EnphaseForceCloudRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to manually force data refresh from the cloud."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "Force Cloud Refresh"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_force_refresh"
        self._attr_icon = "mdi:refresh"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def available(self) -> bool:
        return True  # Always available

    async def async_press(self):
        """Handle button press."""
        _LOGGER.info("[Enphase] Force Cloud Refresh button pressed.")
        try:
            await self.coordinator.async_force_refresh()
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


class EnphaseAddScheduleButton(CoordinatorEntity, ButtonEntity):
    """Button that opens the schedule creation dialog."""

    _attr_name = "Add Schedule"
    _attr_icon = "mdi:calendar-plus"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_add_schedule"

    async def async_press(self) -> None:
        """Launch the options flow for adding a schedule."""
        _LOGGER.debug("[Enphase] Add Schedule button pressed.")
        try:
            flow = await self.coordinator.hass.config_entries.options.async_create_flow(
                self.coordinator.entry.entry_id,
                context={"source": "schedule_add_button"},
            )
        except Exception as exc:
            _LOGGER.exception(
                "[Enphase] Failed to start add schedule options flow: %s",
                exc,
            )
            return
        _LOGGER.debug(
            "[Enphase] Add schedule options flow created: handler=%s type=%s",
            flow.handler,
            type(flow).__name__,
        )

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }


class EnphaseDeleteScheduleButton(CoordinatorEntity, ButtonEntity):
    """Button that opens the schedule deletion dialog."""

    _attr_name = "Delete Schedule"
    _attr_icon = "mdi:calendar-remove"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_delete_schedule"

    async def async_press(self) -> None:
        """Launch the options flow for deleting a schedule."""
        _LOGGER.debug("[Enphase] Delete Schedule button pressed.")
        try:
            flow = await self.coordinator.hass.config_entries.options.async_create_flow(
                self.coordinator.entry.entry_id,
                context={"source": "schedule_delete_button"},
            )
        except Exception as exc:
            _LOGGER.exception(
                "[Enphase] Failed to start delete schedule options flow: %s",
                exc,
            )
            return
        _LOGGER.debug(
            "[Enphase] Delete schedule options flow created: handler=%s type=%s",
            flow.handler,
            type(flow).__name__,
        )

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }
