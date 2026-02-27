"""Tests for Jackery __init__.py and constants."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.jackery import PLATFORMS, async_setup_entry, async_unload_entry
from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD, DEFAULT_POLL_INTERVAL, DOMAIN


def test_domain_constant():
    assert DOMAIN == "jackery"


def test_poll_interval_constant():
    assert DEFAULT_POLL_INTERVAL == 300


def test_conf_constants():
    assert CONF_EMAIL == "email"
    assert CONF_PASSWORD == "password"


def test_platforms_list():
    assert "sensor" in PLATFORMS
    assert "binary_sensor" in PLATFORMS
    assert "switch" in PLATFORMS
    assert "select" in PLATFORMS
    assert "number" in PLATFORMS


async def test_async_setup_entry():
    """Test that async_setup_entry creates coordinator and forwards platforms."""
    hass = MagicMock()

    async def _add_executor_job(func, *args):
        return func(*args)

    hass.async_add_executor_job = _add_executor_job
    hass.config_entries.async_forward_entry_setups = AsyncMock()

    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret123",
    }

    fake_devices = [{"devSn": "SN001", "devId": "ID001", "devName": "Test"}]
    fake_props = {"properties": {"rb": 80}}

    mock_client = MagicMock()
    mock_client.fetch_devices.return_value = fake_devices
    mock_client.select_device.return_value = fake_devices[0]
    mock_client.get_all_properties.return_value = fake_props

    with patch(
        "custom_components.jackery.coordinator.Client.login",
        return_value=mock_client,
    ):
        result = await async_setup_entry(hass, entry)

    assert result is True
    assert entry.runtime_data is not None
    hass.config_entries.async_forward_entry_setups.assert_called_once_with(entry, PLATFORMS)


async def test_async_unload_entry():
    """Test that async_unload_entry unloads platforms and cleans up coordinator."""
    hass = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    coordinator = MagicMock()
    coordinator.client = MagicMock()

    entry = MagicMock()
    entry.runtime_data = coordinator

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert coordinator.client is None
    hass.config_entries.async_unload_platforms.assert_called_once_with(entry, PLATFORMS)
