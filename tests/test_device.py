"""Tests for device.py — pure device info functions."""

from custom_components.enphase_envoy_cloud_control.const import (
    DEVICE_KIND_SCHEDULE_EDITOR,
    DOMAIN,
)
from custom_components.enphase_envoy_cloud_control.device import (
    battery_device_info,
    schedule_editor_device_info,
)


def test_battery_device_info_identifiers():
    info = battery_device_info("entry1")
    assert info["identifiers"] == {(DOMAIN, "entry1")}


def test_battery_device_info_fields():
    info = battery_device_info("entry1")
    assert info["name"] == "Enphase Battery"
    assert info["manufacturer"] == "Enphase"
    assert info["model"] == "IQ Battery"


def test_schedule_editor_device_info_identifiers():
    info = schedule_editor_device_info("entry1")
    assert info["identifiers"] == {(DOMAIN, "entry1", DEVICE_KIND_SCHEDULE_EDITOR)}


def test_schedule_editor_device_info_via_device():
    info = schedule_editor_device_info("entry1")
    assert info["via_device"] == (DOMAIN, "entry1")
    assert info["name"] == "Enphase Schedule Editor"
    assert info["manufacturer"] == "Enphase"
    assert info["model"] == "Schedule Editor"
