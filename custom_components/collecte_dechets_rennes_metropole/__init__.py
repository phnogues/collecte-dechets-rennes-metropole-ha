"""Intégration Collecte Déchets Rennes Métropole."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .coordinator import STORAGE_VERSION, CollecteConfigEntry, CollecteCoordinator, outdated_issue_id

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CollecteConfigEntry) -> bool:
    coordinator = CollecteCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CollecteConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: CollecteConfigEntry) -> None:
    """Supprime le cache local et l'alerte éventuelle quand l'intégration est retirée."""
    await Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}").async_remove()
    ir.async_delete_issue(hass, DOMAIN, outdated_issue_id(entry.entry_id))


async def _async_reload_entry(hass: HomeAssistant, entry: CollecteConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
