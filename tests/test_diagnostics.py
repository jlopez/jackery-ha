"""Tests for Jackery diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.jackery.const import CONF_EMAIL, CONF_PASSWORD
from custom_components.jackery.coordinator import JackeryCoordinator
from custom_components.jackery.diagnostics import (
    REDACT_FIELDS,
    _redact_device_metadata,
    _redact_dict,
    async_get_config_entry_diagnostics,
)

# --- Helpers ---

FAKE_DEVICES: list[dict[str, object]] = [
    {"devSn": "SN001", "devId": "ID001", "devName": "Explorer 2000", "modelCode": 12},
    {"devSn": "SN002", "devId": "ID002", "devName": "Explorer 1000 Plus", "modelCode": 5},
]

FAKE_DATA: dict[str, dict[str, object]] = {
    "SN001": {"rb": 85, "bt": 250, "bs": 1},
    "SN002": {"rb": 42, "bt": 300},
}


def _make_coordinator(
    data: dict[str, dict[str, object]] | None = None,
    devices: list[dict[str, object]] | None = None,
) -> JackeryCoordinator:
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    coordinator = JackeryCoordinator(hass, entry)
    coordinator.data = data if data is not None else dict(FAKE_DATA)
    coordinator.devices = devices if devices is not None else list(FAKE_DEVICES)
    return coordinator


# --- _redact_dict tests ---


def test_redact_dict_redacts_known_fields():
    data = {
        "email": "user@example.com",
        "password": "secret",
        "token": "jwt-token-123",
        "mqttPassWord": "mqtt-pass",
        "userId": "uid-456",
        "safe_field": "visible",
    }
    result = _redact_dict(data)
    for field in REDACT_FIELDS:
        assert result[field] == "**REDACTED**"
    assert result["safe_field"] == "visible"


def test_redact_dict_handles_nested_dicts():
    data = {
        "outer": {"email": "user@example.com", "info": "ok"},
        "plain": "value",
    }
    result = _redact_dict(data)
    assert result["outer"]["email"] == "**REDACTED**"
    assert result["outer"]["info"] == "ok"
    assert result["plain"] == "value"


def test_redact_dict_preserves_non_sensitive_data():
    data = {"rb": 85, "bt": 250, "bs": 1}
    result = _redact_dict(data)
    assert result == data


def test_redact_dict_empty():
    assert _redact_dict({}) == {}


def test_redact_dict_handles_lists_with_dicts():
    data = {
        "items": [
            {"token": "secret-jwt", "name": "visible"},
            {"password": "pass123", "id": 42},
        ],
    }
    result = _redact_dict(data)
    assert result["items"][0]["token"] == "**REDACTED**"
    assert result["items"][0]["name"] == "visible"
    assert result["items"][1]["password"] == "**REDACTED**"
    assert result["items"][1]["id"] == 42


def test_redact_dict_handles_nested_lists():
    data = {
        "outer": [
            {"inner": [{"email": "user@example.com", "ok": True}]},
        ],
    }
    result = _redact_dict(data)
    assert result["outer"][0]["inner"][0]["email"] == "**REDACTED**"
    assert result["outer"][0]["inner"][0]["ok"] is True


def test_redact_dict_handles_list_of_non_dicts():
    data = {"tags": ["a", "b", "c"], "nums": [1, 2, 3]}
    result = _redact_dict(data)
    assert result["tags"] == ["a", "b", "c"]
    assert result["nums"] == [1, 2, 3]


# --- _redact_device_metadata tests ---


def test_redact_device_metadata_preserves_safe_fields():
    devices: list[dict[str, object]] = [
        {"devSn": "SN001", "devName": "Test", "modelCode": 12},
    ]
    result = _redact_device_metadata(devices)
    assert len(result) == 1
    assert result[0]["devSn"] == "SN001"
    assert result[0]["devName"] == "Test"
    assert result[0]["modelCode"] == 12


def test_redact_device_metadata_redacts_sensitive_fields():
    devices: list[dict[str, object]] = [
        {"devSn": "SN001", "token": "jwt-token", "userId": "uid-123"},
    ]
    result = _redact_device_metadata(devices)
    assert result[0]["devSn"] == "SN001"
    assert result[0]["token"] == "**REDACTED**"
    assert result[0]["userId"] == "**REDACTED**"


def test_redact_device_metadata_empty_list():
    assert _redact_device_metadata([]) == []


def test_redact_device_metadata_redacts_nested_sensitive_fields():
    """Nested sensitive fields inside a device dict must also be redacted."""
    devices: list[dict[str, object]] = [
        {
            "devSn": "SN001",
            "credentials": {"token": "nested-secret", "safe": "visible"},
        }
    ]
    result = _redact_device_metadata(devices)
    assert result[0]["devSn"] == "SN001"
    nested = result[0]["credentials"]
    assert isinstance(nested, dict)
    assert nested["token"] == "**REDACTED**"
    assert nested["safe"] == "visible"


# --- async_get_config_entry_diagnostics tests ---


async def test_diagnostics_returns_device_properties():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    # Coordinator data should be present
    assert "coordinator_data" in result
    assert "SN001" in result["coordinator_data"]
    assert result["coordinator_data"]["SN001"]["rb"] == 85


async def test_diagnostics_redacts_sensitive_config_data():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "secret",
    }
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["config_entry_data"]["email"] == "**REDACTED**"
    assert result["config_entry_data"]["password"] == "**REDACTED**"


async def test_diagnostics_includes_device_metadata():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert "devices" in result
    assert len(result["devices"]) == 2
    assert result["devices"][0]["devSn"] == "SN001"
    assert result["devices"][1]["devSn"] == "SN002"


async def test_diagnostics_includes_device_count():
    coordinator = _make_coordinator()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["device_count"] == 2


async def test_diagnostics_handles_empty_coordinator_data():
    coordinator = _make_coordinator(data={})
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["coordinator_data"] == {}


async def test_diagnostics_includes_client_connected_true():
    coordinator = _make_coordinator()
    coordinator.client = MagicMock()
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["client_connected"] is True


async def test_diagnostics_includes_client_connected_false():
    coordinator = _make_coordinator()
    coordinator.client = None
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["client_connected"] is False
    assert result["mqtt_connected"] is False


async def test_diagnostics_mqtt_connected_true():
    coordinator = _make_coordinator()
    coordinator.client = MagicMock()
    coordinator._subscription = MagicMock()  # Non-None means MQTT subscription is active
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["mqtt_connected"] is True


async def test_diagnostics_mqtt_connected_false_when_no_active_mqtt():
    coordinator = _make_coordinator()
    client = MagicMock(spec=[])  # No attributes at all
    coordinator.client = client
    entry = MagicMock()
    entry.data = {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    assert result["client_connected"] is True
    assert result["mqtt_connected"] is False


async def test_diagnostics_no_sensitive_data_exposed():
    """Verify that no sensitive field values appear in the output."""
    coordinator = _make_coordinator()
    # Add a device with sensitive fields
    coordinator.devices = [
        {
            "devSn": "SN001",
            "devName": "Test",
            "token": "secret-jwt",
            "userId": "user-id-secret",
            "mqttPassWord": "mqtt-secret",
        }
    ]
    entry = MagicMock()
    entry.data = {
        CONF_EMAIL: "user@example.com",
        CONF_PASSWORD: "supersecretpass",
        "token": "jwt-token-value",
    }
    entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(MagicMock(), entry)

    # Check config entry data is redacted
    assert result["config_entry_data"]["email"] == "**REDACTED**"
    assert result["config_entry_data"]["password"] == "**REDACTED**"
    assert result["config_entry_data"]["token"] == "**REDACTED**"

    # Check device metadata is redacted
    device = result["devices"][0]
    assert device["devSn"] == "SN001"
    assert device["devName"] == "Test"
    assert device["token"] == "**REDACTED**"
    assert device["userId"] == "**REDACTED**"
    assert device["mqttPassWord"] == "**REDACTED**"

    # Verify no raw sensitive values appear anywhere in the serialized output
    import json

    serialized = json.dumps(result)
    assert "user@example.com" not in serialized
    assert "supersecretpass" not in serialized
    assert "jwt-token-value" not in serialized
    assert "secret-jwt" not in serialized
    assert "user-id-secret" not in serialized
    assert "mqtt-secret" not in serialized
