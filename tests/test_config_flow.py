"""Tests for Jackery config flow."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from custom_components.jackery.config_flow import JackeryConfigFlow
from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD

# --- Helpers to simulate HA config flow machinery ---


def _make_hass() -> MagicMock:
    """Create a minimal mock HomeAssistant instance."""
    hass = MagicMock()

    async def _add_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = _add_executor_job
    return hass


def _make_flow(hass: MagicMock) -> JackeryConfigFlow:
    """Create a JackeryConfigFlow with a mocked hass."""
    flow = JackeryConfigFlow()
    flow.hass = hass
    return flow


# --- Test data ---

VALID_INPUT = {
    CONF_EMAIL: "user@example.com",
    CONF_PASSWORD: "secret123",
}

FAKE_DEVICES: list[dict[str, object]] = [
    {
        "devSn": "SN001",
        "devId": "ID001",
        "devName": "My Jackery",
    }
]


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock socketry Client."""
    client = MagicMock()
    client._creds = {"userId": "user-42", "devices": FAKE_DEVICES}
    return client


@pytest.fixture
def hass() -> MagicMock:
    return _make_hass()


# --- Tests ---


async def test_successful_flow(hass, mock_client):
    """Test successful login and device discovery creates an entry."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        return_value=mock_client,
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "create_entry"
    assert result["title"] == VALID_INPUT[CONF_EMAIL]
    assert result["data"][CONF_EMAIL] == VALID_INPUT[CONF_EMAIL]
    assert result["data"][CONF_PASSWORD] == VALID_INPUT[CONF_PASSWORD]


async def test_show_form_when_no_input(hass):
    """Test that the form is shown when no user input is provided."""
    flow = _make_flow(hass)

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_invalid_auth(hass):
    """Test invalid credentials shows invalid_auth error."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        side_effect=RuntimeError("Login failed: invalid credentials"),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


async def test_cannot_connect_request_exception(hass):
    """Test network error (RequestException) shows cannot_connect."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        side_effect=requests.exceptions.ConnectionError("Connection refused"),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_cannot_connect_timeout(hass):
    """Test timeout shows cannot_connect."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        side_effect=TimeoutError("Connection timed out"),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_cannot_connect_os_error(hass):
    """Test OS-level network error shows cannot_connect."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        side_effect=OSError("Network unreachable"),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_no_devices(hass, mock_client):
    """Test empty device list shows no_devices error."""
    flow = _make_flow(hass)
    mock_client._creds["devices"] = []

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        return_value=mock_client,
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "no_devices"


async def test_unknown_error(hass):
    """Test unexpected exception shows unknown error."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        side_effect=ValueError("Something weird happened"),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "unknown"


async def test_duplicate_account(hass, mock_client):
    """Test duplicate account aborts with already_configured."""
    flow = _make_flow(hass)

    # Simulate the HA behavior where _abort_if_unique_id_configured raises
    # an exception when a matching entry already exists.
    class AbortFlow(Exception):
        def __init__(self, reason: str) -> None:
            self.reason = reason

    flow._abort_if_unique_id_configured = MagicMock(
        side_effect=AbortFlow("already_configured"),
    )

    with (
        patch(
            "custom_components.jackery.config_flow.Client.login",
            return_value=mock_client,
        ),
        pytest.raises(AbortFlow, match="already_configured"),
    ):
        await flow.async_step_user(user_input=VALID_INPUT)
