"""Base entity for Jackery integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from socketry import MODEL_NAMES

from .const import DOMAIN
from .coordinator import JackeryCoordinator


class JackeryEntity(CoordinatorEntity[JackeryCoordinator]):  # type: ignore[misc]
    """Base entity for all Jackery platform entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JackeryCoordinator,
        device_sn: str,
        description: EntityDescription,
    ) -> None:
        """Initialize the Jackery entity."""
        super().__init__(coordinator)
        self._device_sn = device_sn
        self.entity_description = description
        self._attr_unique_id = f"{device_sn}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for device registry."""
        device = self._find_device()
        name = str(device.get("devName", "Jackery")) if device else "Jackery"
        raw_code = device.get("modelCode", 0) if device else 0
        try:
            model_code = int(raw_code)  # type: ignore[call-overload]
        except (TypeError, ValueError):
            model_code = 0
        model: str = MODEL_NAMES.get(model_code, f"Unknown ({model_code})")
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_sn)},
            manufacturer="Jackery",
            name=name,
            model=model,
            serial_number=self._device_sn,
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._device_sn in self.coordinator.data
        )

    def _prop(self, key: str) -> object:
        """Return a raw property value from coordinator data."""
        data = self.coordinator.data
        if data is None:
            return None
        device_data = data.get(self._device_sn)
        if device_data is None:
            return None
        return device_data.get(key)

    def _find_device(self) -> dict[str, object] | None:
        """Find the device dict for this entity's serial number."""
        coordinator: JackeryCoordinator = self.coordinator
        for dev in coordinator.devices:
            if dev.get("devSn") == self._device_sn:
                return dev
        return None

    def _device_index(self) -> int | None:
        """Return the index of this entity's device in the coordinator device list."""
        for idx, dev in enumerate(self.coordinator.devices):
            if dev.get("devSn") == self._device_sn:
                return idx
        return None
