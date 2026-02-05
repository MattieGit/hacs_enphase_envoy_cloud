"""Tests for select.py — select entity classes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.enphase_envoy_cloud_control.const import DOMAIN
from custom_components.enphase_envoy_cloud_control.select import (
    EnphaseNewScheduleTypeSelect,
    EnphaseScheduleSelect,
    EnphaseTimedModeSelect,
)

from .conftest import ENTRY_ID


# ---------------------------------------------------------------------------
# EnphaseScheduleSelect
# ---------------------------------------------------------------------------
class TestScheduleSelect:
    @pytest.fixture
    def select(self, mock_coordinator, mock_hass):
        sel = EnphaseScheduleSelect(mock_coordinator, ENTRY_ID)
        sel.hass = mock_hass
        return sel

    def test_options_from_schedules(self, select):
        opts = select.options
        assert isinstance(opts, list)
        assert len(opts) >= 1  # At least cfg schedule from sample data

    def test_current_option_default(self, select):
        assert select.current_option is None

    @pytest.mark.asyncio
    async def test_select_option_populates_editor(self, select, editor_state):
        select.async_write_ha_state = MagicMock()
        # Get available options
        opts = select.options
        if opts:
            await select.async_select_option(opts[0])
            assert editor_state["selected_schedule_id"] == opts[0]

    @pytest.mark.asyncio
    async def test_select_unknown_option(self, select, editor_state):
        select.async_write_ha_state = MagicMock()
        await select.async_select_option("nonexistent-id")
        assert editor_state["selected_schedule_id"] == "nonexistent-id"

    def test_device_info(self, select):
        info = select.device_info
        assert "identifiers" in info


# ---------------------------------------------------------------------------
# EnphaseNewScheduleTypeSelect
# ---------------------------------------------------------------------------
class TestNewScheduleTypeSelect:
    @pytest.fixture
    def select(self, mock_hass):
        sel = EnphaseNewScheduleTypeSelect(ENTRY_ID)
        sel.hass = mock_hass
        return sel

    def test_options(self, select):
        assert select.options == ["cfg", "dtg", "rbd"]

    def test_current_option_default(self, select):
        assert select.current_option == "cfg"

    @pytest.mark.asyncio
    async def test_select_valid_option(self, select, new_editor_state):
        select.async_write_ha_state = MagicMock()
        await select.async_select_option("dtg")
        assert new_editor_state["schedule_type"] == "dtg"

    @pytest.mark.asyncio
    async def test_select_invalid_option(self, select, new_editor_state):
        select.async_write_ha_state = MagicMock()
        await select.async_select_option("invalid")
        # Should not change
        assert new_editor_state["schedule_type"] == "cfg"


# ---------------------------------------------------------------------------
# EnphaseTimedModeSelect
# ---------------------------------------------------------------------------
class TestTimedModeSelect:
    @pytest.fixture
    def select(self):
        return EnphaseTimedModeSelect(ENTRY_ID)

    def test_options(self, select):
        opts = select._attr_options
        assert "Charge from Grid" in opts
        assert "Discharge to Grid" in opts
        assert "Restrict Battery Discharge" in opts

    def test_default_selection(self, select):
        assert select.current_option == "Restrict Battery Discharge"

    @pytest.mark.asyncio
    async def test_select_option(self, select):
        select.async_write_ha_state = MagicMock()
        await select.async_select_option("Charge from Grid")
        assert select.current_option == "Charge from Grid"

    @pytest.mark.asyncio
    async def test_select_invalid_no_change(self, select):
        select.async_write_ha_state = MagicMock()
        await select.async_select_option("Invalid Mode")
        assert select.current_option == "Restrict Battery Discharge"
