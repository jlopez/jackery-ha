"""Shared test fixtures and homeassistant module mocks."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import timedelta
from types import ModuleType
from typing import Any

# ---------------------------------------------------------------------------
# Minimal stubs for the ``homeassistant`` package hierarchy so that imports
# inside custom_components/ succeed even though homeassistant is not installed.
# This must run before any custom_components module is imported.
# ---------------------------------------------------------------------------


class _StubConfigEntry:
    """Minimal ConfigEntry stub."""

    data: dict[str, Any]
    runtime_data: Any = None

    def __class_getitem__(cls, item: Any) -> type:
        return cls


class _StubConfigFlow:
    """Minimal ConfigFlow stub that supports ``domain=`` class keyword."""

    def __init_subclass__(cls, *, domain: str = "", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    def async_show_form(
        self, *, step_id: str, data_schema: Any = None, errors: dict[str, str] | None = None
    ) -> dict[str, Any]:
        return {"type": "form", "step_id": step_id, "errors": errors or {}}

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}

    def async_abort(self, *, reason: str) -> dict[str, Any]:
        return {"type": "abort", "reason": reason}

    async def async_set_unique_id(self, unique_id: str) -> None:
        pass

    def _abort_if_unique_id_configured(self) -> None:
        pass


# A simple alias for ConfigFlowResult
ConfigFlowResult = dict[str, Any]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class _ConfigEntryAuthFailed(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryAuthFailed."""


class _ConfigEntryNotReady(Exception):
    """Stub for homeassistant.exceptions.ConfigEntryNotReady."""


# ---------------------------------------------------------------------------
# DataUpdateCoordinator stub
# ---------------------------------------------------------------------------


class _StubDataUpdateCoordinator:
    """Minimal DataUpdateCoordinator stub for testing."""

    def __init__(
        self,
        hass: Any,
        logger: Any,
        *,
        name: str = "",
        update_interval: timedelta | None = None,
        config_entry: Any = None,
    ) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.config_entry = config_entry
        self.data: Any = {}
        self._listeners: list[Any] = []
        self.last_update_success: bool = True

    def __class_getitem__(cls, item: Any) -> type:
        return cls

    @property
    def available(self) -> bool:
        return self.last_update_success

    async def async_config_entry_first_refresh(self) -> None:
        await self._async_setup()
        self.data = await self._async_update_data()

    async def _async_setup(self) -> None:
        """Override in subclasses for first-time setup."""

    async def _async_update_data(self) -> Any:
        raise NotImplementedError

    def async_set_updated_data(self, data: Any) -> None:
        self.data = data

    async def async_request_refresh(self) -> None:
        self.data = await self._async_update_data()


class _StubCoordinatorEntity:
    """Minimal CoordinatorEntity stub for testing."""

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator

    def __class_getitem__(cls, item: Any) -> type:
        return cls

    @property
    def available(self) -> bool:
        result: bool = self.coordinator.available
        return result


# ---------------------------------------------------------------------------
# DeviceInfo stub
# ---------------------------------------------------------------------------


class _StubDeviceInfo:
    """Minimal DeviceInfo stub for testing."""

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


# ---------------------------------------------------------------------------
# EntityDescription stub
# ---------------------------------------------------------------------------


class _StubEntityDescription:
    """Minimal EntityDescription stub for testing."""

    key: str = ""

    def __init__(self, *, key: str = "", **kwargs: Any) -> None:
        self.key = key
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)


class _UpdateFailed(Exception):
    """Stub for homeassistant.helpers.update_coordinator.UpdateFailed."""


# ---------------------------------------------------------------------------
# Platform enum stub
# ---------------------------------------------------------------------------


class _Platform:
    """Stub for homeassistant.const.Platform."""

    SENSOR = "sensor"
    BINARY_SENSOR = "binary_sensor"
    SWITCH = "switch"
    SELECT = "select"
    NUMBER = "number"


class _EntityCategory:
    """Stub for homeassistant.const.EntityCategory."""

    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


class _UnitOfTemperature:
    CELSIUS = "°C"
    FAHRENHEIT = "°F"


class _UnitOfPower:
    WATT = "W"
    KILO_WATT = "kW"


class _UnitOfElectricPotential:
    VOLT = "V"


class _UnitOfFrequency:
    HERTZ = "Hz"


class _UnitOfTime:
    HOURS = "h"
    MINUTES = "min"
    SECONDS = "s"


