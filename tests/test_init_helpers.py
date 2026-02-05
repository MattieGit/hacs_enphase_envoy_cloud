"""Tests for __init__.py helper functions."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.enphase_envoy_cloud_control import (
    _collect_schedules,
    _mode_settings_from_data,
    _normalize_schedule_ids,
)


# ---------------------------------------------------------------------------
# _normalize_schedule_ids
# ---------------------------------------------------------------------------
class TestNormalizeScheduleIds:
    def test_none_returns_empty(self):
        assert _normalize_schedule_ids(None) == []

    def test_single_string(self):
        result = _normalize_schedule_ids("abc123def456")
        assert result == ["abc123def456"]

    def test_list_of_strings(self):
        result = _normalize_schedule_ids(["abc123", "def456"])
        assert "abc123" in result
        assert "def456" in result

    def test_comma_separated(self):
        result = _normalize_schedule_ids("abc123,def456")
        assert "abc123" in result
        assert "def456" in result

    def test_hex_extraction(self):
        result = _normalize_schedule_ids("Schedule abc123-def456-789012")
        assert "abc123-def456-789012" in result

    def test_empty_string(self):
        assert _normalize_schedule_ids("") == []

    def test_tuple_input(self):
        result = _normalize_schedule_ids(("abc123",))
        assert "abc123" in result

    def test_set_input(self):
        result = _normalize_schedule_ids({"abcdef"})
        assert "abcdef" in result

    def test_strips_quotes(self):
        result = _normalize_schedule_ids(["'abc123'", '"def456"'])
        assert "abc123" in result
        assert "def456" in result

    def test_short_ids_fallback(self):
        # IDs shorter than 6 hex chars go through the split path
        result = _normalize_schedule_ids("ab cd")
        assert "ab" in result
        assert "cd" in result


# ---------------------------------------------------------------------------
# _collect_schedules
# ---------------------------------------------------------------------------
class TestCollectSchedules:
    def _make_coordinator(self, data):
        coord = MagicMock()
        coord.data = data
        coord.client = MagicMock(spec=[])
        return coord

    def test_primary_path(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {"schedules": [{"scheduleId": "s1"}]}
            }
        })
        assert _collect_schedules(coord, "cfg") == [{"scheduleId": "s1"}]

    def test_fallback_dict_details(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {"dtg": {"details": [{"scheduleId": "s2"}]}},
        })
        assert _collect_schedules(coord, "dtg") == [{"scheduleId": "s2"}]

    def test_fallback_list(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {"rbd": [{"scheduleId": "s3"}]},
        })
        assert _collect_schedules(coord, "rbd") == [{"scheduleId": "s3"}]

    def test_fallback_data_inner(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {"data": {"cfg": {"details": [{"scheduleId": "s4"}]}}},
        })
        assert _collect_schedules(coord, "cfg") == [{"scheduleId": "s4"}]

    def test_client_cache_fallback(self):
        coord = self._make_coordinator({"data": {}})
        coord.client._last_schedules = {"cfg": [{"scheduleId": "s5"}]}
        assert _collect_schedules(coord, "cfg") == [{"scheduleId": "s5"}]

    def test_empty_returns_empty(self):
        coord = self._make_coordinator(None)
        assert _collect_schedules(coord, "cfg") == []


# ---------------------------------------------------------------------------
# _mode_settings_from_data
# ---------------------------------------------------------------------------
class TestModeSettingsFromData:
    def _make_coordinator(self, data):
        coord = MagicMock()
        coord.data = data
        return coord

    def test_cfg_mode(self):
        coord = self._make_coordinator({
            "data": {"cfgControl": {"chargeFromGrid": True}}
        })
        result = _mode_settings_from_data(coord, "cfg")
        assert result == {"enabled": True}

    def test_dtg_mode_with_times(self):
        coord = self._make_coordinator({
            "data": {"dtgControl": {"enabled": True, "startTime": 480, "endTime": 1200}}
        })
        result = _mode_settings_from_data(coord, "dtg")
        assert result["enabled"] is True
        assert result["start_time"] == 480
        assert result["end_time"] == 1200

    def test_rbd_mode(self):
        coord = self._make_coordinator({
            "data": {"rbdControl": {"enabled": False}}
        })
        result = _mode_settings_from_data(coord, "rbd")
        assert result == {"enabled": False}

    def test_missing_control(self):
        coord = self._make_coordinator({"data": {}})
        result = _mode_settings_from_data(coord, "cfg")
        assert result == {}

    def test_none_enabled_returns_empty(self):
        coord = self._make_coordinator({
            "data": {"cfgControl": {"other": "value"}}
        })
        result = _mode_settings_from_data(coord, "cfg")
        assert result == {}

    def test_none_data(self):
        coord = self._make_coordinator(None)
        result = _mode_settings_from_data(coord, "cfg")
        assert result == {}
