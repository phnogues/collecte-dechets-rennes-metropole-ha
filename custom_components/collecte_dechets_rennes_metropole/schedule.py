"""Logique de calendrier, indépendante de Home Assistant (testable seule)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SUPPORTED_SCHEMA_VERSION = 1


class InvalidDataError(Exception):
    """Le fichier de données n'a pas le format attendu."""


@dataclass(frozen=True)
class WasteType:
    key: str
    names: dict[str, str]
    bin: str

    def name(self, language: str) -> str:
        return self.names.get(language.split("-")[0], self.names.get("en", self.key))


@dataclass(frozen=True)
class Collection:
    day: date
    waste_types: tuple[str, ...]


@dataclass
class ZoneSchedule:
    zone_id: str
    name: str
    collections: dict[str, list[date]]
    waste_types: dict[str, WasteType]
    collection_start: time
    valid_until: date | None

    def next_date(self, waste: str, today: date) -> date | None:
        return next((d for d in self.collections.get(waste, []) if d >= today), None)

    def collections_between(self, start: date, end: date) -> list[Collection]:
        """Collectes dont le jour est dans [start, end[, regroupées par jour."""
        by_day: dict[date, list[str]] = {}
        for waste, days in self.collections.items():
            for day in days:
                if start <= day < end:
                    by_day.setdefault(day, []).append(waste)
        return [Collection(day, tuple(sorted(w))) for day, w in sorted(by_day.items())]

    def next_collection(self, today: date) -> Collection | None:
        upcoming = [d for d in (self.next_date(w, today) for w in self.collections) if d]
        if not upcoming:
            return None
        day = min(upcoming)
        return self.collections_between(day, day + timedelta(days=1))[0]

    def take_out_window(self, day: date, reminder: time, tz) -> tuple[datetime, datetime]:
        """Période où il faut sortir le bac pour la collecte du jour ``day``."""
        start = datetime.combine(day - timedelta(days=1), reminder, tzinfo=tz)
        end = datetime.combine(day, self.collection_start, tzinfo=tz)
        return start, end

    def take_out_status(self, now: datetime, reminder: time) -> tuple[Collection | None, datetime | None]:
        """Retourne (collecte concernée si le rappel est actif, prochain changement d'état)."""
        for collection in self.collections_between(now.date(), now.date() + timedelta(days=400)):
            start, end = self.take_out_window(collection.day, reminder, now.tzinfo)
            if end <= now:
                continue
            if start <= now:
                return collection, end
            return None, start
        return None, None

    def is_outdated(self, today: date) -> bool:
        if self.valid_until is not None and today > self.valid_until:
            return True
        return self.next_collection(today) is None


def parse_schedule(raw: dict, zone_id: str) -> ZoneSchedule:
    """Construit le calendrier d'une zone à partir du JSON publié."""
    try:
        if raw["schema_version"] != SUPPORTED_SCHEMA_VERSION:
            raise InvalidDataError(f"schema_version {raw['schema_version']} non supportée")
        zone = raw["zones"][zone_id]
        waste_types = {
            key: WasteType(key, {k: v for k, v in info.items() if k != "bin"}, info.get("bin", ""))
            for key, info in raw["waste_types"].items()
        }
        collections = {
            waste: sorted(date.fromisoformat(d) for d in days)
            for waste, days in zone["collections"].items()
            if waste in waste_types
        }
        hour, minute = (int(x) for x in raw.get("collection_start", "05:30").split(":"))
        valid_until = date.fromisoformat(raw["valid_until"]) if raw.get("valid_until") else None
        return ZoneSchedule(zone_id, zone["name"], collections, waste_types, time(hour, minute), valid_until)
    except InvalidDataError:
        raise
    except (KeyError, TypeError, ValueError, AttributeError) as err:
        raise InvalidDataError(f"données invalides pour la zone {zone_id} : {err!r}") from err


def list_zones(raw: dict) -> dict[str, str]:
    """{zone_id: nom affiché} dans l'ordre du fichier."""
    try:
        if raw["schema_version"] != SUPPORTED_SCHEMA_VERSION:
            raise InvalidDataError(f"schema_version {raw['schema_version']} non supportée")
        return {zone_id: zone["name"] for zone_id, zone in raw["zones"].items()}
    except InvalidDataError:
        raise
    except (KeyError, TypeError, AttributeError) as err:
        raise InvalidDataError(f"données invalides : {err!r}") from err