# ---------------------------------------------------------------------------
# Sensor platform stubs
# ---------------------------------------------------------------------------


class _SensorDeviceClass:
    """Stub for homeassistant.components.sensor.SensorDeviceClass."""

    BATTERY = "battery"
    TEMPERATURE = "temperature"
    POWER = "power"
    VOLTAGE = "voltage"
    FREQUENCY = "frequency"
    DURATION = "duration"
    ENUM = "enum"


class _SensorStateClass:
    """Stub for homeassistant.components.sensor.SensorStateClass."""

    MEASUREMENT = "measurement"
    TOTAL = "total"
    TOTAL_INCREASING = "total_increasing"


@dataclass(frozen=True, kw_only=True)
class _SensorEntityDescription:
    """Stub for homeassistant.components.sensor.SensorEntityDescription."""

    key: str = ""
    device_class: Any = None
    native_unit_of_measurement: str | None = None
    state_class: Any = None
    entity_category: Any = None
    options: list[str] | None = None
    translation_key: str | None = None


class _SensorEntity:
    """Stub for homeassistant.components.sensor.SensorEntity."""

    entity_description: Any = None


# ---------------------------------------------------------------------------
# Binary sensor platform stubs
# ---------------------------------------------------------------------------


class _BinarySensorDeviceClass:
    """Stub for homeassistant.components.binary_sensor.BinarySensorDeviceClass."""

    BATTERY_CHARGING = "battery_charging"
    PROBLEM = "problem"
    CONNECTIVITY = "connectivity"


@dataclass(frozen=True, kw_only=True)
class _BinarySensorEntityDescription:
    """Stub for homeassistant.components.binary_sensor.BinarySensorEntityDescription."""

    key: str = ""
    device_class: Any = None
    entity_category: Any = None
    translation_key: str | None = None


class _BinarySensorEntity:
    """Stub for homeassistant.components.binary_sensor.BinarySensorEntity."""

    entity_description: Any = None


# ---------------------------------------------------------------------------
# Switch platform stubs
# ---------------------------------------------------------------------------


class _SwitchDeviceClass:
    """Stub for homeassistant.components.switch.SwitchDeviceClass."""

    OUTLET = "outlet"
    SWITCH = "switch"


@dataclass(frozen=True, kw_only=True)
class _SwitchEntityDescription:
    """Stub for homeassistant.components.switch.SwitchEntityDescription."""

    key: str = ""
    device_class: Any = None
    entity_category: Any = None
    translation_key: str | None = None


class _SwitchEntity:
    """Stub for homeassistant.components.switch.SwitchEntity."""

    entity_description: Any = None


# ---------------------------------------------------------------------------
# Select platform stubs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _SelectEntityDescription:
    """Stub for homeassistant.components.select.SelectEntityDescription."""

    key: str = ""
    device_class: Any = None
    entity_category: Any = None
    translation_key: str | None = None
    options: list[str] | None = None


class _SelectEntity:
    """Stub for homeassistant.components.select.SelectEntity."""

    entity_description: Any = None


# ---------------------------------------------------------------------------
# Number platform stubs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class _NumberEntityDescription:
    """Stub for homeassistant.components.number.NumberEntityDescription."""

    key: str = ""
    device_class: Any = None
    entity_category: Any = None
    translation_key: str | None = None
    native_unit_of_measurement: str | None = None
    native_min_value: float | None = None
    native_max_value: float | None = None
    native_step: float | None = None


class _NumberEntity:
    """Stub for homeassistant.components.number.NumberEntity."""

    entity_description: Any = None


# ---------------------------------------------------------------------------
# Register all fake homeassistant modules
# ---------------------------------------------------------------------------


