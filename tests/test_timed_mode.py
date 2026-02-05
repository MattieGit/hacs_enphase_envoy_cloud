"""Tests for timed_mode.py — async business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.enphase_envoy_cloud_control.const import DOMAIN
from custom_components.enphase_envoy_cloud_control.timed_mode import (
    MODE_NAMES,
    STORE_KEY,
    STORE_VERSION,
    _calculate_schedule_times,
    _timed_modes,
    cancel_all_timed_modes,
    cancel_timed_mode,
    enable_timed_mode,
    get_active_timed_mode,
    recover_timed_modes,
)

from .conftest import ENTRY_ID


@pytest.fixture
def hass_with_timed(mock_hass, mock_coordinator):
    """A hass object pre-configured for timed mode tests."""
    mock_hass.data[DOMAIN][ENTRY_ID]["timed_modes"] = {}
    return mock_hass


# ---------------------------------------------------------------------------
# _calculate_schedule_times
# ---------------------------------------------------------------------------
class TestCalculateScheduleTimes:
    def test_same_day(self):
        with patch("custom_components.enphase_envoy_cloud_control.timed_mode.datetime") as mock_dt:
            from zoneinfo import ZoneInfo
            # Monday 10:00 UTC + 60 minutes = Monday 11:00 UTC
            mock_now = datetime(2025, 1, 6, 10, 0, tzinfo=ZoneInfo("UTC"))  # Monday
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            start, end, days = _calculate_schedule_times(60, "UTC")
            assert start == "10:00"
            assert end == "11:00"
            assert days == [1]  # Monday only

    def test_midnight_crossing(self):
        with patch("custom_components.enphase_envoy_cloud_control.timed_mode.datetime") as mock_dt:
            from zoneinfo import ZoneInfo
            # Monday 23:00 UTC + 120 min = Tuesday 01:00 UTC
            mock_now = datetime(2025, 1, 6, 23, 0, tzinfo=ZoneInfo("UTC"))  # Monday
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            start, end, days = _calculate_schedule_times(120, "UTC")
            assert start == "23:00"
            assert end == "01:00"
            assert 1 in days and 2 in days  # Mon + Tue

    def test_timezone_handling(self):
        from freezegun import freeze_time

        with freeze_time("2025-01-06 10:00:00", tz_offset=0):
            start, end, days = _calculate_schedule_times(30, "UTC")
            assert start == "10:00"
            assert end == "10:30"


# ---------------------------------------------------------------------------
# get_active_timed_mode
# ---------------------------------------------------------------------------
class TestGetActiveTimedMode:
    def test_no_timed_modes(self, hass_with_timed):
        result = get_active_timed_mode(hass_with_timed, ENTRY_ID)
        assert result is None

    def test_expired_mode(self, hass_with_timed):
        past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]["rbd"] = {
            "expires_at": past,
            "mode_name": "Restrict Battery Discharge",
            "schedule_id": "s1",
        }
        result = get_active_timed_mode(hass_with_timed, ENTRY_ID)
        assert result is None

    def test_active_mode(self, hass_with_timed):
        future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]["cfg"] = {
            "expires_at": future,
            "mode_name": "Charge from Grid",
            "schedule_id": "s2",
        }
        result = get_active_timed_mode(hass_with_timed, ENTRY_ID)
        assert result is not None
        assert result["mode"] == "cfg"
        assert result["mode_name"] == "Charge from Grid"
        assert result["remaining_minutes"] > 0
        assert result["schedule_id"] == "s2"

    def test_remaining_minutes_calculation(self, hass_with_timed):
        future = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
        hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]["dtg"] = {
            "expires_at": future,
            "mode_name": "Discharge to Grid",
            "schedule_id": "s3",
        }
        result = get_active_timed_mode(hass_with_timed, ENTRY_ID)
        # Should be approximately 45 minutes, give or take 1
        assert 43 <= result["remaining_minutes"] <= 46


# ---------------------------------------------------------------------------
# enable_timed_mode
# ---------------------------------------------------------------------------
class TestEnableTimedMode:
    @pytest.mark.asyncio
    async def test_enables_mode_and_sets_timer(self, hass_with_timed, mock_coordinator):
        """Timed mode simply enables the mode and sets a timer to disable it."""
        mock_coordinator.client.set_mode.return_value = True

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.async_call_later"
            ) as mock_timer:
                mock_timer.return_value = MagicMock()  # cancel callback
                with patch(
                    "custom_components.enphase_envoy_cloud_control.timed_mode._save_store",
                    new_callable=AsyncMock,
                ):
                    await enable_timed_mode(hass_with_timed, ENTRY_ID, "rbd", 60)

        # No schedule created — just enable mode and set timer
        mock_coordinator.client.add_schedule.assert_not_called()
        # Verify mode was enabled
        mock_coordinator.client.set_mode.assert_called_once_with("rbd", True)
        # Verify timed modes dict was populated
        timed = hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]
        assert "rbd" in timed
        assert timed["rbd"]["schedule_id"] is None  # No schedule

    @pytest.mark.asyncio
    async def test_cancels_existing_before_enabling(self, hass_with_timed, mock_coordinator):
        # Pre-populate an existing timed mode
        cancel_cb = MagicMock()
        hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]["rbd"] = {
            "schedule_id": "old-sched",
            "cancel": cancel_cb,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "mode_name": "Restrict Battery Discharge",
        }

        mock_coordinator.client.add_schedule.return_value = {"scheduleId": "new-sched"}

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.async_call_later"
            ) as mock_timer:
                mock_timer.return_value = MagicMock()
                with patch(
                    "custom_components.enphase_envoy_cloud_control.timed_mode._save_store",
                    new_callable=AsyncMock,
                ):
                    await enable_timed_mode(hass_with_timed, ENTRY_ID, "rbd", 30)

        # The old cancel callback should have been called
        cancel_cb.assert_called_once()


# ---------------------------------------------------------------------------
# cancel_timed_mode
# ---------------------------------------------------------------------------
class TestCancelTimedMode:
    @pytest.mark.asyncio
    async def test_cancels_timer_and_deletes_schedule(self, hass_with_timed, mock_coordinator):
        cancel_cb = MagicMock()
        hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]["cfg"] = {
            "schedule_id": "sched-to-delete",
            "cancel": cancel_cb,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=20)).isoformat(),
            "mode_name": "Charge from Grid",
        }
        # Set up coordinator data so disable_mode path works
        mock_coordinator.data = {
            "data": {"cfgControl": {"chargeFromGrid": True}}
        }

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode._save_store",
                new_callable=AsyncMock,
            ):
                with patch(
                    "custom_components.enphase_envoy_cloud_control.timed_mode.async_call_later"
                ):
                    await cancel_timed_mode(hass_with_timed, ENTRY_ID, "cfg", disable_mode=True)

        cancel_cb.assert_called_once()
        mock_coordinator.client.delete_schedule.assert_called_with("sched-to-delete")
        mock_coordinator.client.set_mode.assert_called_with("cfg", False)

    @pytest.mark.asyncio
    async def test_no_op_if_no_active_mode(self, hass_with_timed, mock_coordinator):
        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode._save_store",
                new_callable=AsyncMock,
            ):
                await cancel_timed_mode(hass_with_timed, ENTRY_ID, "rbd")

        mock_coordinator.client.delete_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_delete_error(self, hass_with_timed, mock_coordinator):
        hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]["dtg"] = {
            "schedule_id": "error-sched",
            "cancel": MagicMock(),
        }
        mock_coordinator.client.delete_schedule.side_effect = Exception("API error")
        mock_coordinator.data = {"data": {"dtgControl": {"enabled": True}}}

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode._save_store",
                new_callable=AsyncMock,
            ):
                with patch(
                    "custom_components.enphase_envoy_cloud_control.timed_mode.async_call_later"
                ):
                    # Should not raise
                    await cancel_timed_mode(hass_with_timed, ENTRY_ID, "dtg", disable_mode=True)


# ---------------------------------------------------------------------------
# cancel_all_timed_modes
# ---------------------------------------------------------------------------
class TestCancelAllTimedModes:
    @pytest.mark.asyncio
    async def test_cancels_all(self, hass_with_timed, mock_coordinator):
        now_plus = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
        timed = hass_with_timed.data[DOMAIN][ENTRY_ID]["timed_modes"]
        timed["cfg"] = {"schedule_id": "s1", "cancel": MagicMock(), "expires_at": now_plus}
        timed["rbd"] = {"schedule_id": "s2", "cancel": MagicMock(), "expires_at": now_plus}
        mock_coordinator.data = {"data": {"cfgControl": {"chargeFromGrid": True}, "rbdControl": {"enabled": True}}}

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode._save_store",
                new_callable=AsyncMock,
            ):
                with patch(
                    "custom_components.enphase_envoy_cloud_control.timed_mode._clear_store",
                    new_callable=AsyncMock,
                ) as mock_clear:
                    with patch(
                        "custom_components.enphase_envoy_cloud_control.timed_mode.async_call_later"
                    ):
                        await cancel_all_timed_modes(hass_with_timed, ENTRY_ID)

        mock_clear.assert_called_once()
        # Both schedules should be deleted
        assert mock_coordinator.client.delete_schedule.call_count == 2


# ---------------------------------------------------------------------------
# recover_timed_modes
# ---------------------------------------------------------------------------
class TestRecoverTimedModes:
    @pytest.mark.asyncio
    async def test_cleans_up_orphans(self, hass_with_timed, mock_coordinator):
        store_data = {
            "cfg": {"schedule_id": "orphan-1", "mode": "cfg"},
            "rbd": {"schedule_id": "orphan-2", "mode": "rbd"},
        }

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.Store"
            ) as MockStore:
                store_instance = AsyncMock()
                store_instance.async_load.return_value = store_data
                MockStore.return_value = store_instance

                await recover_timed_modes(hass_with_timed, ENTRY_ID)

        assert mock_coordinator.client.delete_schedule.call_count == 2
        assert mock_coordinator.client.set_mode.call_count == 2

    @pytest.mark.asyncio
    async def test_no_data_no_op(self, hass_with_timed, mock_coordinator):
        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.Store"
            ) as MockStore:
                store_instance = AsyncMock()
                store_instance.async_load.return_value = None
                MockStore.return_value = store_instance

                await recover_timed_modes(hass_with_timed, ENTRY_ID)

        mock_coordinator.client.delete_schedule.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_delete_failure(self, hass_with_timed, mock_coordinator):
        store_data = {"cfg": {"schedule_id": "fail-sched", "mode": "cfg"}}
        mock_coordinator.client.delete_schedule.side_effect = Exception("fail")

        with patch(
            "custom_components.enphase_envoy_cloud_control.editor.get_coordinator",
            return_value=mock_coordinator,
        ):
            with patch(
                "custom_components.enphase_envoy_cloud_control.timed_mode.Store"
            ) as MockStore:
                store_instance = AsyncMock()
                store_instance.async_load.return_value = store_data
                MockStore.return_value = store_instance

                # Should not raise
                await recover_timed_modes(hass_with_timed, ENTRY_ID)
