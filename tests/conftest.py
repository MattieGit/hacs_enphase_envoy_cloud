"""Shared fixtures for Enphase Envoy Cloud Control tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ENTRY_ID = "test_entry_id_123"

SAMPLE_BATTERY_DATA = {
    "data": {
        "cfgControl": {
            "chargeFromGrid": True,
            "scheduleSupported": True,
            "schedules": [
                {
                    "scheduleId": "sched-cfg-1",
                    "startTime": "06:00",
                    "endTime": "10:00",
                    "limit": 80,
                    "days": [1, 2, 3, 4, 5],
                }
            ],
        },
        "dtgControl": {
            "enabled": False,
            "scheduleSupported": True,
            "startTime": 780,
            "endTime": 1080,
            "schedules": [],
        },
        "rbdControl": {
            "enabled": True,
            "schedules": [
                {
                    "scheduleId": "sched-rbd-1",
                    "startTime": "22:00",
                    "endTime": "06:00",
                    "days": [6, 7],
                }
            ],
        },
        "otherField": "some_value",
    }
}

SAMPLE_SCHEDULES_DATA = {
    "data": {
        "cfg": {
            "details": [
                {
                    "scheduleId": "sched-cfg-1",
                    "scheduleType": "cfg",
                    "startTime": "06:00",
                    "endTime": "10:00",
                    "limit": 80,
                    "days": [1, 2, 3, 4, 5],
                }
            ]
        },
        "dtg": {"details": []},
        "rbd": {
            "details": [
                {
                    "scheduleId": "sched-rbd-1",
                    "scheduleType": "rbd",
                    "startTime": "22:00",
                    "endTime": "06:00",
                    "days": [6, 7],
                }
            ]
        },
    }
}

SAMPLE_COORDINATOR_DATA = {
    "data": SAMPLE_BATTERY_DATA["data"],
    "schedules": SAMPLE_SCHEDULES_DATA["data"],
    "schedules_raw": SAMPLE_SCHEDULES_DATA,
}


@pytest.fixture
def mock_entry():
    """Create a mock ConfigEntry."""
    entry = MagicMock()
    entry.entry_id = ENTRY_ID
    entry.data = {
        "email": "test@example.com",
        "password": "secret",
        "user_id": "12345",
        "battery_id": "67890",
    }
    entry.options = {"poll_interval": 30}
    return entry


@pytest.fixture
def mock_client():
    """Create a mock EnphaseClient."""
    client = MagicMock()
    client.email = "test@example.com"
    client.password = "secret"
    client.user_id = "12345"
    client.battery_id = "67890"
    client.jwt_token = "fake.jwt.token"
    client.xsrf_token = "fake-xsrf"
    client.battery_settings.return_value = SAMPLE_BATTERY_DATA
    client.get_schedules.return_value = SAMPLE_SCHEDULES_DATA
    client.add_schedule.return_value = {"scheduleId": "new-sched-id"}
    client.delete_schedule.return_value = True
    client.set_mode.return_value = True
    client.validate_schedule.return_value = {"valid": True}
    client.ensure_authenticated.return_value = {"user_id": "12345", "battery_id": "67890"}
    client._last_schedules = SAMPLE_SCHEDULES_DATA
    return client


@pytest.fixture
def mock_coordinator(mock_entry, mock_client):
    """Create a mock EnphaseCoordinator."""
    coordinator = MagicMock()
    coordinator.entry = mock_entry
    coordinator.client = mock_client
    coordinator.data = SAMPLE_COORDINATOR_DATA
    coordinator.hass = MagicMock()
    coordinator.hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_force_refresh = AsyncMock()
    coordinator.last_update_success_time = None
    return coordinator


@pytest.fixture
def mock_hass(mock_coordinator):
    """Create a lightweight mock HomeAssistant."""
    from custom_components.enphase_envoy_cloud_control.editor import (
        default_editor_state,
        default_new_editor_state,
    )
    from custom_components.enphase_envoy_cloud_control.const import DOMAIN

    hass = MagicMock()
    hass.data = {
        DOMAIN: {
            ENTRY_ID: {
                "coordinator": mock_coordinator,
                "editor": default_editor_state(),
                "new_editor": default_new_editor_state(),
            }
        }
    }
    hass.config.time_zone = "UTC"
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
    hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close() if hasattr(coro, 'close') else None)
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.loop = MagicMock()
    return hass


@pytest.fixture
def editor_state(mock_hass):
    """Convenience access to the editor state dict."""
    from custom_components.enphase_envoy_cloud_control.const import DOMAIN
    return mock_hass.data[DOMAIN][ENTRY_ID]["editor"]


@pytest.fixture
def new_editor_state(mock_hass):
    """Convenience access to the new editor state dict."""
    from custom_components.enphase_envoy_cloud_control.const import DOMAIN
    return mock_hass.data[DOMAIN][ENTRY_ID]["new_editor"]