def _make_ha_modules() -> None:
    """Register fake homeassistant modules in sys.modules."""
    # homeassistant
    ha = ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.core
    ha_core = ModuleType("homeassistant.core")
    ha_core.HomeAssistant = type("HomeAssistant", (), {})  # type: ignore[attr-defined]
    sys.modules["homeassistant.core"] = ha_core

    # homeassistant.const
    ha_const = ModuleType("homeassistant.const")
    ha_const.Platform = _Platform  # type: ignore[attr-defined]
    ha_const.PERCENTAGE = "%"  # type: ignore[attr-defined]
    ha_const.EntityCategory = _EntityCategory  # type: ignore[attr-defined]
    ha_const.UnitOfTemperature = _UnitOfTemperature  # type: ignore[attr-defined]
    ha_const.UnitOfPower = _UnitOfPower  # type: ignore[attr-defined]
    ha_const.UnitOfElectricPotential = _UnitOfElectricPotential  # type: ignore[attr-defined]
    ha_const.UnitOfFrequency = _UnitOfFrequency  # type: ignore[attr-defined]
    ha_const.UnitOfTime = _UnitOfTime  # type: ignore[attr-defined]
    sys.modules["homeassistant.const"] = ha_const

    # homeassistant.config_entries
    ha_ce = ModuleType("homeassistant.config_entries")
    ha_ce.ConfigEntry = _StubConfigEntry  # type: ignore[attr-defined]
    ha_ce.ConfigFlow = _StubConfigFlow  # type: ignore[attr-defined]
    ha_ce.ConfigFlowResult = ConfigFlowResult  # type: ignore[attr-defined]
    sys.modules["homeassistant.config_entries"] = ha_ce

    # homeassistant.exceptions
    ha_exc = ModuleType("homeassistant.exceptions")
    ha_exc.ConfigEntryAuthFailed = _ConfigEntryAuthFailed  # type: ignore[attr-defined]
    ha_exc.ConfigEntryNotReady = _ConfigEntryNotReady  # type: ignore[attr-defined]
    sys.modules["homeassistant.exceptions"] = ha_exc

    # homeassistant.helpers
    ha_helpers = ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = ha_helpers

    # homeassistant.helpers.update_coordinator
    ha_coord = ModuleType("homeassistant.helpers.update_coordinator")
    ha_coord.DataUpdateCoordinator = _StubDataUpdateCoordinator  # type: ignore[attr-defined]
    ha_coord.CoordinatorEntity = _StubCoordinatorEntity  # type: ignore[attr-defined]
    ha_coord.UpdateFailed = _UpdateFailed  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_coord

    # homeassistant.helpers.device_registry
    ha_devreg = ModuleType("homeassistant.helpers.device_registry")
    ha_devreg.DeviceInfo = _StubDeviceInfo  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.device_registry"] = ha_devreg

    # homeassistant.helpers.entity
    ha_entity = ModuleType("homeassistant.helpers.entity")
    ha_entity.EntityDescription = _StubEntityDescription  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.entity"] = ha_entity

    # homeassistant.helpers.entity_platform
    ha_entity_platform = ModuleType("homeassistant.helpers.entity_platform")
    ha_entity_platform.AddEntitiesCallback = None  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.entity_platform"] = ha_entity_platform

    # homeassistant.components
    ha_components = ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = ha_components

    # homeassistant.components.sensor
    ha_sensor = ModuleType("homeassistant.components.sensor")
    ha_sensor.SensorDeviceClass = _SensorDeviceClass  # type: ignore[attr-defined]
    ha_sensor.SensorStateClass = _SensorStateClass  # type: ignore[attr-defined]
    ha_sensor.SensorEntityDescription = _SensorEntityDescription  # type: ignore[attr-defined]
    ha_sensor.SensorEntity = _SensorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.sensor"] = ha_sensor

    # homeassistant.components.binary_sensor
    ha_binary_sensor = ModuleType("homeassistant.components.binary_sensor")
    ha_binary_sensor.BinarySensorDeviceClass = _BinarySensorDeviceClass  # type: ignore[attr-defined]
    ha_binary_sensor.BinarySensorEntityDescription = _BinarySensorEntityDescription  # type: ignore[attr-defined]
    ha_binary_sensor.BinarySensorEntity = _BinarySensorEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.binary_sensor"] = ha_binary_sensor

    # homeassistant.components.switch
    ha_switch = ModuleType("homeassistant.components.switch")
    ha_switch.SwitchDeviceClass = _SwitchDeviceClass  # type: ignore[attr-defined]
    ha_switch.SwitchEntityDescription = _SwitchEntityDescription  # type: ignore[attr-defined]
    ha_switch.SwitchEntity = _SwitchEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.switch"] = ha_switch

    # homeassistant.components.select
    ha_select = ModuleType("homeassistant.components.select")
    ha_select.SelectEntityDescription = _SelectEntityDescription  # type: ignore[attr-defined]
    ha_select.SelectEntity = _SelectEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.select"] = ha_select

    # homeassistant.components.number
    ha_number = ModuleType("homeassistant.components.number")
    ha_number.NumberEntityDescription = _NumberEntityDescription  # type: ignore[attr-defined]
    ha_number.NumberEntity = _NumberEntity  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.number"] = ha_number


_make_ha_modules()
