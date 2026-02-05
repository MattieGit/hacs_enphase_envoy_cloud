"""Tests for coordinator.py — data merging and coordinator lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.enphase_envoy_cloud_control.coordinator import EnphaseCoordinator

from .conftest import ENTRY_ID, SAMPLE_BATTERY_DATA, SAMPLE_SCHEDULES_DATA


@pytest.fixture
def coordinator(mock_entry):
    """Create a real EnphaseCoordinator with a mocked hass."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    with patch(
        "custom_components.enphase_envoy_cloud_control.coordinator.DataUpdateCoordinator.__init__"
    ):
        coord = EnphaseCoordinator(hass, mock_entry)
    return coord


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------
class TestConstructor:
    def test_default_poll_interval(self, mock_entry):
        mock_entry.options = {}
        hass = MagicMock()
        with patch(
            "custom_components.enphase_envoy_cloud_control.coordinator.DataUpdateCoordinator.__init__"
        ):
            coord = EnphaseCoordinator(hass, mock_entry)
        assert coord.update_interval == timedelta(seconds=30)

    def test_custom_poll_interval(self, mock_entry):
        mock_entry.options = {"poll_interval": 60}
        hass = MagicMock()
        with patch(
            "custom_components.enphase_envoy_cloud_control.coordinator.DataUpdateCoordinator.__init__"
        ):
            coord = EnphaseCoordinator(hass, mock_entry)
        assert coord.update_interval == timedelta(seconds=60)

    def test_client_credentials(self, coordinator, mock_entry):
        assert coordinator.client.email == mock_entry.data["email"]
        assert coordinator.client.password == mock_entry.data["password"]


# ---------------------------------------------------------------------------
# _fetch
# ---------------------------------------------------------------------------
class TestFetch:
    def test_merges_schedule_details(self, coordinator):
        coordinator.client.battery_settings = MagicMock(return_value=SAMPLE_BATTERY_DATA)
        coordinator.client.get_schedules = MagicMock(return_value=SAMPLE_SCHEDULES_DATA)

        result = coordinator._fetch()

        assert "data" in result
        assert "schedules" in result
        assert "schedules_raw" in result

    def test_handles_missing_schedule_data(self, coordinator):
        coordinator.client.battery_settings = MagicMock(return_value={"data": {}})
        coordinator.client.get_schedules = MagicMock(return_value={})

        result = coordinator._fetch()
        assert result["data"] == {}

    def test_caches_last_schedules(self, coordinator):
        coordinator.client.battery_settings = MagicMock(return_value={})
        schedules = {"data": {"cfg": {"details": []}}}
        coordinator.client.get_schedules = MagicMock(return_value=schedules)

        coordinator._fetch()
        assert coordinator.client._last_schedules == schedules

    def test_merges_schedule_details_into_control(self, coordinator):
        battery = {
            "data": {
                "cfgControl": {
                    "schedules": [
                        {"startTime": None, "endTime": None}
                    ]
                }
            }
        }
        schedules = {
            "data": {
                "cfg": {
                    "details": [
                        {
                            "scheduleId": "real-id",
                            "startTime": "06:00",
                            "endTime": "10:00",
                            "limit": 80,
                            "days": [1, 2],
                        }
                    ]
                }
            }
        }
        coordinator.client.battery_settings = MagicMock(return_value=battery)
        coordinator.client.get_schedules = MagicMock(return_value=schedules)

        result = coordinator._fetch()
        merged_sched = result["data"]["cfgControl"]["schedules"][0]
        assert merged_sched["startTime"] == "06:00"
        assert merged_sched["endTime"] == "10:00"
        assert merged_sched["scheduleId"] == "real-id"
        assert merged_sched["limit"] == 80

    def test_fetch_raises_on_error(self, coordinator):
        coordinator.client.battery_settings = MagicMock(side_effect=Exception("API error"))

        with pytest.raises(Exception, match="API error"):
            coordinator._fetch()

    def test_handles_none_battery_data(self, coordinator):
        coordinator.client.battery_settings = MagicMock(return_value=None)
        coordinator.client.get_schedules = MagicMock(return_value=None)

        result = coordinator._fetch()
        assert result is not None


# ---------------------------------------------------------------------------
# _async_update_data
# ---------------------------------------------------------------------------
class TestAsyncUpdateData:
    @pytest.mark.asyncio
    async def test_sets_timestamps(self, coordinator):
        coordinator.client.battery_settings = MagicMock(return_value={"data": {}})
        coordinator.client.get_schedules = MagicMock(return_value={})

        result = await coordinator._async_update_data()
        assert coordinator.last_successful_poll is not None
        assert coordinator.last_refresh is not None
        assert isinstance(coordinator.last_successful_poll, datetime)

    @pytest.mark.asyncio
    async def test_wraps_errors_in_update_failed(self, coordinator):
        coordinator.client.battery_settings = MagicMock(side_effect=Exception("fail"))

        from homeassistant.helpers.update_coordinator import UpdateFailed
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()


# ---------------------------------------------------------------------------
# async_initialize_auth
# ---------------------------------------------------------------------------
class TestAsyncInitializeAuth:
    @pytest.mark.asyncio
    async def test_persists_discovered_ids(self, coordinator, mock_entry):
        coordinator.client.load_cache = MagicMock()
        coordinator.client.ensure_authenticated = MagicMock(
            return_value={"user_id": "discovered_uid", "battery_id": "discovered_bid"}
        )
        mock_entry.data = {"email": "test@example.com", "password": "secret"}

        coordinator.hass.config_entries = MagicMock()

        await coordinator.async_initialize_auth()

        coordinator.hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = coordinator.hass.config_entries.async_update_entry.call_args
        updated_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        assert updated_data["user_id"] == "discovered_uid"
        assert updated_data["battery_id"] == "discovered_bid"

    @pytest.mark.asyncio
    async def test_no_update_when_ids_present(self, coordinator, mock_entry):
        coordinator.client.load_cache = MagicMock()
        coordinator.client.ensure_authenticated = MagicMock(
            return_value={"user_id": "12345", "battery_id": "67890"}
        )

        coordinator.hass.config_entries = MagicMock()

        await coordinator.async_initialize_auth()

        coordinator.hass.config_entries.async_update_entry.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_update_when_auth_returns_none(self, coordinator, mock_entry):
        coordinator.client.load_cache = MagicMock()
        coordinator.client.ensure_authenticated = MagicMock(return_value=None)

        coordinator.hass.config_entries = MagicMock()

        await coordinator.async_initialize_auth()

        coordinator.hass.config_entries.async_update_entry.assert_not_called()
