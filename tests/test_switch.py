"""Tests for switch.py — switch entity classes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.enphase_envoy_cloud_control.const import DOMAIN
from custom_components.enphase_envoy_cloud_control.switch import (
    EnphaseEditorDaySwitch,
    EnphaseModeSwitch,
)

from .conftest import ENTRY_ID


# ---------------------------------------------------------------------------
# EnphaseModeSwitch
# ---------------------------------------------------------------------------
class TestModeSwitch:
    @pytest.fixture
    def cfg_switch(self, mock_coordinator):
        return EnphaseModeSwitch(mock_coordinator, "cfgControl")

    @pytest.fixture
    def dtg_switch(self, mock_coordinator):
        return EnphaseModeSwitch(mock_coordinator, "dtgControl")

    def test_is_on_cfg_no_enabled_key(self, cfg_switch):
        # cfgControl has chargeFromGrid not enabled, so is_on catches and returns False
        assert cfg_switch.is_on is False

    def test_is_on_cfg_with_enabled(self, cfg_switch):
        cfg_switch.coordinator.data = {
            "data": {"cfgControl": {"enabled": True}}
        }
        assert cfg_switch.is_on is True

    def test_is_on_dtg(self, dtg_switch):
        # dtgControl.enabled = False in sample data
        assert dtg_switch.is_on is False

    def test_is_on_missing_data(self, cfg_switch):
        cfg_switch.coordinator.data = None
        assert cfg_switch.is_on is False

    def test_human_readable_name(self, cfg_switch):
        assert cfg_switch._attr_name == "Charge from Grid"

    def test_unique_id(self, cfg_switch):
        assert cfg_switch._attr_unique_id == f"{ENTRY_ID}_cfg"

    @pytest.mark.asyncio
    async def test_turn_on(self, cfg_switch):
        with patch("custom_components.enphase_envoy_cloud_control.switch.asyncio.sleep", new_callable=AsyncMock):
            await cfg_switch.async_turn_on()
        cfg_switch.coordinator.client.set_mode.assert_called_with("cfgControl", True)

    @pytest.mark.asyncio
    async def test_turn_off(self, cfg_switch):
        with patch("custom_components.enphase_envoy_cloud_control.switch.asyncio.sleep", new_callable=AsyncMock):
            await cfg_switch.async_turn_off()
        cfg_switch.coordinator.client.set_mode.assert_called_with("cfgControl", False)

    def test_device_info(self, cfg_switch):
        info = cfg_switch.device_info
        assert "identifiers" in info


# ---------------------------------------------------------------------------
# EnphaseEditorDaySwitch
# ---------------------------------------------------------------------------
class TestEditorDaySwitch:
    @pytest.fixture
    def edit_switch(self, mock_hass):
        switch = EnphaseEditorDaySwitch(ENTRY_ID, "mon", is_new=False)
        switch.hass = mock_hass
        return switch

    @pytest.fixture
    def new_switch(self, mock_hass):
        switch = EnphaseEditorDaySwitch(ENTRY_ID, "fri", is_new=True)
        switch.hass = mock_hass
        return switch

    def test_is_on_default_false(self, edit_switch):
        assert edit_switch.is_on is False

    @pytest.mark.asyncio
    async def test_turn_on_edit(self, edit_switch, editor_state):
        edit_switch.async_write_ha_state = MagicMock()
        await edit_switch.async_turn_on()
        assert editor_state["days"]["mon"] is True

    @pytest.mark.asyncio
    async def test_turn_off_edit(self, edit_switch, editor_state):
        editor_state["days"]["mon"] = True
        edit_switch.async_write_ha_state = MagicMock()
        await edit_switch.async_turn_off()
        assert editor_state["days"]["mon"] is False

    @pytest.mark.asyncio
    async def test_new_switch_routing(self, new_switch, new_editor_state):
        new_switch.async_write_ha_state = MagicMock()
        await new_switch.async_turn_on()
        assert new_editor_state["days"]["fri"] is True

    def test_name_edit(self, edit_switch):
        assert "Schedule Mon" in edit_switch._attr_name

    def test_name_new(self, new_switch):
        assert "New Schedule Fri" in new_switch._attr_name

    def test_unique_id_edit(self, edit_switch):
        assert edit_switch._attr_unique_id == f"{ENTRY_ID}_edit_mon"

    def test_unique_id_new(self, new_switch):
        assert new_switch._attr_unique_id == f"{ENTRY_ID}_new_fri"
