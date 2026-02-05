"""Tests for number.py — number entity classes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.enphase_envoy_cloud_control.const import DOMAIN
from custom_components.enphase_envoy_cloud_control.number import (
    EnphaseScheduleLimit,
    EnphaseTimedDuration,
)

from .conftest import ENTRY_ID


# ---------------------------------------------------------------------------
# EnphaseScheduleLimit
# ---------------------------------------------------------------------------
class TestScheduleLimit:
    @pytest.fixture
    def edit_limit(self, mock_hass):
        entity = EnphaseScheduleLimit(ENTRY_ID, is_new=False)
        entity.hass = mock_hass
        return entity

    @pytest.fixture
    def new_limit(self, mock_hass):
        entity = EnphaseScheduleLimit(ENTRY_ID, is_new=True)
        entity.hass = mock_hass
        return entity

    def test_reads_editor_value(self, edit_limit, editor_state):
        editor_state["limit"] = 42
        assert edit_limit.native_value == 42.0

    @pytest.mark.asyncio
    async def test_writes_editor_value(self, edit_limit, editor_state):
        edit_limit.async_write_ha_state = MagicMock()
        await edit_limit.async_set_native_value(75.0)
        assert editor_state["limit"] == 75

    def test_min_max_step(self, edit_limit):
        assert edit_limit._attr_native_min_value == 0
        assert edit_limit._attr_native_max_value == 100
        assert edit_limit._attr_native_step == 1

    def test_reads_new_editor(self, new_limit, new_editor_state):
        new_editor_state["limit"] = 33
        assert new_limit.native_value == 33.0

    @pytest.mark.asyncio
    async def test_writes_new_editor(self, new_limit, new_editor_state):
        new_limit.async_write_ha_state = MagicMock()
        await new_limit.async_set_native_value(80.0)
        assert new_editor_state["limit"] == 80

    def test_unique_id_edit(self, edit_limit):
        assert edit_limit._attr_unique_id == f"{ENTRY_ID}_edit_limit"

    def test_unique_id_new(self, new_limit):
        assert new_limit._attr_unique_id == f"{ENTRY_ID}_new_limit"


# ---------------------------------------------------------------------------
# EnphaseTimedDuration
# ---------------------------------------------------------------------------
class TestTimedDuration:
    @pytest.fixture
    def duration(self):
        return EnphaseTimedDuration(ENTRY_ID)

    def test_default_value(self, duration):
        assert duration.native_value == 60.0

    @pytest.mark.asyncio
    async def test_set_value(self, duration):
        duration.async_write_ha_state = MagicMock()
        await duration.async_set_native_value(120.0)
        assert duration.native_value == 120.0

    def test_bounds(self, duration):
        assert duration._attr_native_min_value == 1
        assert duration._attr_native_max_value == 1440

    def test_display_precision(self, duration):
        assert duration._attr_suggested_display_precision == 0

    def test_unique_id(self, duration):
        assert duration._attr_unique_id == f"{ENTRY_ID}_timed_duration"

    def test_unit(self, duration):
        assert duration._attr_native_unit_of_measurement == "min"
