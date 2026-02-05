"""Timed battery mode control — enable a mode for a fixed duration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORE_KEY = f"{DOMAIN}_timed_modes"
STORE_VERSION = 1


MODE_NAMES = {"cfg": "Charge from Grid", "dtg": "Discharge to Grid", "rbd": "Restrict Battery Discharge"}


def _timed_modes(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    """Return the timed_modes dict for an entry, creating it if needed."""
    entry_data = hass.data[DOMAIN][entry_id]
    if "timed_modes" not in entry_data:
        entry_data["timed_modes"] = {}
    return entry_data["timed_modes"]


def get_active_timed_mode(hass: HomeAssistant, entry_id: str) -> dict[str, Any] | None:
    """Return info about the currently active timed mode, or None."""
    timed = _timed_modes(hass, entry_id)
    for mode, info in timed.items():
        expires_at_str = info.get("expires_at")
        if not expires_at_str:
            continue
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at > datetime.now(timezone.utc):
            remaining = expires_at - datetime.now(timezone.utc)
            remaining_minutes = max(1, int(remaining.total_seconds() / 60))
            return {
                "mode": mode,
                "mode_name": info.get("mode_name", mode.upper()),
                "remaining_minutes": remaining_minutes,
                "expires_at": expires_at_str,
                "schedule_id": info.get("schedule_id"),
            }
    return None


def _calculate_schedule_times(
    duration_minutes: int,
    tz_name: str = "UTC",
) -> tuple[str, str, list[int]]:
    """Calculate start time, end time and ISO weekday list for a timed schedule.

    Returns (start_HH:MM, end_HH:MM, days) where days uses ISO weekday
    numbering (1=Monday .. 7=Sunday).  Handles midnight crossing.
    Times are in the given timezone so they match what the API expects.
    """
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    now = datetime.now(tz)
    end = now + timedelta(minutes=duration_minutes)

    start_str = now.strftime("%H:%M")
    end_str = end.strftime("%H:%M")

    start_day = now.isoweekday()  # 1=Mon .. 7=Sun
    end_day = end.isoweekday()

    days = sorted({start_day, end_day})
    return start_str, end_str, days


async def _save_store(hass: HomeAssistant, entry_id: str) -> None:
    """Persist active timed modes to disk for restart recovery."""
    timed = _timed_modes(hass, entry_id)
    store = Store(hass, STORE_VERSION, f"{STORE_KEY}_{entry_id}")
    data = {
        mode: {
            "schedule_id": info["schedule_id"],
            "mode": mode,
            "expires_at": info.get("expires_at"),
            "mode_name": info.get("mode_name"),
        }
        for mode, info in timed.items()
        if info.get("schedule_id")
    }
    await store.async_save(data)


async def _clear_store(hass: HomeAssistant, entry_id: str) -> None:
    """Remove persisted timed mode data."""
    store = Store(hass, STORE_VERSION, f"{STORE_KEY}_{entry_id}")
    await store.async_remove()


async def enable_timed_mode(
    hass: HomeAssistant,
    entry_id: str,
    mode: str,
    duration_minutes: int,
) -> None:
    """Enable a battery mode for *duration_minutes*, then auto-disable.

    1. Cancel any existing timed mode for this mode type.
    2. Create a temporary schedule via the Enphase API.
    3. Enable the mode.
    4. Set a timer to clean up when the duration expires.
    """
    from .editor import get_coordinator  # local to avoid circular import

    coordinator = get_coordinator(hass, entry_id)
    client = coordinator.client
    timed = _timed_modes(hass, entry_id)

    # Cancel existing timed mode for this mode if active
    await cancel_timed_mode(hass, entry_id, mode, disable_mode=True)

    tz = hass.config.time_zone or "UTC"
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo(tz) if tz else timezone.utc)
    expires_at = now + timedelta(minutes=duration_minutes)
    start_str, end_str, days = _calculate_schedule_times(duration_minutes, tz)

    _LOGGER.info(
        "[Enphase] Enabling timed %s: %s–%s days=%s (%d min)",
        mode, start_str, end_str, days, duration_minutes,
    )

    # Add schedule
    result = await hass.async_add_executor_job(
        client.add_schedule, mode, start_str, end_str, 100, days, tz,
    )

    # Extract schedule ID from the response
    schedule_id: str | None = None
    if isinstance(result, dict):
        schedule_id = result.get("scheduleId") or result.get("id")
    if not schedule_id:
        # Refresh schedules and find the new one by matching times
        await coordinator.async_request_refresh()
        _LOGGER.warning(
            "[Enphase] Could not extract schedule ID from add_schedule response; "
            "cleanup may require manual deletion."
        )

    # Wait for the schedule to propagate in the Enphase API
    await asyncio.sleep(2)

    # Enable the mode (only dtg accepts start/end times in set_mode)
    await hass.async_add_executor_job(
        client.set_mode, mode, True,
        start_str if mode == "dtg" else None,
        end_str if mode == "dtg" else None,
    )

    # Set up expiry timer
    cancel: CALLBACK_TYPE = async_call_later(
        hass,
        duration_minutes * 60,
        lambda _now: hass.async_create_task(
            _on_timed_mode_expired(hass, entry_id, mode)
        ),
    )

    timed[mode] = {
        "schedule_id": schedule_id,
        "cancel": cancel,
        "expires_at": expires_at.isoformat(),
        "mode_name": MODE_NAMES.get(mode, mode.upper()),
    }

    await _save_store(hass, entry_id)

    # Refresh so entities pick up the new schedule
    async_call_later(
        hass, 5,
        lambda _: hass.async_create_task(coordinator.async_request_refresh()),
    )


async def _on_timed_mode_expired(
    hass: HomeAssistant, entry_id: str, mode: str
) -> None:
    """Timer callback: delete the temporary schedule and disable the mode."""
    _LOGGER.info("[Enphase] Timed %s expired — cleaning up.", mode)
    await cancel_timed_mode(hass, entry_id, mode, disable_mode=True)


async def cancel_timed_mode(
    hass: HomeAssistant,
    entry_id: str,
    mode: str,
    *,
    disable_mode: bool = True,
) -> None:
    """Cancel an active timed mode: delete schedule, optionally disable mode."""
    from .editor import get_coordinator

    timed = _timed_modes(hass, entry_id)
    info = timed.pop(mode, None)
    if info is None:
        return

    # Cancel the pending timer if it hasn't fired yet
    cancel_cb = info.get("cancel")
    if callable(cancel_cb):
        cancel_cb()

    coordinator = get_coordinator(hass, entry_id)
    client = coordinator.client

    # Delete the temporary schedule
    schedule_id = info.get("schedule_id")
    if schedule_id:
        try:
            await hass.async_add_executor_job(client.delete_schedule, schedule_id)
            _LOGGER.info("[Enphase] Deleted timed schedule %s for %s.", schedule_id, mode)
        except Exception as exc:
            _LOGGER.error(
                "[Enphase] Failed to delete timed schedule %s: %s", schedule_id, exc
            )

    # Disable the mode (skip if the user already turned it off)
    if disable_mode:
        try:
            data = coordinator.data or {}
            control = data.get("data", {}).get(f"{mode}Control", {})
            if mode == "cfg":
                currently_on = control.get("chargeFromGrid", False)
            else:
                currently_on = control.get("enabled", False)
            if currently_on:
                await hass.async_add_executor_job(client.set_mode, mode, False)
                _LOGGER.info("[Enphase] Disabled %s after timed mode expiry.", mode)
        except Exception as exc:
            _LOGGER.error("[Enphase] Failed to disable %s: %s", mode, exc)

    await _save_store(hass, entry_id)

    # Refresh
    async_call_later(
        hass, 5,
        lambda _: hass.async_create_task(coordinator.async_request_refresh()),
    )


async def cancel_all_timed_modes(
    hass: HomeAssistant, entry_id: str, *, disable_modes: bool = True
) -> None:
    """Cancel all active timed modes for an entry (used on unload)."""
    timed = _timed_modes(hass, entry_id)
    for mode in list(timed.keys()):
        await cancel_timed_mode(hass, entry_id, mode, disable_mode=disable_modes)
    await _clear_store(hass, entry_id)


async def recover_timed_modes(hass: HomeAssistant, entry_id: str) -> None:
    """On startup, clean up any orphaned timed schedules from a previous run."""
    store = Store(hass, STORE_VERSION, f"{STORE_KEY}_{entry_id}")
    data = await store.async_load()
    if not data or not isinstance(data, dict):
        return

    from .editor import get_coordinator

    coordinator = get_coordinator(hass, entry_id)
    client = coordinator.client

    _LOGGER.info("[Enphase] Recovering %d orphaned timed mode(s).", len(data))
    for mode, info in data.items():
        schedule_id = info.get("schedule_id") if isinstance(info, dict) else None
        if schedule_id:
            try:
                await hass.async_add_executor_job(client.delete_schedule, schedule_id)
                _LOGGER.info("[Enphase] Cleaned up orphaned schedule %s (%s).", schedule_id, mode)
            except Exception as exc:
                _LOGGER.warning(
                    "[Enphase] Could not delete orphaned schedule %s: %s", schedule_id, exc
                )
        try:
            await hass.async_add_executor_job(client.set_mode, mode, False)
        except Exception as exc:
            _LOGGER.warning("[Enphase] Could not disable orphaned mode %s: %s", mode, exc)

    await _clear_store(hass, entry_id)
