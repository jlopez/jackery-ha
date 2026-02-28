"""DataUpdateCoordinator for Jackery power stations."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from socketry import Client, Subscription

from .const import CONF_EMAIL, CONF_PASSWORD, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

type JackeryData = dict[str, dict[str, object]]


class JackeryCoordinator(DataUpdateCoordinator[JackeryData]):  # type: ignore[misc]
    """Coordinator for Jackery power stations.

    Subscribes to real-time MQTT push updates via socketry and falls back to
    HTTP polling every ``DEFAULT_POLL_INTERVAL`` seconds when MQTT is down.
    """

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Jackery",
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
            config_entry=entry,
        )
        self.client: Client | None = None
        self.devices: list[dict[str, object]] = []
        self._subscription: Subscription | None = None

    @property
    def mqtt_connected(self) -> bool:
        """Return True when the MQTT subscription is active."""
        return self._subscription is not None

    async def _async_setup(self) -> None:
        """Perform first-time setup: login, fetch device list, start MQTT."""
        email = self.config_entry.data[CONF_EMAIL]
        password = self.config_entry.data[CONF_PASSWORD]

        try:
            client = await Client.login(email, password)
            devices = await client.fetch_devices()
        except RuntimeError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Cannot connect to Jackery API: {err}") from err

        self.client = client
        self.devices = devices

        self._subscription = await self.client.subscribe(
            self._handle_mqtt_update,
            on_disconnect=self._handle_disconnect,
        )

    async def _async_update_data(self) -> JackeryData:
        """Fetch properties for all devices via HTTP."""
        if self.client is None:
            await self._async_setup()
        assert self.client is not None

        data: JackeryData = {}
        last_error: Exception | None = None
        for device in self.devices:
            sn = str(device.get("devSn", ""))
            if not sn:
                continue
            try:
                device_obj = self.client.device(sn)
                raw = await device_obj.get_all_properties()
                # Extract properties from the response; the HTTP API returns
                # {"device": {...}, "properties": {...}} — we want just the
                # property map.
                props = raw.get("properties") or raw
                if isinstance(props, dict):
                    data[sn] = props
                else:
                    data[sn] = {}
            except RuntimeError as err:
                # Auth errors affect the whole account — abort immediately.
                raise ConfigEntryAuthFailed(str(err)) from err
            except (aiohttp.ClientError, TimeoutError, OSError) as err:
                # Transient error for this device — log and continue with the
                # remaining devices so one unreachable device doesn't block all.
                _LOGGER.warning("Error fetching data for %s: %s", sn, err)
                last_error = err

        if not data and last_error is not None:
            raise UpdateFailed(f"Failed to fetch data for any device: {last_error}") from last_error

        return data

    async def _handle_mqtt_update(self, device_sn: str, properties: dict[str, object]) -> None:
        """Handle a real-time MQTT property update."""
        if self.data is None:
            return
        if device_sn in self.data:
            self.data[device_sn].update(properties)
        else:
            self.data[device_sn] = dict(properties)
        self.async_set_updated_data(self.data)

    async def _handle_disconnect(self) -> None:
        """Handle MQTT disconnection — log a warning and fall back to HTTP poll."""
        _LOGGER.warning("Jackery MQTT disconnected — falling back to HTTP poll")
