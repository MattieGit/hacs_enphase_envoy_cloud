"""Number entities for schedule editing."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity

from .const import DOMAIN
from .device import battery_device_info, schedule_editor_device_info
from .editor import get_entry_data


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up schedule number entities."""
    async_add_entities(
        [
            EnphaseScheduleLimit(entry.entry_id, False),
            EnphaseScheduleLimit(entry.entry_id, True),
            EnphaseTimedDuration(entry.entry_id),
        ],
        True,
    )


class EnphaseScheduleLimit(NumberEntity):
    """Number entity for schedule limit."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"

    def __init__(self, entry_id: str, is_new: bool):
        self.entry_id = entry_id
        self.is_new = is_new
        schedule_label = "New Schedule" if is_new else "Schedule"
        self._attr_name = f"Enphase {schedule_label} Limit"
        suffix = "new" if is_new else "edit"
        self._attr_unique_id = f"{entry_id}_{suffix}_limit"

    @property
    def native_value(self) -> float | None:
        entry_data = get_entry_data(self.hass, self.entry_id)
        editor_key = "new_editor" if self.is_new else "editor"
        return float(entry_data[editor_key].get("limit", 0))

    async def async_set_native_value(self, value: float) -> None:
        entry_data = get_entry_data(self.hass, self.entry_id)
        editor_key = "new_editor" if self.is_new else "editor"
        entry_data[editor_key]["limit"] = int(value)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return schedule_editor_device_info(self.entry_id)


class EnphaseTimedDuration(NumberEntity):
    """Number entity for timed mode duration in minutes."""

    _attr_native_min_value = 1
    _attr_native_max_value = 1440
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_name = "Timed Duration"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, entry_id: str):
        self.entry_id = entry_id
        self._attr_unique_id = f"{entry_id}_timed_duration"
        self._duration = 60  # default 60 minutes

    @property
    def native_value(self) -> float:
        return float(self._duration)

    async def async_set_native_value(self, value: float) -> None:
        self._duration = int(value)
        self.async_write_ha_state()

    @property
    def device_info(self):
        return battery_device_info(self.entry_id)
