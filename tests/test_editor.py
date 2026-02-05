"""Tests for editor.py — pure data transformations."""

from __future__ import annotations

from datetime import time
from unittest.mock import MagicMock

import pytest

from custom_components.enphase_envoy_cloud_control.editor import (
    DAY_KEY_BY_INDEX,
    DAY_ORDER,
    _collect_schedules,
    _normalize_days,
    _normalize_time,
    days_list_from_editor,
    default_day_flags,
    default_editor_state,
    default_new_editor_state,
    editor_days_from_list,
    normalize_schedules,
)


# ---------------------------------------------------------------------------
# default_day_flags
# ---------------------------------------------------------------------------
class TestDefaultDayFlags:
    def test_all_false(self):
        flags = default_day_flags()
        assert all(v is False for v in flags.values())

    def test_keys(self):
        flags = default_day_flags()
        expected_keys = [key for key, _ in DAY_ORDER]
        assert list(flags.keys()) == expected_keys


# ---------------------------------------------------------------------------
# default_editor_state / default_new_editor_state
# ---------------------------------------------------------------------------
class TestDefaultStates:
    def test_editor_state_keys(self):
        state = default_editor_state()
        assert "selected_schedule_id" in state
        assert state["schedule_type"] == "cfg"
        assert state["start_time"] == "00:00"
        assert state["end_time"] == "00:00"
        assert state["limit"] == 0
        assert isinstance(state["days"], dict)

    def test_new_editor_state_keys(self):
        state = default_new_editor_state()
        assert "selected_schedule_id" not in state
        assert state["schedule_type"] == "cfg"
        assert isinstance(state["days"], dict)

    def test_editor_state_independence(self):
        s1 = default_editor_state()
        s2 = default_editor_state()
        s1["limit"] = 99
        assert s2["limit"] == 0


# ---------------------------------------------------------------------------
# editor_days_from_list / days_list_from_editor
# ---------------------------------------------------------------------------
class TestDayConversions:
    def test_round_trip(self):
        original = [1, 3, 5, 7]
        flags = editor_days_from_list(original)
        result = days_list_from_editor(flags)
        assert result == original

    def test_empty_list(self):
        flags = editor_days_from_list([])
        assert all(v is False for v in flags.values())
        assert days_list_from_editor(flags) == []

    def test_all_days(self):
        flags = editor_days_from_list([1, 2, 3, 4, 5, 6, 7])
        assert all(flags.values())
        assert days_list_from_editor(flags) == [1, 2, 3, 4, 5, 6, 7]

    def test_invalid_day_ignored(self):
        flags = editor_days_from_list([0, 8, 99])
        assert all(v is False for v in flags.values())

    def test_single_day(self):
        flags = editor_days_from_list([3])
        assert flags["wed"] is True
        assert sum(flags.values()) == 1


# ---------------------------------------------------------------------------
# _normalize_time
# ---------------------------------------------------------------------------
class TestNormalizeTime:
    def test_time_object(self):
        assert _normalize_time(time(14, 30)) == "14:30"

    def test_time_midnight(self):
        assert _normalize_time(time(0, 0)) == "00:00"

    def test_none(self):
        assert _normalize_time(None) == "00:00"

    def test_int(self):
        assert _normalize_time(8) == "08:00"

    def test_float(self):
        assert _normalize_time(23.5) == "23:00"

    def test_string_hhmm(self):
        assert _normalize_time("09:45") == "09:45"

    def test_string_with_seconds(self):
        assert _normalize_time("09:45:30") == "09:45"

    def test_string_embedded(self):
        assert _normalize_time("time is 14:30 today") == "14:30"

    def test_short_string_no_match(self):
        result = _normalize_time("abc")
        assert result == "abc"[:5]


# ---------------------------------------------------------------------------
# _normalize_days
# ---------------------------------------------------------------------------
class TestNormalizeDays:
    def test_list_of_ints(self):
        assert _normalize_days([3, 1, 5]) == [1, 3, 5]

    def test_dict_with_enabled(self):
        raw = {"1": True, "3": True, "5": False}
        assert _normalize_days(raw) == [1, 3]

    def test_string_csv(self):
        assert _normalize_days("1,3,5") == [1, 3, 5]

    def test_string_space_separated(self):
        assert _normalize_days("2 4 6") == [2, 4, 6]

    def test_empty_list(self):
        assert _normalize_days([]) == []

    def test_none(self):
        assert _normalize_days(None) == []

    def test_empty_string(self):
        assert _normalize_days("") == []

    def test_out_of_range_filtered(self):
        assert _normalize_days([0, 1, 8, 3]) == [1, 3]

    def test_duplicates_removed(self):
        assert _normalize_days([1, 1, 3, 3]) == [1, 3]

    def test_tuple_input(self):
        assert _normalize_days((5, 2, 7)) == [2, 5, 7]

    def test_set_input(self):
        result = _normalize_days({1, 4})
        assert sorted(result) == [1, 4]

    def test_non_digit_values_skipped(self):
        assert _normalize_days(["Mon", "1", "abc", "3"]) == [1, 3]

    def test_dict_non_digit_keys_ignored(self):
        raw = {"mon": True, "1": True, "abc": True}
        assert _normalize_days(raw) == [1]


