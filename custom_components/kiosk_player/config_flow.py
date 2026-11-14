"""Setting up Kiosk Player: the main server's address and a pairing code made there."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL, __version__ as HA_VERSION
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import KioskApi, KioskAuthError, KioskConnectionError, KioskError, KioskRateLimited, normalize_url
from .const import (
    CONF_CREDENTIAL,
    CONF_CREDENTIAL_ID,
    CONF_PAIRING_CODE,
    CONF_RELAY_ID,
    CONF_RELAY_NAME,
    CONF_SITE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class KioskPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pairs this Home Assistant with the main Kiosk server as one relay."""

    VERSION = 1

    async def _pair(self, url: str, code: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
        try:
            result = await KioskApi.pair(
                async_get_clientsession(self.hass), url, code, {"name": "Home Assistant", "ha_version": HA_VERSION}
            )
        except KioskAuthError as err:
            return None, {"base": "relay_disabled" if err.status == 403 else "invalid_code"}
        except KioskRateLimited:
            return None, {"base": "too_many_attempts"}
        except KioskConnectionError:
            return None, {CONF_URL: "cannot_connect"}
        except KioskError:
            _LOGGER.exception("Unexpected answer while pairing with the Kiosk server")
            return None, {"base": "unknown"}
        return result, {}

    @staticmethod
    def _entry_data(url: str, result: dict[str, Any]) -> dict[str, Any]:
        relay = result["relay"]
        return {
            CONF_URL: url,
            CONF_RELAY_ID: relay["id"],
            CONF_RELAY_NAME: relay["name"],
            CONF_SITE: relay.get("site"),
            CONF_CREDENTIAL_ID: result["credential_id"],
            CONF_CREDENTIAL: result["credential"],
        }

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            result, errors = await self._pair(url, user_input[CONF_PAIRING_CODE])
            if result is not None:
                await self.async_set_unique_id(result["relay"]["id"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=result["relay"]["name"], data=self._entry_data(url, result))
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_URL): str, vol.Required(CONF_PAIRING_CODE): str}),
                {CONF_URL: (user_input or {}).get(CONF_URL, "")},
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """The credential was revoked (or the relay disabled): pair again with a new code."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            url = entry.data[CONF_URL]
            result, errors = await self._pair(url, user_input[CONF_PAIRING_CODE])
            if result is not None:
                await self.async_set_unique_id(result["relay"]["id"])
                self._abort_if_unique_id_mismatch(reason="wrong_relay")
                return self.async_update_reload_and_abort(entry, data=self._entry_data(url, result))
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PAIRING_CODE): str}),
            description_placeholders={"relay": entry.title},
            errors=errors,
        )
