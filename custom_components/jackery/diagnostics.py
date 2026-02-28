"""Diagnostics support for the Jackery integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import JackeryCoordinator

REDACT_FIELDS = {"email", "password", "token", "mqttPassWord", "userId"}


def _redact_value(value: Any) -> Any:
    """Recursively redact sensitive fields from a value (dict or list)."""
    if isinstance(value, dict):
        return _redact_dict(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive fields from a dictionary."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in REDACT_FIELDS:
            result[key] = "**REDACTED**"
        else:
            result[key] = _redact_value(value)
    return result


def _redact_device_metadata(
    devices: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Extract safe metadata from device dicts, redacting sensitive fields."""
    safe_devices: list[dict[str, object]] = []
    for device in devices:
        safe: dict[str, object] = {}
        for key, value in device.items():
            if key in REDACT_FIELDS:
                safe[key] = "**REDACTED**"
            else:
                safe[key] = value
        safe_devices.append(safe)
    return safe_devices


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a Jackery config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    data: dict[str, Any] = {}

    # Include redacted config entry data
    data["config_entry_data"] = _redact_dict(dict(entry.data))

    # Include device metadata (SN, name, model -- not credentials)
    data["devices"] = _redact_device_metadata(coordinator.devices)

    # Include coordinator data (all device properties)
    if coordinator.data:
        data["coordinator_data"] = _redact_dict(dict(coordinator.data))
    else:
        data["coordinator_data"] = {}

    # Include device count
    data["device_count"] = len(coordinator.devices)

    # Include MQTT connection status
    data["client_connected"] = coordinator.client is not None
    data["mqtt_connected"] = coordinator.mqtt_connected

    return data
