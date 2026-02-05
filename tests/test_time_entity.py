"""Tests for time.py — time entity classes."""

from __future__ import annotations

from datetime import time

from unittest.mock import MagicMock

import pytest

from custom_components.enphase_envoy_cloud_control.const import DOMAIN
from custom_components.enphase_envoy_cloud_control.time import (
    EnphaseScheduleTime,
    _parse_time,
)

from .conftest import ENTRY_ID


# ---------------------------------------------------------------------------
# _parse_time
# ---------------------------------------------------------------------------
class TestParseTime:
    def test_valid_string(self):
        result = _parse_time("14:30")
        assert result == time(14, 30)

    def test_none_returns_none(self):
        assert _parse_time(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_time("") is None

    def test_invalid_returns_none(self):
        assert _parse_time("not-a-time") is None

    def test_midnight(self):
        result = _parse_time("00:00")
        assert result == time(0, 0)

    def test_with_seconds(self):
        result = _parse_time("14:30:00")
        assert result == time(14, 30, 0)


# ---------------------------------------------------------------------------
# EnphaseScheduleTime
# ---------------------------------------------------------------------------
class TestScheduleTime:
    @pytest.fixture
    def edit_start(self, mock_hass, editor_state):
        entity = EnphaseScheduleTime(ENTRY_ID, "start_time", is_new=False)
        entity.hass = mock_hass
        return entity

    @pytest.fixture
    def new_end(self, mock_hass, new_editor_state):
        entity = EnphaseScheduleTime(ENTRY_ID, "end_time", is_new=True)
        entity.hass = mock_hass
        return entity

    def test_reads_from_editor(self, edit_start, editor_state):
        editor_state["start_time"] = "08:30"
        result = edit_start.native_value
        assert result == time(8, 30)

    def test_reads_time_object(self, edit_start, editor_state):
        editor_state["start_time"] = time(14, 0)
        result = edit_start.native_value
        assert result == time(14, 0)

    @pytest.mark.asyncio
    async def test_writes_hhmm_format(self, edit_start, editor_state):
        edit_start.async_write_ha_state = MagicMock()
        await edit_start.async_set_value(time(9, 45))
        assert editor_state["start_time"] == "09:45"

    def test_reads_from_new_editor(self, new_end, new_editor_state):
        new_editor_state["end_time"] = "22:00"
        result = new_end.native_value
        assert result == time(22, 0)

    def test_name_edit_start(self, edit_start):
        assert "Schedule Start" in edit_start._attr_name

    def test_name_new_end(self, new_end):
        assert "New Schedule End" in new_end._attr_name
