from __future__ import annotations
import logging
import os
import json
import re
from datetime import datetime, timezone
import requests

_LOGGER = logging.getLogger(__name__)
SESSION = requests.Session()

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "auth.json")


class AuthError(Exception):
    """Authentication or token error."""


class EnphaseClient:
    """Handles Enphase Cloud authentication and API calls."""

    def __init__(self, email: str, password: str, user_id: str, battery_id: str):
        self.email = email
        self.password = password
        self.user_id = user_id
        self.battery_id = battery_id
        self.jwt_token: str | None = None
        self.xsrf_token: str | None = None
        self.cookies: dict | None = None
        self._load_cache()

    # -------------------------------------------------------------------------
    # CACHE
    # -------------------------------------------------------------------------

    def _load_cache(self):
        """Load cached JWT/XSRF tokens if present."""
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.jwt_token = data.get("jwt")
                    self.xsrf_token = data.get("xsrf")
                    self.cookies = data.get("cookies")
                    _LOGGER.debug("[Enphase] Loaded cached tokens")
        except Exception as exc:
            _LOGGER.warning("[Enphase] Failed to load cache: %s", exc)

    def _save_cache(self):
        """Persist JWT/XSRF tokens."""
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            data = {
                "jwt": self.jwt_token,
                "xsrf": self.xsrf_token,
                "cookies": self.cookies,
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
            _LOGGER.debug("[Enphase] Cache saved.")
        except Exception as exc:
            _LOGGER.warning("[Enphase] Failed to save cache: %s", exc)

    # -------------------------------------------------------------------------
    # AUTH
    # -------------------------------------------------------------------------

    def _csrf_login_token(self):
        """Get authenticity_token for login."""
        r = SESSION.get("https://enlighten.enphaseenergy.com/login", timeout=30)
        if not r.ok:
            raise AuthError("Failed to access login page.")
        match = re.search(
            r'name=["\']authenticity_token["\'][^>]*value=["\']([^"\']+)["\']', r.text
        )
        if not match:
            raise AuthError("Could not find authenticity_token on login page.")
        return match.group(1)

    def _login(self):
        """Perform login to retrieve JWT."""
        authenticity = self._csrf_login_token()
        payload = {
            "utf8": "✓",
            "authenticity_token": authenticity,
            "user[email]": self.email,
            "user[password]": self.password,
        }

        r = SESSION.post(
            "https://enlighten.enphaseenergy.com/login/login",
            data=payload,
            timeout=30,
        )
        if not r.ok:
            raise AuthError("Login failed.")

        jwt_resp = SESSION.get(
            "https://enlighten.enphaseenergy.com/app-api/jwt_token.json", timeout=30
        )
        jwt_json = jwt_resp.json()
        jwt_token = jwt_json.get("token")
        if not jwt_token:
            raise AuthError("JWT not found in response.")

        self.jwt_token = jwt_token
        _LOGGER.info("[Enphase] JWT retrieved successfully.")

        # get XSRF
        self._update_xsrf()
        self._save_cache()

    def _update_xsrf(self):
        """Fetch new XSRF token using JWT."""
        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"battery/sites/{self.battery_id}/schedules/isValid"
        )
        headers = {
            "content-type": "application/json",
            "origin": "https://battery-profile-ui.enphaseenergy.com",
            "referer": "https://battery-profile-ui.enphaseenergy.com/",
            "e-auth-token": self.jwt_token,
            "username": str(self.user_id),
        }
        payload = {"scheduleType": "dtg"}
        r = SESSION.post(url, json=payload, headers=headers, timeout=30)
        if "BP-XSRF-Token" in r.cookies:
            self.xsrf_token = r.cookies["BP-XSRF-Token"]
        elif "BP-XSRF-Token" in r.headers.get("Set-Cookie", ""):
            m = re.search(r"BP-XSRF-Token=([^;]+)", r.headers["Set-Cookie"])
            if m:
                self.xsrf_token = m.group(1)
        if not self.xsrf_token:
            raise AuthError("Failed to retrieve XSRF token.")
        _LOGGER.debug("[Enphase] XSRF token updated.")

    def _ensure_tokens(self, force_refresh=False):
        """Ensure JWT/XSRF tokens are present and valid."""
        if force_refresh or not self.jwt_token or not self.xsrf_token:
            _LOGGER.info("[Enphase] Refreshing authentication tokens.")
            self._login()
        return self.jwt_token, self.xsrf_token

    # -------------------------------------------------------------------------
    # DATA
    # -------------------------------------------------------------------------

    def battery_settings(self):
        """Fetch current battery configuration."""
        jwt, xsrf = self._ensure_tokens()
        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"batterySettings/{self.battery_id}?userId={self.user_id}&source=enho"
        )
        headers = {
            "content-type": "application/json",
            "e-auth-token": jwt,
            "x-xsrf-token": xsrf,
            "username": str(self.user_id),
            "cookie": f"BP-XSRF-Token={xsrf}",
        }
        r = SESSION.get(url, headers=headers, timeout=30)
        if r.status_code == 403:
            _LOGGER.warning("[Enphase] 403 Forbidden on battery_settings – refreshing XSRF.")
            jwt, xsrf = self._ensure_tokens(force_refresh=True)
            headers["e-auth-token"] = jwt
            headers["x-xsrf-token"] = xsrf
            headers["cookie"] = f"BP-XSRF-Token={xsrf}"
            r = SESSION.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        _LOGGER.debug("[Enphase] Battery settings fetched.")
        return r.json()

    # -------------------------------------------------------------------------
    # ACTIONS (toggles)
    # -------------------------------------------------------------------------

    def set_mode(self, mode: str, enable: bool):
        """
        Toggle Enphase battery control modes via the cloud API.

        Accepts either short names (cfg/dtg/rbd) or full keys (cfgControl/dtgControl/rbdControl).
        """
        valid_modes = ["cfg", "dtg", "rbd", "cfgControl", "dtgControl", "rbdControl"]
        if mode not in valid_modes:
            raise ValueError(f"Invalid mode: {mode}")

        # Normalise key
        short_mode = mode.replace("Control", "")
        _LOGGER.info("[Enphase] Setting mode '%s' -> %s", short_mode, enable)

        jwt, xsrf = self._ensure_tokens()
        headers = {
            "content-type": "application/json",
            "e-auth-token": jwt,
            "x-xsrf-token": xsrf,
            "username": str(self.user_id),
            "cookie": f"BP-XSRF-Token={xsrf}",
            "origin": "https://battery-profile-ui.enphaseenergy.com",
            "referer": "https://battery-profile-ui.enphaseenergy.com/",
        }

        # Payload mapping for each mode type
        if short_mode == "cfg":
            payload = {
                "chargeFromGrid": enable,
                "acceptedItcDisclaimer": self._now_iso(),
            }
        elif short_mode == "dtg":
            payload = {
                "dtgControl": {
                    "enabled": enable,
                    "scheduleSupported": True,
                }
            }
        elif short_mode == "rbd":
            payload = {"rbdControl": {"enabled": enable}}
        else:
            raise ValueError(f"Unsupported mode: {short_mode}")

        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"batterySettings/{self.battery_id}?userId={self.user_id}&source=enho"
        )

        r = SESSION.put(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 403:
            _LOGGER.warning("[Enphase] 403 Forbidden on set_mode(%s) – refreshing XSRF and retrying", short_mode)
            jwt, xsrf = self._ensure_tokens(force_refresh=True)
            headers["e-auth-token"] = jwt
            headers["x-xsrf-token"] = xsrf
            headers["cookie"] = f"BP-XSRF-Token={xsrf}"
            r = SESSION.put(url, json=payload, headers=headers, timeout=30)

        if not r.ok:
            _LOGGER.error("[Enphase] set_mode(%s) failed: %s %s", short_mode, r.status_code, r.text)
            r.raise_for_status()

        _LOGGER.info("[Enphase] Mode '%s' set successfully (HTTP %s)", short_mode, r.status_code)
        return True

    # -------------------------------------------------------------------------
    # SCHEDULE MANAGEMENT
    # -------------------------------------------------------------------------

    def get_schedules(self):
        """Return all schedules for this site/battery."""
        jwt, xsrf = self._ensure_tokens()
        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"battery/sites/{self.battery_id}/schedules"
        )
        headers = {
            "content-type": "application/json",
            "e-auth-token": jwt,
            "x-xsrf-token": xsrf,
            "username": str(self.user_id),
            "cookie": f"BP-XSRF-Token={xsrf}",
            "origin": "https://battery-profile-ui.enphaseenergy.com",
            "referer": "https://battery-profile-ui.enphaseenergy.com/",
        }
        r = SESSION.get(url, headers=headers, timeout=30)
        if r.status_code == 403:
            _LOGGER.warning("[Enphase] 403 on get_schedules – refreshing tokens.")
            jwt, xsrf = self._ensure_tokens(force_refresh=True)
            headers["e-auth-token"] = jwt
            headers["x-xsrf-token"] = xsrf
            headers["cookie"] = f"BP-XSRF-Token={xsrf}"
            r = SESSION.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def add_schedule(
        self,
        schedule_type,
        start_time,
        end_time,
        limit,
        days,
        timezone="UTC",
    ):
        """Add a new schedule entry (mirrors your REST command)."""
        jwt, xsrf = self._ensure_tokens()
        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"battery/sites/{self.battery_id}/schedules"
        )
        headers = {
            "content-type": "application/json",
            "e-auth-token": jwt,
            "x-xsrf-token": xsrf,
            "username": str(self.user_id),
            "cookie": f"BP-XSRF-Token={xsrf}",
            "origin": "https://battery-profile-ui.enphaseenergy.com",
            "referer": "https://battery-profile-ui.enphaseenergy.com/",
        }
        payload = {
            "timezone": timezone or "UTC",
            "startTime": start_time[:5],
            "endTime": end_time[:5],
            "limit": int(limit),
            "scheduleType": schedule_type,
            "days": [int(d) for d in days],
        }
        _LOGGER.info("[Enphase] Adding schedule: %s", payload)
        r = SESSION.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 403:
            jwt, xsrf = self._ensure_tokens(force_refresh=True)
            headers["e-auth-token"] = jwt
            headers["x-xsrf-token"] = xsrf
            headers["cookie"] = f"BP-XSRF-Token={xsrf}"
            r = SESSION.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        _LOGGER.info("[Enphase] Schedule added successfully.")
        return r.json()

    def delete_schedule(self, schedule_id):
        """Delete a schedule by ID (mirrors your REST command)."""
        jwt, xsrf = self._ensure_tokens()
        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"battery/sites/{self.battery_id}/schedules/{schedule_id}/delete"
        )
        headers = {
            "content-type": "application/json",
            "e-auth-token": jwt,
            "x-xsrf-token": xsrf,
            "username": str(self.user_id),
            "cookie": f"BP-XSRF-Token={xsrf}",
            "origin": "https://battery-profile-ui.enphaseenergy.com",
            "referer": "https://battery-profile-ui.enphaseenergy.com/",
        }
        _LOGGER.info("[Enphase] Deleting schedule ID %s", schedule_id)
        r = SESSION.post(url, json={}, headers=headers, timeout=30)
        if r.status_code == 403:
            jwt, xsrf = self._ensure_tokens(force_refresh=True)
            headers["e-auth-token"] = jwt
            headers["x-xsrf-token"] = xsrf
            headers["cookie"] = f"BP-XSRF-Token={xsrf}"
            r = SESSION.post(url, json={}, headers=headers, timeout=30)
        r.raise_for_status()
        _LOGGER.info("[Enphase] Schedule %s deleted successfully.", schedule_id)
        return True

    def validate_schedule(self, schedule_type="dtg", force_opted=False):
        """Validate schedule feasibility (isValid endpoint)."""
        jwt, xsrf = self._ensure_tokens()
        url = (
            f"https://enlighten.enphaseenergy.com/service/batteryConfig/api/v1/"
            f"battery/sites/{self.battery_id}/schedules/isValid"
        )
        payload = {"scheduleType": schedule_type}
        if schedule_type == "cfg" and force_opted:
            payload["forceScheduleOpted"] = True
        headers = {
            "content-type": "application/json",
            "e-auth-token": jwt,
            "x-xsrf-token": xsrf,
            "username": str(self.user_id),
            "cookie": f"BP-XSRF-Token={xsrf}",
            "origin": "https://battery-profile-ui.enphaseenergy.com",
            "referer": "https://battery-profile-ui.enphaseenergy.com/",
        }
        r = SESSION.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    # -------------------------------------------------------------------------
    # UTILS
    # -------------------------------------------------------------------------

    def _now_iso(self):
        """Return current UTC time in ISO format (milliseconds precision)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
