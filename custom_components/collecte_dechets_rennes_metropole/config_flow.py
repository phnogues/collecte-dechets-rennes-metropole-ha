"""Configuration : choix de la zone dans une liste, URL des données et heure du rappel en options."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .api import CannotFetchError, async_fetch_data
from .const import CONF_DATA_URL, CONF_REMINDER_TIME, CONF_ZONE, DEFAULT_DATA_URL, DEFAULT_REMINDER_TIME, DOMAIN
from .coordinator import CollecteConfigEntry
from .schedule import InvalidDataError, list_zones

_LOGGER = logging.getLogger(__name__)

# Type texte (et non URL) pour accepter aussi un chemin local, ex. /config/collectes.json
URL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))


class CollecteConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._url = DEFAULT_DATA_URL
        self._zones: dict[str, str] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Charge la liste des zones depuis l'URL par défaut, sinon demande l'URL."""
        if not await self._async_load_zones(self._url):
            return await self.async_step_zone()
        return await self.async_step_source()

    async def async_step_source(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_load_zones(user_input[CONF_DATA_URL])
            if not errors:
                self._url = user_input[CONF_DATA_URL]
                return await self.async_step_zone()
        return self.async_show_form(
            step_id="source",
            data_schema=vol.Schema({vol.Required(CONF_DATA_URL, default=self._url): URL_SELECTOR}),
            errors=errors,
        )

    async def async_step_zone(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            zone = user_input[CONF_ZONE]
            await self.async_set_unique_id(zone)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._zones[zone],
                data={CONF_ZONE: zone},
                options={CONF_DATA_URL: self._url, CONF_REMINDER_TIME: DEFAULT_REMINDER_TIME},
            )
        selector = SelectSelector(
            SelectSelectorConfig(
                options=[SelectOptionDict(value=k, label=v) for k, v in self._zones.items()],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
        return self.async_show_form(step_id="zone", data_schema=vol.Schema({vol.Required(CONF_ZONE): selector}))

    async def _async_load_zones(self, url: str) -> dict[str, str]:
        try:
            self._zones = list_zones(await async_fetch_data(self.hass, url))
        except CannotFetchError as err:
            _LOGGER.debug("Données injoignables à %s : %s", url, err)
            return {"base": "cannot_connect"}
        except InvalidDataError as err:
            _LOGGER.debug("Données invalides à %s : %s", url, err)
            return {"base": "invalid_data"}
        return {} if self._zones else {"base": "no_zones"}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: CollecteConfigEntry) -> OptionsFlow:
        return CollecteOptionsFlow()


class CollecteOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        zone = self.config_entry.data[CONF_ZONE]
        if user_input is not None:
            try:
                zones = list_zones(await async_fetch_data(self.hass, user_input[CONF_DATA_URL]))
            except CannotFetchError:
                errors["base"] = "cannot_connect"
            except InvalidDataError:
                errors["base"] = "invalid_data"
            else:
                if zone not in zones:
                    errors["base"] = "zone_missing"
                else:
                    return self.async_create_entry(data=user_input)

        options = {**self.config_entry.options, **(user_input or {})}
        schema = vol.Schema(
            {
                vol.Required(CONF_REMINDER_TIME, default=options.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME)): TimeSelector(),
                vol.Required(CONF_DATA_URL, default=options.get(CONF_DATA_URL, DEFAULT_DATA_URL)): URL_SELECTOR,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
