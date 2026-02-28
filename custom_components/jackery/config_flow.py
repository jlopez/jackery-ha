"""Config flow for Jackery integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from socketry import Client

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)


class JackeryConfigFlow(ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    """Handle a config flow for Jackery."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                client = await Client.login(email, password)
                # login() fetches devices internally; read from the cached list.
                devices = client.devices
            except RuntimeError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Jackery login")
                errors["base"] = "unknown"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    user_id = str(client._creds.get("userId", ""))
                    await self.async_set_unique_id(user_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=email,
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_schema(user_input),
            errors=errors,
        )

    def _build_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        """Build the form schema with optional defaults from prior input."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_EMAIL,
                    default=(user_input or {}).get(CONF_EMAIL, ""),
                ): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
