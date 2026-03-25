"""Tests for Jackery config flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from socketry import AuthenticationError, SocketryError

from custom_components.jackery.config_flow import JackeryConfigFlow
from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD

# --- Helpers to simulate HA config flow machinery ---


def _make_hass() -> MagicMock:
    """Create a minimal mock HomeAssistant instance."""
    return MagicMock()


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
    client.devices = FAKE_DEVICES
    client.user_id = "user-42"
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
        new=AsyncMock(return_value=mock_client),
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
        new=AsyncMock(side_effect=AuthenticationError("Login failed: invalid credentials")),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_auth"


async def test_cannot_connect_client_error(hass):
    """Test network error (aiohttp.ClientError) shows cannot_connect."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=aiohttp.ClientConnectionError("Connection refused")),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_cannot_connect_timeout(hass):
    """Test timeout shows cannot_connect."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=TimeoutError("Connection timed out")),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_cannot_connect_os_error(hass):
    """Test OS-level network error shows cannot_connect."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=OSError("Network unreachable")),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_no_devices_creates_entry(hass, mock_client):
    """Test empty device list still creates config entry."""
    flow = _make_flow(hass)
    mock_client.devices = []

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await flow.async_step_user(user_input=VALID_INPUT)

    assert result["type"] == "create_entry"
    assert result["title"] == "user@example.com"
    assert result["data"][CONF_EMAIL] == "user@example.com"
    assert result["data"][CONF_PASSWORD] == "secret123"


async def test_unknown_error(hass):
    """Test unexpected exception shows unknown error."""
    flow = _make_flow(hass)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=ValueError("Something weird happened")),
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
            new=AsyncMock(return_value=mock_client),
        ),
        pytest.raises(AbortFlow, match="already_configured"),
    ):
        await flow.async_step_user(user_input=VALID_INPUT)


# --- Options Flow tests ---


def _make_options_flow(hass: MagicMock, mock_entry: MagicMock) -> Any:
    """Create a JackeryOptionsFlow with mocked entry and hass."""
    from custom_components.jackery.config_flow import JackeryOptionsFlow

    options_flow = JackeryOptionsFlow()
    options_flow.hass = hass
    options_flow.config_entry = mock_entry
    return options_flow


@pytest.fixture
def mock_options_entry(mock_client):
    """Create a mock config entry for options flow tests."""
    mock_entry = MagicMock()
    mock_entry.runtime_data = MagicMock()
    mock_entry.runtime_data.client = mock_client
    mock_entry.entry_id = "test_entry_id"
    return mock_entry


async def test_options_flow_available(hass, mock_options_entry):
    """Test that options flow is available."""
    from custom_components.jackery.config_flow import JackeryConfigFlow

    options_flow = JackeryConfigFlow.async_get_options_flow(mock_options_entry)

    assert options_flow is not None
    assert hasattr(options_flow, "async_step_init")


async def test_options_flow_shows_qr(hass, mock_client, mock_options_entry):
    """Test options flow generates and displays QR code."""
    mock_client.generate_share_qrcode = AsyncMock(
        return_value={"qrCodeId": "abc123", "userId": 1234567890}
    )

    options_flow = _make_options_flow(hass, mock_options_entry)
    result = await options_flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert "qr_code" in result["data_schema"].schema
    mock_client.generate_share_qrcode.assert_awaited_once()


async def test_options_flow_qr_generation_failure(hass, mock_client, mock_options_entry):
    """Test options flow QR generation failure shows error."""
    mock_client.generate_share_qrcode = AsyncMock(side_effect=SocketryError("QR generation failed"))

    options_flow = _make_options_flow(hass, mock_options_entry)
    result = await options_flow.async_step_init()

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    assert result["errors"]["base"] == "qr_failed"


async def test_options_flow_submit_creates_entry(hass, mock_client, mock_options_entry):
    """Test options flow submit reloads integration and creates entry."""
    hass.config_entries.async_reload = AsyncMock()
    options_flow = _make_options_flow(hass, mock_options_entry)

    result = await options_flow.async_step_init(user_input={"qr_code": ""})

    assert result["type"] == "create_entry"
    assert result["title"] == ""
    assert result["data"] == {}
    hass.config_entries.async_reload.assert_awaited_once_with("test_entry_id")


# --- Reauth flow helpers ---


def _make_reauth_flow(hass: MagicMock, existing_entry: MagicMock) -> JackeryConfigFlow:
    """Create a JackeryConfigFlow configured for reauth."""
    flow = JackeryConfigFlow()
    flow.hass = hass
    flow.context = {"_reauth_entry": existing_entry}
    return flow


@pytest.fixture
def existing_entry() -> MagicMock:
    """Create a mock config entry with existing credentials."""
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "old_password"}
    return entry


# --- Reauth tests ---


async def test_reauth_shows_form(hass, existing_entry):
    """async_step_reauth shows a form pre-filled with existing email."""
    flow = _make_reauth_flow(hass, existing_entry)

    result = await flow.async_step_reauth(
        entry_data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "old_password"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}


async def test_reauth_confirm_success(hass, existing_entry, mock_client):
    """Successful reauth updates stored password and aborts with reauth_successful."""
    flow = _make_reauth_flow(hass, existing_entry)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        result = await flow.async_step_reauth_confirm(
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "new_password"},
        )

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert existing_entry.data[CONF_EMAIL] == "user@example.com"
    assert existing_entry.data[CONF_PASSWORD] == "new_password"


async def test_reauth_confirm_shows_form_when_no_input(hass, existing_entry):
    """async_step_reauth_confirm with no user_input shows the form."""
    flow = _make_reauth_flow(hass, existing_entry)

    result = await flow.async_step_reauth_confirm(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}


async def test_reauth_confirm_invalid_auth(hass, existing_entry):
    """AuthenticationError during reauth shows invalid_auth error."""
    flow = _make_reauth_flow(hass, existing_entry)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=AuthenticationError("Login failed: bad credentials")),
    ):
        result = await flow.async_step_reauth_confirm(
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "wrong_password"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_confirm_authentication_error(hass, existing_entry):
    """AuthenticationError during reauth shows invalid_auth error."""
    flow = _make_reauth_flow(hass, existing_entry)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=AuthenticationError("Re-authentication failed")),
    ):
        result = await flow.async_step_reauth_confirm(
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "wrong_password"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_confirm_cannot_connect(hass, existing_entry):
    """Network error during reauth shows cannot_connect error."""
    flow = _make_reauth_flow(hass, existing_entry)

    with patch(
        "custom_components.jackery.config_flow.Client.login",
        new=AsyncMock(side_effect=aiohttp.ClientConnectionError("Connection refused")),
    ):
        result = await flow.async_step_reauth_confirm(
            user_input={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "new_password"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"]["base"] == "cannot_connect"
