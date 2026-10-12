"""Entité calendrier : un événement « journée entière » par jour de collecte."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import CollecteConfigEntry, CollecteCoordinator
from .entity import CollecteEntity
from .schedule import Collection


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CollecteConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([CollecteCalendar(entry.runtime_data)])


class CollecteCalendar(CollecteEntity, CalendarEntity):
    _attr_translation_key = "collections"

    def __init__(self, coordinator: CollecteCoordinator) -> None:
        super().__init__(coordinator, "calendar")

    @property
    def event(self) -> CalendarEvent | None:
        nxt = self.coordinator.data.next_collection(dt_util.now().date())
        return self._to_event(nxt) if nxt else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        start = dt_util.as_local(start_date)
        end = dt_util.as_local(end_date)
        # Un événement « journée entière » le jour J chevauche [start, end[ si J >= start.date() et minuit(J) < end.
        last = end.date() + timedelta(days=1) if end.time() != time.min else end.date()
        collections = self.coordinator.data.collections_between(start.date(), last)
        return [self._to_event(c) for c in collections]

    def _to_event(self, collection: Collection) -> CalendarEvent:
        schedule = self.coordinator.data
        types = [schedule.waste_types[w] for w in collection.waste_types]
        french = self.language.startswith("fr")
        bins = " + ".join(f"bac {t.bin}" if french else f"{t.name('en').lower()} bin" for t in types)
        summary = (f"Collecte {bins}" if french else f"Collection: {bins}")
        description = ", ".join(t.name(self.language) for t in types)
        start = schedule.collection_start.strftime("%H:%M")
        description += (
            f". Sortir le bac la veille au soir (passage dès {start})."
            if french
            else f". Put the bin out the evening before (collection from {start})."
        )
        return CalendarEvent(
            start=collection.day,
            end=collection.day + timedelta(days=1),
            summary=summary,
            description=description,
            uid=f"{schedule.zone_id}-{collection.day.isoformat()}",
        )
