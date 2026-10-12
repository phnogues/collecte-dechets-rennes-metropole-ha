"""Entité de base : un appareil par zone, rafraîchi chaque nuit."""

from __future__ import annotations

from datetime import datetime

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import CollecteCoordinator


class CollecteEntity(CoordinatorEntity[CollecteCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    def __init__(self, coordinator: CollecteCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Rennes Métropole",
            model="Calendrier de collecte",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://dechets.metropole.rennes.fr/ou-et-comment-jeter-vos-dechets/",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # La « prochaine collecte » change à minuit, même sans nouvelles données.
        self.async_on_remove(async_track_time_change(self.hass, self._async_midnight, hour=0, minute=0, second=5))

    @callback
    def _async_midnight(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def language(self) -> str:
        return self.hass.config.language or "fr"
