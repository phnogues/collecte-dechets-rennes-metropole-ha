"""Capteurs : prochaine collecte par type de déchet et toutes collectes confondues."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import CollecteConfigEntry, CollecteCoordinator
from .entity import CollecteEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CollecteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [WasteSensor(coordinator, waste) for waste in coordinator.data.waste_types]
    entities.append(NextCollectionSensor(coordinator))
    async_add_entities(entities)


class WasteSensor(CollecteEntity, SensorEntity):
    """Date du prochain passage pour un type de déchet."""

    _attr_device_class = SensorDeviceClass.DATE

    def __init__(self, coordinator: CollecteCoordinator, waste: str) -> None:
        super().__init__(coordinator, waste)
        self._waste = waste
        self._attr_translation_key = waste

    @property
    def native_value(self) -> date | None:
        return self.coordinator.data.next_date(self._waste, dt_util.now().date())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date()
        nxt = self.native_value
        upcoming = [d.isoformat() for d in self.coordinator.data.collections.get(self._waste, []) if d >= today][:5]
        return {
            "days_until": (nxt - today).days if nxt else None,
            "bin": self.coordinator.data.waste_types[self._waste].bin,
            "upcoming": upcoming,
        }


class NextCollectionSensor(CollecteEntity, SensorEntity):
    """Prochain passage, tous déchets confondus."""

    _attr_device_class = SensorDeviceClass.DATE
    _attr_translation_key = "next_collection"

    def __init__(self, coordinator: CollecteCoordinator) -> None:
        super().__init__(coordinator, "next_collection")

    @property
    def native_value(self) -> date | None:
        nxt = self.coordinator.data.next_collection(dt_util.now().date())
        return nxt.day if nxt else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        today = dt_util.now().date()
        schedule = self.coordinator.data
        nxt = schedule.next_collection(today)
        if nxt is None:
            return {"days_until": None, "waste_types": [], "description": None}
        names = [schedule.waste_types[w].name(self.language) for w in nxt.waste_types]
        return {
            "days_until": (nxt.day - today).days,
            "waste_types": list(nxt.waste_types),
            "bins": [schedule.waste_types[w].bin for w in nxt.waste_types],
            "description": ", ".join(names),
        }
