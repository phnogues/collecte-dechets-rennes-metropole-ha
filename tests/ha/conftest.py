"""Fixtures pour les tests avec Home Assistant."""

from pathlib import Path

import pytest

DATA_FILE = str(Path(__file__).resolve().parents[2] / "data" / "collectes.json")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def paris(hass):
    await hass.config.async_set_time_zone("Europe/Paris")
    return hass
