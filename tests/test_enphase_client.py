"""Tests for enphase_client.py — HTTP client and pure utility methods."""

from __future__ import annotations

import base64
import json
import time as _time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from custom_components.enphase_envoy_cloud_control.enphase_client import (
    AuthError,
    EnphaseClient,
)


# ---------------------------------------------------------------------------
# Helper to create a valid-looking JWT for testing
# ---------------------------------------------------------------------------
def _make_jwt(payload: dict | None = None, exp: int | None = None) -> str:
    """Create a fake JWT with the given payload."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    if payload is None:
        payload = {}
    if exp is not None:
        payload["exp"] = exp
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(b"fakesig").decode().rstrip("=")
    return f"{header}.{body}.{sig}"


@pytest.fixture
def client():
    """Create a fresh EnphaseClient."""
    return EnphaseClient("test@example.com", "secret", "12345", "67890")


# ---------------------------------------------------------------------------
# Pure methods (no HTTP)
# ---------------------------------------------------------------------------
class TestTimeToMinutes:
    def test_hhmm_string(self, client):
        assert client._time_to_minutes("14:30") == 870

    def test_midnight(self, client):
        assert client._time_to_minutes("00:00") == 0

    def test_end_of_day(self, client):
        assert client._time_to_minutes("23:59") == 1439

    def test_int_passthrough(self, client):
        assert client._time_to_minutes(600) == 600

    def test_invalid_raises(self, client):
        with pytest.raises(ValueError):
            client._time_to_minutes("abc")

    def test_single_digit_hour(self, client):
        assert client._time_to_minutes("9:05") == 545


class TestB64urlDecode:
    def test_standard(self, client):
        text = "hello world"
        encoded = base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")
        assert client._b64url_decode(encoded) == text

    def test_with_padding(self, client):
        text = "test"
        encoded = base64.urlsafe_b64encode(text.encode()).decode()
        assert client._b64url_decode(encoded) == text

    def test_invalid_returns_empty(self, client):
        # bytes that can't be decoded as utf-8
        assert client._b64url_decode("!!!") == ""


class TestJwtPayloadJson:
    def test_valid_jwt(self, client):
        jwt = _make_jwt({"sub": "user1", "exp": 99999})
        result = client._jwt_payload_json(jwt)
        assert result["sub"] == "user1"
        assert result["exp"] == 99999

    def test_no_dots_returns_empty(self, client):
        assert client._jwt_payload_json("nodots") == {}

    def test_invalid_base64_returns_empty(self, client):
        assert client._jwt_payload_json("a.!!!.c") == {}


class TestJwtExp:
    def test_valid(self, client):
        jwt = _make_jwt(exp=1700000000)
        assert client._jwt_exp(jwt) == 1700000000

    def test_missing_exp(self, client):
        jwt = _make_jwt({"sub": "test"})
        assert client._jwt_exp(jwt) is None

    def test_invalid_jwt(self, client):
        assert client._jwt_exp("not.a.jwt") is None


class TestJwtValid:
    def test_no_token(self, client):
        client.jwt_token = None
        assert client._jwt_valid() is False

    def test_expired_token(self, client):
        # Set exp to 1 hour ago — fails the 1-hour grace check
        past_exp = int(datetime.now(timezone.utc).timestamp()) - 3600
        client.jwt_token = _make_jwt(exp=past_exp)
        client.jwt_exp = past_exp
        assert client._jwt_valid() is False

    def test_valid_token(self, client):
        # Set exp far in the future
        future_exp = int(datetime.now(timezone.utc).timestamp()) + 7200
        client.jwt_token = _make_jwt(exp=future_exp)
        client.jwt_exp = future_exp
        assert client._jwt_valid() is True

    def test_token_within_grace_period(self, client):
        # exp exactly 30 min from now — within 1h grace, so invalid
        near_exp = int(datetime.now(timezone.utc).timestamp()) + 1800
        client.jwt_token = _make_jwt(exp=near_exp)
        client.jwt_exp = near_exp
        assert client._jwt_valid() is False


class TestNowIso:
    def test_format(self, client):
        result = client._now_iso()
        assert result.endswith("Z")
        assert "T" in result
        # Verify it parses
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# API methods — patch SESSION
# ---------------------------------------------------------------------------
class TestBatterySettings:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_success(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"data": {"cfgControl": {}}}
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.battery_settings()
        assert result == {"data": {"cfgControl": {}}}

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_403_retry(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        forbidden = MagicMock()
        forbidden.status_code = 403
        forbidden.ok = False

        success = MagicMock()
        success.status_code = 200
        success.ok = True
        success.json.return_value = {"data": {}}
        success.raise_for_status = MagicMock()

        mock_session.get.side_effect = [forbidden, success]
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True
        mock_session.cookies.__contains__ = lambda self, key: key == "BP-XSRF-Token"
        mock_session.cookies.__getitem__ = lambda self, key: "new-xsrf"
        mock_session.post.return_value = MagicMock(headers={}, cookies={})

        # Need to patch _login to avoid real HTTP
        with patch.object(client, "_login"):
            result = client.battery_settings()
            assert result == {"data": {}}


class TestSetMode:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_cfg_mode(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status = MagicMock()
        mock_session.put.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.set_mode("cfg", True)
        assert result is True
        call_kwargs = mock_session.put.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "cfgControl" in payload
        assert payload["cfgControl"]["chargeFromGrid"] is True

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_dtg_mode_with_times(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status = MagicMock()
        mock_session.put.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.set_mode("dtg", True, start_time="08:00", end_time="20:00")
        assert result is True
        call_kwargs = mock_session.put.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "dtgControl" in payload
        assert payload["dtgControl"]["enabled"] is True
        assert payload["dtgControl"]["startTime"] == 480
        assert payload["dtgControl"]["endTime"] == 1200

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_rbd_mode(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status = MagicMock()
        mock_session.put.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.set_mode("rbd", False)
        assert result is True
        call_kwargs = mock_session.put.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "rbdControl" in payload
        assert payload["rbdControl"]["enabled"] is False

    def test_invalid_mode(self, client):
        with pytest.raises(ValueError, match="Invalid mode"):
            client.set_mode("invalid", True)

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_403_retry(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        forbidden = MagicMock()
        forbidden.status_code = 403
        forbidden.ok = False
        forbidden.text = "Forbidden"

        success = MagicMock()
        success.status_code = 200
        success.ok = True
        success.raise_for_status = MagicMock()
        success.text = "OK"

        mock_session.put.side_effect = [forbidden, success]
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True
        mock_session.cookies.__contains__ = lambda self, key: key == "BP-XSRF-Token"
        mock_session.cookies.__getitem__ = lambda self, key: "new-xsrf"
        mock_session.post.return_value = MagicMock(headers={}, cookies={})

        with patch.object(client, "_login"):
            result = client.set_mode("rbd", True)
            assert result is True


class TestGetSchedules:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_success(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"data": {"cfg": {"details": []}}}
        mock_resp.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.get_schedules()
        assert "data" in result

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_403_retry(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        forbidden = MagicMock()
        forbidden.status_code = 403

        success = MagicMock()
        success.status_code = 200
        success.ok = True
        success.json.return_value = {}
        success.raise_for_status = MagicMock()

        mock_session.get.side_effect = [forbidden, success]
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True
        mock_session.cookies.__contains__ = lambda self, key: key == "BP-XSRF-Token"
        mock_session.cookies.__getitem__ = lambda self, key: "new-xsrf"
        mock_session.post.return_value = MagicMock(headers={}, cookies={})

        with patch.object(client, "_login"):
            result = client.get_schedules()
            assert result == {}


class TestAddSchedule:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_success(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"scheduleId": "new-id"}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = '{"scheduleId": "new-id"}'
        mock_session.post.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.add_schedule("cfg", "06:00", "10:00", 80, [1, 2, 3])
        assert result["scheduleId"] == "new-id"

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_schedule_type_uppercased(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "{}"
        mock_session.post.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        client.add_schedule("cfg", "06:00", "10:00", 80, [1])
        call_kwargs = mock_session.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["scheduleType"] == "CFG"


class TestDeleteSchedule:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_success(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "OK"
        mock_session.post.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.delete_schedule("sched-123")
        assert result is True

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_403_retry(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        forbidden = MagicMock()
        forbidden.status_code = 403
        forbidden.text = "Forbidden"

        success = MagicMock()
        success.status_code = 200
        success.ok = True
        success.raise_for_status = MagicMock()
        success.text = "OK"

        mock_session.post.side_effect = [forbidden, MagicMock(headers={}, cookies={}), success]
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True
        mock_session.cookies.__contains__ = lambda self, key: key == "BP-XSRF-Token"
        mock_session.cookies.__getitem__ = lambda self, key: "new-xsrf"
        mock_session.get.return_value = MagicMock(
            url="https://enlighten.enphaseenergy.com/web/12345",
            json=MagicMock(return_value={"app": {"userId": "12345"}}),
            ok=True,
        )

        with patch.object(client, "_login"):
            result = client.delete_schedule("sched-456")
            assert result is True


class TestValidateSchedule:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_success(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"valid": True}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = '{"valid": true}'
        mock_session.post.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        result = client.validate_schedule("dtg")
        assert result["valid"] is True

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_cfg_with_force_opted(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = int(datetime.now(timezone.utc).timestamp()) + 7200

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.ok = True
        mock_resp.json.return_value = {"valid": True}
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = '{"valid": true}'
        mock_session.post.return_value = mock_resp
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        client.validate_schedule("cfg", force_opted=True)
        call_kwargs = mock_session.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["scheduleType"] == "CFG"
        assert payload["forceScheduleOpted"] is True


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------
class TestEnsureTokens:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_calls_login_when_jwt_invalid(self, mock_session, client):
        client.jwt_token = None
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: False

        with patch.object(client, "_login") as mock_login:
            with patch.object(client, "_save_cache"):
                mock_login.side_effect = lambda: setattr(client, "jwt_token", "new_jwt") or setattr(client, "xsrf_token", "new_xsrf")
                jwt, xsrf = client._ensure_tokens()
                mock_login.assert_called_once()

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_force_refresh(self, mock_session, client):
        future_exp = int(datetime.now(timezone.utc).timestamp()) + 7200
        client.jwt_token = _make_jwt(exp=future_exp)
        client.jwt_exp = future_exp
        client.xsrf_token = "xsrf"
        mock_session.cookies = MagicMock()
        mock_session.cookies.__bool__ = lambda self: True

        with patch.object(client, "_login") as mock_login:
            with patch.object(client, "_save_cache"):
                mock_login.side_effect = lambda: None
                client._ensure_tokens(force_refresh=True)
                mock_login.assert_called_once()


class TestLoadCache:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    @patch("os.path.exists", return_value=True)
    @patch(
        "builtins.open",
        new_callable=lambda: lambda: MagicMock(
            __enter__=lambda s: MagicMock(
                read=lambda: json.dumps(
                    {"jwt": "cached_jwt", "xsrf": "cached_xsrf", "cookies": {}, "jwt_exp": 999}
                )
            ),
            __exit__=lambda s, *a: None,
        ),
    )
    def test_loads_cached_values(self, mock_open, mock_exists, mock_session, client):
        """Verify load_cache populates client attributes from cache file."""
        # Use a simpler approach — just patch the json.load
        import json as _json

        cache_data = {
            "jwt": "cached_jwt",
            "xsrf": "cached_xsrf",
            "cookies": {"key": "value"},
            "jwt_exp": 999,
            "user_id": "111",
            "battery_id": "222",
        }
        client.user_id = None
        client.battery_id = None

        with patch("builtins.open", MagicMock()):
            with patch("json.load", return_value=cache_data):
                mock_session.cookies = MagicMock()
                client.load_cache()
                assert client.jwt_token == "cached_jwt"
                assert client.xsrf_token == "cached_xsrf"
                assert client.jwt_exp == 999
                assert client.user_id == "111"
                assert client.battery_id == "222"

    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    @patch("os.path.exists", return_value=False)
    def test_no_cache_file(self, mock_exists, mock_session, client):
        """No error when cache file doesn't exist."""
        client.load_cache()
        assert client.jwt_token is None


class TestSaveCache:
    @patch("custom_components.enphase_envoy_cloud_control.enphase_client.SESSION")
    def test_writes_cache(self, mock_session, client):
        client.jwt_token = "jwt"
        client.xsrf_token = "xsrf"
        client.jwt_exp = 12345
        mock_session.cookies = MagicMock()

        with patch("builtins.open", MagicMock()) as mock_open:
            with patch("json.dump") as mock_dump:
                with patch("os.makedirs"):
                    client._save_cache()
                    mock_dump.assert_called_once()
                    data = mock_dump.call_args[0][0]
                    assert data["jwt"] == "jwt"
                    assert data["xsrf"] == "xsrf"
