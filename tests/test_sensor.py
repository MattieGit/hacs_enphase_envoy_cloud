"""Tests for sensor.py — sensor entity classes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from custom_components.enphase_envoy_cloud_control.sensor import (
    EnphaseBatteryModesSensor,
    EnphaseScheduleSensor,
    EnphaseSchedulesSummarySensor,
    EnphaseTimedModeActiveSensor,
)

from .conftest import ENTRY_ID, SAMPLE_COORDINATOR_DATA


@pytest.fixture
def battery_sensor(mock_coordinator):
    sensor = EnphaseBatteryModesSensor(mock_coordinator)
    return sensor


@pytest.fixture
def summary_sensor(mock_coordinator):
    sensor = EnphaseSchedulesSummarySensor(mock_coordinator)
    return sensor


@pytest.fixture
def schedule_sensor(mock_coordinator):
    sensor = EnphaseScheduleSensor(mock_coordinator, "cfg")
    return sensor


@pytest.fixture
def timed_sensor(mock_coordinator):
    sensor = EnphaseTimedModeActiveSensor(mock_coordinator)
    return sensor


# ---------------------------------------------------------------------------
# EnphaseBatteryModesSensor
# ---------------------------------------------------------------------------
class TestBatteryModesSensor:
    def test_state_ok(self, battery_sensor):
        assert battery_sensor.state == "OK"

    def test_state_unavailable(self, battery_sensor):
        battery_sensor.coordinator.data = None
        assert battery_sensor.state == "Unavailable"

    def test_unique_id(self, battery_sensor):
        assert battery_sensor._attr_unique_id == f"{ENTRY_ID}_battery_modes"

    def test_extra_state_attributes(self, battery_sensor):
        attrs = battery_sensor.extra_state_attributes
        assert "cfg" in attrs
        assert "dtg" in attrs
        assert "rbd" in attrs
        assert "other" in attrs
        assert "last_refresh" in attrs

    def test_extra_state_attributes_with_poll_time(self, battery_sensor):
        battery_sensor.coordinator.last_update_success_time = datetime(
            2025, 1, 1, 12, 0, tzinfo=timezone.utc
        )
        attrs = battery_sensor.extra_state_attributes
        assert "last_successful_poll" in attrs

    def test_extra_state_attributes_empty_data(self, battery_sensor):
        battery_sensor.coordinator.data = None
        attrs = battery_sensor.extra_state_attributes
        # Should not crash — returns partial attrs or error
        assert isinstance(attrs, dict)

    def test_device_info(self, battery_sensor):
        info = battery_sensor.device_info
        assert "identifiers" in info


# ---------------------------------------------------------------------------
# EnphaseSchedulesSummarySensor
# ---------------------------------------------------------------------------
class TestSchedulesSummarySensor:
    def test_state_count(self, summary_sensor):
        # SAMPLE_COORDINATOR_DATA has cfg + rbd schedules
        state = summary_sensor.state
        assert state.isdigit()
        assert int(state) >= 1

    def test_extra_state_attributes(self, summary_sensor):
        attrs = summary_sensor.extra_state_attributes
        assert "schedules" in attrs
        assert isinstance(attrs["schedules"], list)
        assert "last_refresh" in attrs

    def test_unique_id(self, summary_sensor):
        assert summary_sensor._attr_unique_id == f"{ENTRY_ID}_schedules_summary"


# ---------------------------------------------------------------------------
# EnphaseScheduleSensor
# ---------------------------------------------------------------------------
class TestScheduleSensor:
    def test_state_with_schedules(self, schedule_sensor):
        state = schedule_sensor.state
        assert state != "No schedules"
        assert "06:00" in state or "10:00" in state

    def test_state_no_schedules(self, mock_coordinator):
        mock_coordinator.data = {"data": {"cfgControl": {"schedules": []}}}
        sensor = EnphaseScheduleSensor(mock_coordinator, "cfg")
        assert sensor.state == "No schedules"

    def test_extra_state_attributes(self, schedule_sensor):
        attrs = schedule_sensor.extra_state_attributes
        assert "schedule_count" in attrs
        assert attrs["schedule_count"] >= 1
        # Should have schedule_1 key
        assert "schedule_1" in attrs

    def test_extra_state_attributes_with_id(self, schedule_sensor):
        attrs = schedule_sensor.extra_state_attributes
        assert "schedule_1_id" in attrs
        assert attrs["schedule_1_id"] == "sched-cfg-1"

    def test_name(self, schedule_sensor):
        assert "Charge from Grid" in schedule_sensor._attr_name

    def test_schedules_case1_control_schedules(self, mock_coordinator):
        """Case 1: <mode>Control.schedules[]"""
        mock_coordinator.data = {
            "data": {
                "cfgControl": {
                    "schedules": [{"scheduleId": "c1", "startTime": "01:00", "endTime": "02:00"}]
                }
            }
        }
        sensor = EnphaseScheduleSensor(mock_coordinator, "cfg")
        scheds = sensor._schedules()
        assert len(scheds) == 1
        assert scheds[0]["scheduleId"] == "c1"

    def test_schedules_case2_mode_details(self, mock_coordinator):
        """Case 2: <mode>.details[]"""
        mock_coordinator.data = {
            "data": {
                "cfg": {"details": [{"scheduleId": "c2"}]}
            }
        }
        sensor = EnphaseScheduleSensor(mock_coordinator, "cfg")
        scheds = sensor._schedules()
        assert len(scheds) == 1

    def test_schedules_case3_root_schedules(self, mock_coordinator):
        """Case 3: root schedules dict"""
        mock_coordinator.data = {
            "data": {},
            "schedules": {
                "cfg": {"details": [{"scheduleId": "c3"}]}
            },
        }
        sensor = EnphaseScheduleSensor(mock_coordinator, "cfg")
        scheds = sensor._schedules()
        assert len(scheds) == 1

    def test_schedules_case4_cached(self, mock_coordinator):
        """Case 4: client._last_schedules fallback"""
        mock_coordinator.data = {"data": {}}
        mock_coordinator.client._last_schedules = {
            "cfg": {"details": [{"scheduleId": "c4"}]}
        }
        # Need hass for the background task fallback
        mock_coordinator.hass = MagicMock()
        sensor = EnphaseScheduleSensor(mock_coordinator, "cfg")
        sensor.hass = mock_coordinator.hass
        scheds = sensor._schedules()
        assert len(scheds) == 1


# ---------------------------------------------------------------------------
# EnphaseTimedModeActiveSensor
# ---------------------------------------------------------------------------
class TestTimedModeActiveSensor:
    def test_idle_state(self, timed_sensor, mock_coordinator):
        timed_sensor.hass = MagicMock()
        with patch(
            "custom_components.enphase_envoy_cloud_control.timed_mode.get_active_timed_mode",
            return_value=None,
        ):
            assert timed_sensor.state == "Idle"

    def test_active_state(self, timed_sensor, mock_coordinator):
        timed_sensor.hass = MagicMock()
        active = {
            "mode": "rbd",
            "mode_name": "Restrict Battery Discharge",
            "remaining_minutes": 42,
            "expires_at": "2025-01-01T12:00:00+00:00",
            "schedule_id": "s1",
        }
        with patch(
            "custom_components.enphase_envoy_cloud_control.timed_mode.get_active_timed_mode",
            return_value=active,
        ):
            state = timed_sensor.state
            assert "Restrict Battery Discharge" in state
            assert "42 min" in state

    def test_idle_attributes(self, timed_sensor, mock_coordinator):
        timed_sensor.hass = MagicMock()
        with patch(
            "custom_components.enphase_envoy_cloud_control.timed_mode.get_active_timed_mode",
            return_value=None,
        ):
            attrs = timed_sensor.extra_state_attributes
            assert attrs["mode"] == "none"

    def test_active_attributes(self, timed_sensor, mock_coordinator):
        timed_sensor.hass = MagicMock()
        active = {
            "mode": "cfg",
            "mode_name": "Charge from Grid",
            "remaining_minutes": 15,
            "expires_at": "2025-01-01T12:00:00+00:00",
            "schedule_id": "s1",
        }
        with patch(
            "custom_components.enphase_envoy_cloud_control.timed_mode.get_active_timed_mode",
            return_value=active,
        ):
            attrs = timed_sensor.extra_state_attributes
            assert attrs["mode"] == "cfg"
            assert attrs["remaining_minutes"] == 15
            assert attrs["schedule_id"] == "s1"
