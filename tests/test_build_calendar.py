"""Tests du script de conversion, sur les PDF réels de la saison 2026-2027."""

import datetime as dt
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_calendar as bc  # noqa: E402

SEASON_DIR = ROOT / "sources" / "2026-2027"
D = dt.date

pytestmark = pytest.mark.skipif(not SEASON_DIR.exists(), reason="PDF 2026-2027 absents")


def test_acigne_dates_and_rules():
    cal = bc.parse_pdf(SEASON_DIR / "31d8e5225d.pdf", "2026-2027")
    assert cal.titles == ["Acigné"]
    assert str(cal.rules["ordures_menageres"]) == "mardi – semaine impaire"
    om, cs = cal.collections["ordures_menageres"], cal.collections["recyclables"]
    assert om[:3] == [D(2026, 10, 6), D(2026, 10, 20), D(2026, 11, 3)]
    assert om[-1] == D(2027, 9, 28)
    # Semaines 53 et 1 : deux collectes de bac gris consécutives
    assert D(2026, 12, 29) in om and D(2027, 1, 5) in om
    # Report de Noël (vendredi -> samedi) et de l'Armistice
    assert D(2026, 12, 26) in cs and D(2026, 12, 25) not in cs
    assert D(2026, 11, 14) in cs
    # Ascension : collecte maintenue le vendredi
    assert D(2027, 5, 7) in cs
    # Lundi de Pâques : mardi -> mercredi
    assert D(2027, 3, 31) in om and D(2027, 3, 30) not in om


def test_shared_calendar_gives_several_zones():
    cal = bc.parse_pdf(SEASON_DIR / "8fb42c085f.pdf", "2026-2027")
    zones = {z.id: z.name for z in bc.zones_from_calendar(cal)}
    assert zones == {"rennes-q7": "Rennes – Q7 : La Pommeraie", "rennes-q10": "Rennes – Q10 : Villejean | Beauregard"}

    cal = bc.parse_pdf(SEASON_DIR / "765f719176.pdf", "2026-2027")
    assert "la-chapelle-chaussee" in {z.id for z in bc.zones_from_calendar(cal)}


def test_expected_dates_rule():
    rule = bc.Rule(weekday=4, parity="paire")  # vendredi, semaine paire
    dates = bc.expected_dates(rule, D(2026, 12, 1), D(2027, 1, 31))
    assert D(2026, 12, 26) in dates  # Noël un vendredi -> samedi
    assert D(2026, 12, 11) in dates


def test_full_build_covers_all_communes(tmp_path):
    data, report, _ = bc.build(ROOT / "sources")
    communes = {z["commune"] for z in data["zones"].values()}
    assert communes == set(bc.METROPOLE_COMMUNES)
    assert data["valid_until"] == "2027-09-30"
    for zone in data["zones"].values():
        for dates in zone["collections"].values():
            assert 24 <= len(dates) <= 28
