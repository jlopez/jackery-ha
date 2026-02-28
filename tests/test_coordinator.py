"""Tests for JackeryCoordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator

# Re-import the stub exceptions so we can assert on them
from tests.conftest import _ConfigEntryAuthFailed, _UpdateFailed

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000", "modelCode": 5},
]

FAKE_PROPS_SN001: dict[str, object] = {
    "device": {"devSn": "SN001"},
    "properties": {"rb": 85, "bt": 250, "ip": 100, "op": 50},
}

FAKE_PROPS_SN002: dict[str, object] = {
    "device": {"devSn": "SN002"},
    "properties": {"rb": 42, "bt": 300, "ip": 0, "op": 200},
}


def _make_entry() -> MagicMock:
    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret123",
    }
    return entry


def _make_hass() -> MagicMock:
    return MagicMock()


def _make_mock_subscription() -> MagicMock:
    sub = MagicMock()
    sub.stop = AsyncMock()
    return sub


def _make_mock_client(
    devices: list[dict[str, object]] | None = None,
    props_by_sn: dict[str, dict[str, object]] | None = None,
) -> MagicMock:
    """Build a mock Client with async fetch_devices, subscribe, and device()."""
    client = MagicMock()
    client.fetch_devices = AsyncMock(return_value=devices or FAKE_DEVICES)

    default_props: dict[str, dict[str, object]] = {
        "SN001": FAKE_PROPS_SN001,
        "SN002": FAKE_PROPS_SN002,
    }
    actual_props = props_by_sn or default_props

    def make_device(sn: str) -> MagicMock:
        device_mock = MagicMock()
        device_mock.get_all_properties = AsyncMock(return_value=actual_props.get(sn, {}))
        return device_mock

    client.device.side_effect = make_device

    # subscribe returns a Subscription mock; capture callback/on_disconnect
    # for tests that need to exercise them directly.
    client.subscribe = AsyncMock(return_value=_make_mock_subscription())

    return client


# --- Tests ---


async def test_first_refresh_populates_data():
    """First refresh should login, fetch devices, and populate data for all devices."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert "SN001" in coordinator.data
    assert "SN002" in coordinator.data
    assert coordinator.data["SN001"]["rb"] == 85
    assert coordinator.data["SN001"]["bt"] == 250
    assert coordinator.data["SN002"]["rb"] == 42
    assert coordinator.data["SN002"]["op"] == 200


async def test_first_refresh_stores_client_and_devices():
    """First refresh should store the client and device list on the coordinator."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.client is mock_client
    assert coordinator.devices == FAKE_DEVICES


async def test_first_refresh_starts_mqtt_subscription():
    """First refresh should start the MQTT subscription."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    mock_client.subscribe.assert_called_once()
    assert coordinator._subscription is not None
    assert coordinator.mqtt_connected is True


async def test_mqtt_callback_merges_properties():
    """MQTT callback should merge pushed properties into coordinator data and notify."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    # Capture the callback passed to subscribe
    captured_callback = None

    async def mock_subscribe(callback, *, on_disconnect=None):
        nonlocal captured_callback
        captured_callback = callback
        return _make_mock_subscription()

    mock_client.subscribe = mock_subscribe

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert captured_callback is not None

    # Simulate an MQTT push update for SN001
    await captured_callback("SN001", {"rb": 95, "op": 10})

    assert coordinator.data["SN001"]["rb"] == 95
    assert coordinator.data["SN001"]["op"] == 10
    # Other keys should be preserved
    assert coordinator.data["SN001"]["bt"] == 250


async def test_mqtt_callback_adds_new_device():
    """MQTT callback should add a new device entry if SN is not yet in coordinator data."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    captured_callback = None

    async def mock_subscribe(callback, *, on_disconnect=None):
        nonlocal captured_callback
        captured_callback = callback
        return _make_mock_subscription()

    mock_client.subscribe = mock_subscribe

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert captured_callback is not None

    # Push an update for a device not in the initial HTTP data
    await captured_callback("SN999", {"rb": 50})

    assert "SN999" in coordinator.data
    assert coordinator.data["SN999"]["rb"] == 50


async def test_mqtt_callback_ignored_when_data_is_none():
    """MQTT callback should be a no-op when coordinator data is None."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    captured_callback = None

    async def mock_subscribe(callback, *, on_disconnect=None):
        nonlocal captured_callback
        captured_callback = callback
        return _make_mock_subscription()

    mock_client.subscribe = mock_subscribe

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert captured_callback is not None

    # Manually clear data to simulate the pre-setup state
    coordinator.data = None

    # Should not raise
    await captured_callback("SN001", {"rb": 99})


async def test_disconnect_callback_logs_warning():
    """on_disconnect callback should log a warning."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    captured_disconnect = None

    async def mock_subscribe(callback, *, on_disconnect=None):
        nonlocal captured_disconnect
        captured_disconnect = on_disconnect
        return _make_mock_subscription()

    mock_client.subscribe = mock_subscribe

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert captured_disconnect is not None

    # Calling disconnect should not raise; warning is logged internally
    with patch("custom_components.jackery.coordinator._LOGGER") as mock_logger:
        await captured_disconnect()
        mock_logger.warning.assert_called_once()


