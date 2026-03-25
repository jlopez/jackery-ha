"""Config flow for Jackery integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import QrCodeSelector
from socketry import AuthenticationError, Client, SocketryError

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .coordinator import JackeryCoordinator

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
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Jackery login")
                errors["base"] = "unknown"
            else:
                user_id = client.user_id
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

    @staticmethod
    @callback  # type: ignore[untyped-decorator]
    def async_get_options_flow(config_entry: object) -> OptionsFlow:
        """Create the options flow."""
        return JackeryOptionsFlow()

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> ConfigFlowResult:
        """Handle reauth when credentials become invalid."""
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._build_schema(entry_data),
            errors={},
        )

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauth confirmation form."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            try:
                await Client.login(email, password)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during Jackery reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data={CONF_EMAIL: email, CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
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


class JackeryOptionsFlow(OptionsFlow):  # type: ignore[misc]
    """Jackery config options flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle options flow — generate and display a device-sharing QR code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Reload the integration to pick up newly shared devices.
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        # Get the coordinator from the config entry
        coordinator: JackeryCoordinator = self.config_entry.runtime_data
        client = coordinator.client

        if client is None:
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        # Generate QR code
        try:
            qr_data = await client.generate_share_qrcode()  # type: ignore[attr-defined]
        except (aiohttp.ClientError, TimeoutError, OSError):
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors,
            )
        except SocketryError:
            _LOGGER.exception("Failed to generate share QR code")
            errors["base"] = "qr_failed"
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        qr_json = json.dumps(qr_data, separators=(",", ":"))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("qr_code"): QrCodeSelector({"data": qr_json}),
                }
            ),
            errors=errors,
        )
