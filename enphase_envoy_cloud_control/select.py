"""Select entities for schedule editing."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .editor import (
    editor_days_from_list,
    get_coordinator,
    get_entry_data,
    normalize_schedules,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up schedule select entities."""
    coordinator = get_coordinator(hass, entry.entry_id)
    async_add_entities(
        [
            EnphaseScheduleSelect(coordinator, entry.entry_id),
            EnphaseNewScheduleTypeSelect(entry.entry_id),
        ],
        True,
    )


class EnphaseScheduleSelect(SelectEntity):
    """Select the active schedule to edit."""

    _attr_name = "Enphase Schedule Selected"
    _attr_icon = "mdi:calendar-edit"

    def __init__(self, coordinator, entry_id: str):
        self.coordinator = coordinator
        self.entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_schedule_selected"

    @property
    def options(self):
        schedules = normalize_schedules(self.coordinator)
        return [schedule["id"] for schedule in schedules]

    @property
    def current_option(self):
        editor = get_entry_data(self.hass, self.entry_id)["editor"]
        return editor.get("selected_schedule_id")

    async def async_select_option(self, option: str) -> None:
        entry_data = get_entry_data(self.hass, self.entry_id)
        schedules = normalize_schedules(self.coordinator)
        match = next((sched for sched in schedules if sched["id"] == option), None)
        editor = entry_data["editor"]
        editor["selected_schedule_id"] = option
        if match:
            editor["schedule_type"] = match.get("type", "cfg")
            editor["start_time"] = match.get("start", "00:00")
            editor["end_time"] = match.get("end", "00:00")
            editor["limit"] = int(match.get("limit", 0))
            editor["days"] = editor_days_from_list(match.get("days", []))
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }


class EnphaseNewScheduleTypeSelect(SelectEntity):
    """Select schedule type for a new schedule."""

    _attr_name = "Enphase New Schedule Type"
    _attr_icon = "mdi:calendar-plus"

    def __init__(self, entry_id: str):
        self.entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_new_schedule_type"
        self._attr_options = ["cfg", "dtg", "rbd"]

    @property
    def options(self):
        return list(self._attr_options)

    @property
    def current_option(self):
        entry_data = get_entry_data(self.hass, self.entry_id)
        return entry_data["new_editor"].get("schedule_type", "cfg")

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            _LOGGER.warning("[Enphase] Invalid schedule type selected: %s", option)
            return
        entry_data = get_entry_data(self.hass, self.entry_id)
        entry_data["new_editor"]["schedule_type"] = option
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }
