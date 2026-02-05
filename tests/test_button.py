"""Tests for button.py — button entity classes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.enphase_envoy_cloud_control.const import DOMAIN
from custom_components.enphase_envoy_cloud_control.button import (
    EnphaseCancelTimedModeButton,
    EnphaseForceCloudRefreshButton,
    EnphaseNewScheduleAddButton,
    EnphaseScheduleDeleteButton,
    EnphaseScheduleSaveButton,
    EnphaseStartTimedModeButton,
)

from .conftest import ENTRY_ID


# ---------------------------------------------------------------------------
# EnphaseForceCloudRefreshButton
# ---------------------------------------------------------------------------
class TestForceCloudRefreshButton:
    @pytest.fixture
    def button(self, mock_coordinator):
        return EnphaseForceCloudRefreshButton(mock_coordinator)

    def test_available(self, button):
        assert button.available is True

    @pytest.mark.asyncio
    async def test_press_success(self, button):
        await button.async_press()
        button.coordinator.async_force_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_press_handles_error(self, button):
        button.coordinator.async_force_refresh = AsyncMock(side_effect=Exception("fail"))
        # Should not raise
        await button.async_press()

    def test_device_info(self, button):
        info = button.device_info
        assert "identifiers" in info


# ---------------------------------------------------------------------------
# EnphaseScheduleSaveButton
# ---------------------------------------------------------------------------
class TestScheduleSaveButton:
    @pytest.fixture
    def button(self, mock_hass, editor_state):
        btn = EnphaseScheduleSaveButton(ENTRY_ID)
        btn.hass = mock_hass
        return btn

    @pytest.mark.asyncio
    async def test_press_with_selected_schedule(self, button, editor_state):
        editor_state["selected_schedule_id"] = "sched-123"
        editor_state["schedule_type"] = "cfg"
        editor_state["start_time"] = "08:00"
        editor_state["end_time"] = "16:00"
        editor_state["limit"] = 50

        await button.async_press()

        button.hass.services.async_call.assert_awaited_once()
        call_args = button.hass.services.async_call.call_args
        assert call_args[0][0] == DOMAIN
        assert call_args[0][1] == "update_schedule"
        data = call_args[0][2]
        assert data["schedule_id"] == "sched-123"
        assert data["confirm"] is True

    @pytest.mark.asyncio
    async def test_press_no_selection(self, button, editor_state):
        editor_state["selected_schedule_id"] = None
        await button.async_press()
        button.hass.services.async_call.assert_not_awaited()


# ---------------------------------------------------------------------------
# EnphaseScheduleDeleteButton
# ---------------------------------------------------------------------------
class TestScheduleDeleteButton:
    @pytest.fixture
    def button(self, mock_hass, editor_state):
        btn = EnphaseScheduleDeleteButton(ENTRY_ID)
        btn.hass = mock_hass
        return btn

    @pytest.mark.asyncio
    async def test_press_with_selection(self, button, editor_state):
        editor_state["selected_schedule_id"] = "sched-456"
        await button.async_press()

        button.hass.services.async_call.assert_awaited_once()
        call_args = button.hass.services.async_call.call_args
        assert call_args[0][1] == "delete_schedule"
        data = call_args[0][2]
        assert data["schedule_id"] == "sched-456"
        assert data["confirm"] is True

    @pytest.mark.asyncio
    async def test_press_no_selection(self, button, editor_state):
        editor_state["selected_schedule_id"] = None
        await button.async_press()
        button.hass.services.async_call.assert_not_awaited()


# ---------------------------------------------------------------------------
# EnphaseNewScheduleAddButton
# ---------------------------------------------------------------------------
class TestNewScheduleAddButton:
    @pytest.fixture
    def button(self, mock_hass, new_editor_state):
        btn = EnphaseNewScheduleAddButton(ENTRY_ID)
        btn.hass = mock_hass
        return btn

    @pytest.mark.asyncio
    async def test_press(self, button, new_editor_state):
        new_editor_state["schedule_type"] = "dtg"
        new_editor_state["start_time"] = "09:00"
        new_editor_state["end_time"] = "17:00"
        new_editor_state["limit"] = 75

        await button.async_press()

        button.hass.services.async_call.assert_awaited_once()
        call_args = button.hass.services.async_call.call_args
        assert call_args[0][1] == "add_schedule"
        data = call_args[0][2]
        assert data["schedule_type"] == "dtg"
        assert data["start_time"] == "09:00"
        assert data["limit"] == 75


# ---------------------------------------------------------------------------
# EnphaseStartTimedModeButton
# ---------------------------------------------------------------------------
class TestStartTimedModeButton:
    @pytest.fixture
    def button(self, mock_coordinator):
        btn = EnphaseStartTimedModeButton(mock_coordinator)
        btn.hass = MagicMock()
        return btn

    @pytest.mark.asyncio
    async def test_press_calls_enable(self, button):
        # Mock entity registry and state
        mock_reg = MagicMock()

        def _get_entity_id(domain, integration, unique_id):
            if domain == "select":
                return "select.timed_mode"
            return "number.timed_duration"

        mock_reg.async_get_entity_id.side_effect = _get_entity_id
        mode_state = MagicMock()
        mode_state.state = "Charge from Grid"
        dur_state = MagicMock()
        dur_state.state = "90"

        def _get_state(entity_id):
            if entity_id == "select.timed_mode":
                return mode_state
            return dur_state

        button.hass.states.get = MagicMock(side_effect=_get_state)

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_reg):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.enable_timed_mode",
                new_callable=AsyncMock,
            ) as mock_enable:
                await button.async_press()
                mock_enable.assert_awaited_once()
                args = mock_enable.call_args
                assert args[0][2] == "cfg"  # mode
                assert args[0][3] == 90  # duration

    @pytest.mark.asyncio
    async def test_defaults_when_no_state(self, button):
        mock_reg = MagicMock()
        mock_reg.async_get_entity_id.return_value = None
        button.hass.states.get = MagicMock(return_value=None)

        with patch("homeassistant.helpers.entity_registry.async_get", return_value=mock_reg):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.enable_timed_mode",
                new_callable=AsyncMock,
            ) as mock_enable:
                await button.async_press()
                args = mock_enable.call_args
                assert args[0][2] == "rbd"  # default mode
                assert args[0][3] == 60  # default duration


# ---------------------------------------------------------------------------
# EnphaseCancelTimedModeButton
# ---------------------------------------------------------------------------
class TestCancelTimedModeButton:
    @pytest.fixture
    def button(self, mock_coordinator):
        btn = EnphaseCancelTimedModeButton(mock_coordinator)
        btn.hass = MagicMock()
        return btn

    @pytest.mark.asyncio
    async def test_cancels_active_mode(self, button):
        active = {"mode": "cfg", "mode_name": "Charge from Grid", "remaining_minutes": 30}

        with patch(
            "custom_components.enphase_envoy_cloud_control.timed_mode.get_active_timed_mode",
            return_value=active,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.cancel_timed_mode",
                new_callable=AsyncMock,
            ) as mock_cancel:
                await button.async_press()
                mock_cancel.assert_awaited_once()
                args = mock_cancel.call_args
                assert args[0][2] == "cfg"

    @pytest.mark.asyncio
    async def test_no_op_when_idle(self, button):
        with patch(
            "custom_components.enphase_envoy_cloud_control.timed_mode.get_active_timed_mode",
            return_value=None,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.cancel_timed_mode",
                new_callable=AsyncMock,
            ) as mock_cancel:
                await button.async_press()
                mock_cancel.assert_not_awaited()
