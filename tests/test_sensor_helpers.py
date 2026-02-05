"""Tests for sensor.py — _format_days() helper."""

from custom_components.enphase_envoy_cloud_control.sensor import _format_days


def test_every_day():
    assert _format_days([1, 2, 3, 4, 5, 6, 7]) == "Every day"


def test_mon_fri():
    assert _format_days([1, 2, 3, 4, 5]) == "Mon-Fri"


def test_sat_sun():
    assert _format_days([6, 7]) == "Sat-Sun"


def test_consecutive_range():
    assert _format_days([2, 3, 4]) == "Tue-Thu"


def test_non_consecutive():
    assert _format_days([1, 3, 5]) == "Mon, Wed, Fri"


def test_single_day():
    assert _format_days([3]) == "Wed"


def test_duplicates_collapsed():
    assert _format_days([1, 1, 2, 2, 3]) == "Mon-Wed"


def test_empty():
    assert _format_days([]) == ""


def test_unsorted_input():
    assert _format_days([5, 3, 1]) == "Mon, Wed, Fri"


def test_two_non_consecutive():
    assert _format_days([1, 7]) == "Mon, Sun"