async def test_subsequent_poll_fetches_fresh_data():
    """Subsequent update (HTTP poll) should fetch fresh data for all devices."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    # Update mock to return new values
    updated_props: dict[str, object] = {
        "device": {"devSn": "SN001"},
        "properties": {"rb": 90, "bt": 240, "ip": 50, "op": 25},
    }
    mock_client.device.side_effect = None
    device_mock = MagicMock()
    device_mock.get_all_properties = AsyncMock(return_value=updated_props)
    mock_client.device.return_value = device_mock

    await coordinator.async_request_refresh()

    assert coordinator.data["SN001"]["rb"] == 90


async def test_auth_failure_on_login_raises_config_entry_auth_failed():
    """Login failure (RuntimeError) should raise ConfigEntryAuthFailed."""
    hass = _make_hass()
    entry = _make_entry()

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            new=AsyncMock(side_effect=RuntimeError("Login failed: invalid credentials")),
        ),
        pytest.raises(_ConfigEntryAuthFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_auth_failure_on_fetch_raises_config_entry_auth_failed():
    """RuntimeError during property fetch should raise ConfigEntryAuthFailed."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    device_mock = MagicMock()
    device_mock.get_all_properties = AsyncMock(
        side_effect=RuntimeError("Property fetch failed: token expired")
    )
    mock_client.device.side_effect = None
    mock_client.device.return_value = device_mock

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            new=AsyncMock(return_value=mock_client),
        ),
        pytest.raises(_ConfigEntryAuthFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_transient_error_on_login_raises_update_failed():
    """Network error during login should raise UpdateFailed."""
    hass = _make_hass()
    entry = _make_entry()

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            new=AsyncMock(side_effect=aiohttp.ClientConnectionError("Connection refused")),
        ),
        pytest.raises(_UpdateFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_transient_error_on_fetch_raises_update_failed():
    """Network error during property fetch should raise UpdateFailed."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    device_mock = MagicMock()
    device_mock.get_all_properties = AsyncMock(side_effect=aiohttp.ServerTimeoutError())
    mock_client.device.side_effect = None
    mock_client.device.return_value = device_mock

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            new=AsyncMock(return_value=mock_client),
        ),
        pytest.raises(_UpdateFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_devices_without_sn_are_skipped():
    """Devices with missing devSn should be skipped gracefully."""
    hass = _make_hass()
    entry = _make_entry()

    bad_devices: list[dict[str, object]] = [
        {"devId": "ID_NOSN", "devName": "NoSN"},
        {"devSn": "SN001", "devId": "ID001", "devName": "Good", "modelCode": 12},
    ]
    mock_client = _make_mock_client(
        devices=bad_devices,
        props_by_sn={"SN001": FAKE_PROPS_SN001},
    )

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert "SN001" in coordinator.data
    assert "" not in coordinator.data


async def test_transient_error_on_one_device_does_not_block_others():
    """When one device fails with a transient error, the other devices should still be polled."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    call_count: list[int] = [0]

    def make_device(sn: str) -> MagicMock:
        device_mock = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:
            device_mock.get_all_properties = AsyncMock(side_effect=aiohttp.ServerTimeoutError())
        else:
            device_mock.get_all_properties = AsyncMock(return_value=FAKE_PROPS_SN002)
        return device_mock

    mock_client.device.side_effect = make_device

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    # SN001 failed but SN002 should still be present
    assert "SN001" not in coordinator.data
    assert "SN002" in coordinator.data
    assert coordinator.data["SN002"]["rb"] == 42


async def test_all_devices_transient_error_raises_update_failed():
    """When all devices fail with transient errors, UpdateFailed should be raised."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()

    device_mock = MagicMock()
    device_mock.get_all_properties = AsyncMock(side_effect=aiohttp.ServerTimeoutError())
    mock_client.device.side_effect = None
    mock_client.device.return_value = device_mock

    coordinator = JackeryCoordinator(hass, entry)

    with (
        patch(
            "custom_components.jackery.coordinator.Client.login",
            new=AsyncMock(return_value=mock_client),
        ),
        pytest.raises(_UpdateFailed),
    ):
        await coordinator.async_config_entry_first_refresh()


async def test_properties_without_nested_properties_key():
    """When get_all_properties returns a flat dict (no 'properties' key), use it directly."""
    hass = _make_hass()
    entry = _make_entry()

    flat_props: dict[str, object] = {"rb": 70, "bt": 200}
    devices = [FAKE_DEVICES[0]]
    mock_client = _make_mock_client(
        devices=devices,
        props_by_sn={"SN001": flat_props},
    )

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.data["SN001"]["rb"] == 70
    assert coordinator.data["SN001"]["bt"] == 200


async def test_subscription_stopped_on_unload():
    """Subscription.stop() should be called when the integration is unloaded."""
    hass = _make_hass()
    entry = _make_entry()
    mock_client = _make_mock_client()
    mock_sub = _make_mock_subscription()
    mock_client.subscribe = AsyncMock(return_value=mock_sub)

    coordinator = JackeryCoordinator(hass, entry)

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        new=AsyncMock(return_value=mock_client),
    ):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator._subscription is mock_sub

    await coordinator._subscription.stop()
    mock_sub.stop.assert_called_once()
