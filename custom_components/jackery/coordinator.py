"""DataUpdateCoordinator for Jackery power stations."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from socketry import Client

from .const import CONF_EMAIL, CONF_PASSWORD, DEFAULT_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

type JackeryData = dict[str, dict[str, object]]


class JackeryCoordinator(DataUpdateCoordinator[JackeryData]):  # type: ignore[misc]
    """Coordinator for Jackery power stations.

    Polls all devices via HTTP at a regular interval and merges their
    property maps into a single ``{device_sn: {prop_key: value}}`` dict.
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

    async def _async_setup(self) -> None:
        """Perform first-time setup: login and fetch device list."""
        email = self.config_entry.data[CONF_EMAIL]
        password = self.config_entry.data[CONF_PASSWORD]

        try:
            client = await self.hass.async_add_executor_job(Client.login, email, password)
            devices = await self.hass.async_add_executor_job(client.fetch_devices)
        except RuntimeError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except (requests.exceptions.RequestException, TimeoutError, OSError) as err:
            raise UpdateFailed(f"Cannot connect to Jackery API: {err}") from err

        self.client = client
        self.devices = devices

    async def _async_update_data(self) -> JackeryData:
        """Fetch properties for all devices via HTTP."""
        if self.client is None:
            await self._async_setup()
        assert self.client is not None

        data: JackeryData = {}
        last_error: Exception | None = None
        for idx, device in enumerate(self.devices):
            sn = str(device.get("devSn", ""))
            if not sn:
                continue
            try:
                await self.hass.async_add_executor_job(self.client.select_device, idx)
                raw: dict[str, Any] = await self.hass.async_add_executor_job(
                    self.client.get_all_properties,
                )
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
            except (requests.exceptions.RequestException, TimeoutError, OSError) as err:
                # Transient error for this device — log and continue with the
                # remaining devices so one unreachable device doesn't block all.
                _LOGGER.warning("Error fetching data for %s: %s", sn, err)
                last_error = err

        if not data and last_error is not None:
            raise UpdateFailed(f"Failed to fetch data for any device: {last_error}") from last_error

        return data
