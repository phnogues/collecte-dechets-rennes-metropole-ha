"""Téléchargement du fichier de données (URL http(s) ou chemin local)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import REQUEST_TIMEOUT
from .schedule import InvalidDataError, list_zones


class CannotFetchError(Exception):
    """Le fichier de données est injoignable."""


async def async_fetch_data(hass: HomeAssistant, url: str) -> dict:
    """Récupère et valide sommairement le JSON des collectes."""
    try:
        if url.startswith(("http://", "https://")):
            session = async_get_clientsession(hass)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as resp:
                resp.raise_for_status()
                # raw.githubusercontent.com sert du text/plain : on ignore le content-type.
                data = json.loads(await resp.text())
        else:
            path = Path(url.removeprefix("file://"))
            data = json.loads(await hass.async_add_executor_job(path.read_text, "utf-8"))
    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        raise CannotFetchError(str(err)) from err
    except ValueError as err:
        raise InvalidDataError(f"JSON invalide : {err}") from err
    if not isinstance(data, dict):
        raise InvalidDataError("le fichier ne contient pas un objet JSON")
    list_zones(data)  # lève InvalidDataError si la structure est incorrecte
    return data
