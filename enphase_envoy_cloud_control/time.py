"""Time entities for schedule editing."""

from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity

from .const import DOMAIN
from .editor import get_entry_data


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up schedule time entities."""
    async_add_entities(
        [
            EnphaseScheduleTime(entry.entry_id, "start_time", False),
            EnphaseScheduleTime(entry.entry_id, "end_time", False),
            EnphaseScheduleTime(entry.entry_id, "start_time", True),
            EnphaseScheduleTime(entry.entry_id, "end_time", True),
        ],
        True,
    )


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None


class EnphaseScheduleTime(TimeEntity):
    """Time entity for schedule start/end."""

    def __init__(self, entry_id: str, key: str, is_new: bool):
        self.entry_id = entry_id
        self.key = key
        self.is_new = is_new
        schedule_label = "New Schedule" if is_new else "Schedule"
        label = "Start" if key == "start_time" else "End"
        self._attr_name = f"Enphase {schedule_label} {label}"
        suffix = "new" if is_new else "edit"
        self._attr_unique_id = f"{entry_id}_{suffix}_{key}"

    @property
    def native_value(self) -> time | None:
        entry_data = get_entry_data(self.hass, self.entry_id)
        editor_key = "new_editor" if self.is_new else "editor"
        value = entry_data[editor_key].get(self.key)
        if isinstance(value, time):
            return value
        return _parse_time(value)

    async def async_set_value(self, value: time) -> None:
        entry_data = get_entry_data(self.hass, self.entry_id)
        editor_key = "new_editor" if self.is_new else "editor"
        entry_data[editor_key][self.key] = value.strftime("%H:%M")
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.entry_id)},
            "name": "Enphase Envoy Cloud Control",
            "manufacturer": "Enphase Energy",
            "model": "Envoy Cloud API",
        }
