"""Capteur binaire « Sortir le bac » : actif de la veille (heure réglable) jusqu'au passage."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME
from .coordinator import CollecteConfigEntry, CollecteCoordinator
from .entity import CollecteEntity
from .schedule import Collection


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CollecteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    reminder = time.fromisoformat(entry.options.get(CONF_REMINDER_TIME, DEFAULT_REMINDER_TIME))
    async_add_entities([TakeOutBinSensor(entry.runtime_data, reminder)])


class TakeOutBinSensor(CollecteEntity, BinarySensorEntity):
    _attr_translation_key = "take_out_bin"

    def __init__(self, coordinator: CollecteCoordinator, reminder: time) -> None:
        super().__init__(coordinator, "take_out_bin")
        self._reminder = reminder
        self._collection: Collection | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_timer)
        self._refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._refresh()

    @callback
    def _cancel_timer(self) -> None:
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _refresh(self, _now: datetime | None = None) -> None:
        """Recalcule l'état et programme le prochain changement."""
        self._cancel_timer()
        self._collection, next_change = self.coordinator.data.take_out_status(dt_util.now(), self._reminder)
        if next_change is not None:
            self._unsub_timer = async_track_point_in_time(self.hass, self._refresh, next_change)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        return self._collection is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._collection is None:
            return {"collection_date": None, "waste_types": [], "bins": []}
        schedule = self.coordinator.data
        return {
            "collection_date": self._collection.day.isoformat(),
            "waste_types": list(self._collection.waste_types),
            "bins": [schedule.waste_types[w].bin for w in self._collection.waste_types],
            "description": ", ".join(schedule.waste_types[w].name(self.language) for w in self._collection.waste_types),
        }
