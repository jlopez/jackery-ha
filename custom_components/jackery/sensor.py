"""Sensor platform for Jackery integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import JackeryCoordinator
from .entity import JackeryEntity

BATTERY_STATE_MAP: dict[int, str] = {
    0: "idle",
    1: "charging",
    2: "discharging",
}


@dataclass(frozen=True, kw_only=True)
class JackerySensorEntityDescription(SensorEntityDescription):  # type: ignore[misc]
    """Describes a Jackery sensor entity."""

    property_key: str
    scale: float = 1.0
    value_fn: Callable[[object], float | str | None] | None = None


def _battery_state_fn(raw: object) -> str | None:
    """Map battery state integer to string."""
    try:
        return BATTERY_STATE_MAP.get(int(raw))  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None


def _duration_fn(raw: object) -> float | None:
    """Return None when raw duration is zero or the sentinel max value (999)."""
    try:
        val = int(raw)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return None
    if val == 0 or val >= 999:
        return None
    return float(val) / 10


SENSOR_DESCRIPTIONS: tuple[JackerySensorEntityDescription, ...] = (
    JackerySensorEntityDescription(
        key="rb",
        translation_key="battery",
        property_key="rb",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="bt",
        translation_key="battery_temperature",
        property_key="bt",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        scale=10.0,
    ),
    JackerySensorEntityDescription(
        key="bs",
        translation_key="battery_state",
        property_key="bs",
        value_fn=_battery_state_fn,
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "charging", "discharging"],
    ),
    JackerySensorEntityDescription(
        key="ip",
        translation_key="input_power",
        property_key="ip",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="op",
        translation_key="output_power",
        property_key="op",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="it",
        translation_key="time_to_full",
        property_key="it",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_duration_fn,
    ),
    JackerySensorEntityDescription(
        key="ot",
        translation_key="time_remaining",
        property_key="ot",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_duration_fn,
    ),
    JackerySensorEntityDescription(
        key="acip",
        translation_key="ac_input_power",
        property_key="acip",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="cip",
        translation_key="car_input_power",
        property_key="cip",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="acov",
        translation_key="ac_voltage",
        property_key="acov",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        scale=10.0,
    ),
    JackerySensorEntityDescription(
        key="acohz",
        translation_key="ac_frequency",
        property_key="acohz",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="acps",
        translation_key="ac_power",
        property_key="acps",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="acpss",
        translation_key="ac_power_secondary",
        property_key="acpss",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="acpsp",
        translation_key="ac_socket_power",
        property_key="acpsp",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    JackerySensorEntityDescription(
        key="ec",
        translation_key="error_code",
        property_key="ec",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JackerySensorEntityDescription(
        key="pmb",
        translation_key="power_mode_battery",
        property_key="pmb",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JackerySensorEntityDescription(
        key="tt",
        translation_key="total_temperature",
        property_key="tt",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JackerySensorEntityDescription(
        key="ss",
        translation_key="system_status",
        property_key="ss",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


class JackerySensorEntity(JackeryEntity, SensorEntity):  # type: ignore[misc]
    """Representation of a Jackery sensor."""

    entity_description: JackerySensorEntityDescription

    def __init__(
        self,
        coordinator: JackeryCoordinator,
        device_sn: str,
        description: JackerySensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, device_sn, description)

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value."""
        raw = self._prop(self.entity_description.property_key)
        if raw is None:
            return None

        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(raw)

        if self.entity_description.scale != 1.0:
            try:
                return float(raw) / self.entity_description.scale  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None

        # Return raw numeric value as float, or string as-is
        if isinstance(raw, (int, float)):
            return float(raw)
        if isinstance(raw, str):
            return raw
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jackery sensor entities from a config entry."""
    coordinator: JackeryCoordinator = entry.runtime_data
    entities: list[JackerySensorEntity] = []

    for device in coordinator.devices:
        sn = str(device.get("devSn", ""))
        if not sn:
            continue
        device_data = coordinator.data.get(sn, {})
        for description in SENSOR_DESCRIPTIONS:
            if description.property_key in device_data:
                entities.append(JackerySensorEntity(coordinator, sn, description))

    async_add_entities(entities)
