"""Tests de la logique de calendrier de l'intégration (sans Home Assistant)."""

import importlib.util
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

PATH = Path(__file__).resolve().parent.parent / "custom_components" / "collecte_dechets_rennes_metropole" / "schedule.py"
spec = importlib.util.spec_from_file_location("schedule", PATH)
schedule = importlib.util.module_from_spec(spec)
sys.modules["schedule"] = schedule
spec.loader.exec_module(schedule)

TZ = ZoneInfo("Europe/Paris")
RAW = {
    "schema_version": 1,
    "valid_until": "2027-09-30",
    "collection_start": "05:30",
    "waste_types": {
        "ordures_menageres": {"fr": "Ordures ménagères", "en": "Household waste", "bin": "gris"},
        "recyclables": {"fr": "Déchets recyclables", "en": "Recyclables", "bin": "jaune"},
    },
    "zones": {
        "acigne": {
            "name": "Acigné",
            "commune": "Acigné",
            "collections": {
                "ordures_menageres": ["2026-10-06", "2026-10-20", "2026-11-03"],
                "recyclables": ["2026-10-02", "2026-10-16", "2026-10-20"],
            },
        }
    },
}


@pytest.fixture
def sched():
    return schedule.parse_schedule(RAW, "acigne")


def test_next_date(sched):
    assert sched.next_date("ordures_menageres", date(2026, 10, 6)) == date(2026, 10, 6)
    assert sched.next_date("ordures_menageres", date(2026, 10, 7)) == date(2026, 10, 20)
    assert sched.next_date("ordures_menageres", date(2026, 11, 4)) is None


def test_next_collection_groups_same_day(sched):
    nxt = sched.next_collection(date(2026, 10, 17))
    assert nxt.day == date(2026, 10, 20)
    assert nxt.waste_types == ("ordures_menageres", "recyclables")


def test_take_out_window(sched):
    reminder = time(18, 0)
    # Avant le rappel : inactif, prochain changement la veille à 18h
    coll, change = sched.take_out_status(datetime(2026, 10, 5, 12, 0, tzinfo=TZ), reminder)
    assert coll is None and change == datetime(2026, 10, 5, 18, 0, tzinfo=TZ)
    # Veille au soir : actif jusqu'à 5h30 le jour J
    coll, change = sched.take_out_status(datetime(2026, 10, 5, 21, 0, tzinfo=TZ), reminder)
    assert coll.day == date(2026, 10, 6) and change == datetime(2026, 10, 6, 5, 30, tzinfo=TZ)
    # Jour J après 5h30 : inactif, prochaine fenêtre le 15/10 à 18h
    coll, change = sched.take_out_status(datetime(2026, 10, 6, 7, 0, tzinfo=TZ), reminder)
    assert coll is None and change == datetime(2026, 10, 15, 18, 0, tzinfo=TZ)
    # Après la dernière collecte : plus rien
    assert sched.take_out_status(datetime(2026, 11, 4, 7, 0, tzinfo=TZ), reminder) == (None, None)


def test_collections_between(sched):
    days = [c.day for c in sched.collections_between(date(2026, 10, 1), date(2026, 10, 20))]
    assert days == [date(2026, 10, 2), date(2026, 10, 6), date(2026, 10, 16)]


def test_outdated(sched):
    assert not sched.is_outdated(date(2026, 10, 1))
    assert sched.is_outdated(date(2026, 11, 4))  # plus de date à venir
    assert sched.is_outdated(date(2027, 10, 1))


def test_waste_name_language(sched):
    assert sched.waste_types["recyclables"].name("fr") == "Déchets recyclables"
    assert sched.waste_types["recyclables"].name("en-GB") == "Recyclables"
    assert sched.waste_types["recyclables"].name("de") == "Recyclables"


def test_invalid_data():
    with pytest.raises(schedule.InvalidDataError):
        schedule.parse_schedule(RAW, "inconnue")
    with pytest.raises(schedule.InvalidDataError):
        schedule.list_zones({**RAW, "schema_version": 99})
    assert schedule.list_zones(RAW) == {"acigne": "Acigné"}


def test_published_file_is_valid():
    import json

    data = json.loads((PATH.parents[2] / "data" / "collectes.json").read_text(encoding="utf-8"))
    zones = schedule.list_zones(data)
    assert len(zones) == 53
    for zone_id in zones:
        assert schedule.parse_schedule(data, zone_id).next_collection(date(2026, 10, 1)) is not None