# ---------------------------------------------------------------------------
# _collect_schedules — 4-level fallback
# ---------------------------------------------------------------------------
class TestCollectSchedules:
    def _make_coordinator(self, data):
        coord = MagicMock()
        coord.data = data
        coord.client = MagicMock(spec=[])  # no _last_schedules by default
        return coord

    def test_primary_path(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {
                    "schedules": [{"scheduleId": "s1"}]
                }
            }
        })
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s1"}]

    def test_fallback_schedules_dict_details(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {
                "cfg": {"details": [{"scheduleId": "s2"}]}
            },
        })
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s2"}]

    def test_fallback_schedules_list(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {
                "cfg": [{"scheduleId": "s3"}]
            },
        })
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s3"}]

    def test_fallback_schedules_data_inner(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {
                "data": {
                    "cfg": {"details": [{"scheduleId": "s4"}]}
                }
            },
        })
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s4"}]

    def test_fallback_schedules_data_inner_list(self):
        coord = self._make_coordinator({
            "data": {},
            "schedules": {
                "data": {
                    "cfg": [{"scheduleId": "s5"}]
                }
            },
        })
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s5"}]

    def test_fallback_client_cache_details(self):
        coord = self._make_coordinator({"data": {}})
        coord.client._last_schedules = {
            "cfg": {"details": [{"scheduleId": "s6"}]}
        }
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s6"}]

    def test_fallback_client_cache_list(self):
        coord = self._make_coordinator({"data": {}})
        coord.client._last_schedules = {
            "cfg": [{"scheduleId": "s7"}]
        }
        result = _collect_schedules(coord, "cfg")
        assert result == [{"scheduleId": "s7"}]

    def test_returns_empty_when_no_data(self):
        coord = self._make_coordinator(None)
        result = _collect_schedules(coord, "cfg")
        assert result == []

    def test_returns_empty_when_empty_data(self):
        coord = self._make_coordinator({"data": {}})
        result = _collect_schedules(coord, "cfg")
        assert result == []


# ---------------------------------------------------------------------------
# normalize_schedules
# ---------------------------------------------------------------------------
class TestNormalizeSchedules:
    def _make_coordinator(self, data):
        coord = MagicMock()
        coord.data = data
        coord.client = MagicMock(spec=[])
        return coord

    def test_basic_normalization(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {
                    "schedules": [
                        {
                            "scheduleId": "abc123",
                            "scheduleType": "CFG",
                            "startTime": "06:00",
                            "endTime": "10:00",
                            "limit": 80,
                            "days": [1, 2, 3],
                        }
                    ]
                }
            }
        })
        result = normalize_schedules(coord)
        assert len(result) == 1
        assert result[0]["id"] == "abc123"
        assert result[0]["type"] == "cfg"
        assert result[0]["start"] == "06:00"
        assert result[0]["end"] == "10:00"
        assert result[0]["limit"] == 80
        assert result[0]["days"] == [1, 2, 3]

    def test_skips_entries_without_schedule_id(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {
                    "schedules": [
                        {"startTime": "00:00", "endTime": "01:00"},  # no scheduleId
                    ]
                }
            }
        })
        result = normalize_schedules(coord)
        assert result == []

    def test_multiple_modes(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {"schedules": [{"scheduleId": "s1", "scheduleType": "cfg"}]},
                "rbdControl": {"schedules": [{"scheduleId": "s2", "scheduleType": "rbd"}]},
            }
        })
        result = normalize_schedules(coord)
        assert len(result) == 2
        ids = [r["id"] for r in result]
        assert "s1" in ids
        assert "s2" in ids

    def test_powerLimit_fallback(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {
                    "schedules": [
                        {"scheduleId": "s1", "powerLimit": 50}
                    ]
                }
            }
        })
        result = normalize_schedules(coord)
        assert result[0]["limit"] == 50

    def test_daysOfWeek_fallback(self):
        coord = self._make_coordinator({
            "data": {
                "cfgControl": {
                    "schedules": [
                        {"scheduleId": "s1", "daysOfWeek": [6, 7]}
                    ]
                }
            }
        })
        result = normalize_schedules(coord)
        assert result[0]["days"] == [6, 7]

    def test_type_defaults_to_mode(self):
        coord = self._make_coordinator({
            "data": {
                "dtgControl": {
                    "schedules": [{"scheduleId": "s1"}]
                }
            }
        })
        result = normalize_schedules(coord)
        assert result[0]["type"] == "dtg"

    def test_empty_data(self):
        coord = self._make_coordinator(None)
        assert normalize_schedules(coord) == []
