"""Constantes de l'intégration Collecte Déchets Rennes Métropole."""

from datetime import timedelta

DOMAIN = "collecte_dechets_rennes_metropole"

CONF_ZONE = "zone"
CONF_DATA_URL = "data_url"
CONF_REMINDER_TIME = "reminder_time"

# Modifiable dans les options de l'intégration.
DEFAULT_DATA_URL = (
    "https://raw.githubusercontent.com/phnogues/collecte-dechets-rennes-metropole-ha/main/data/collectes.json"
)
DEFAULT_REMINDER_TIME = "18:00:00"

UPDATE_INTERVAL = timedelta(hours=12)
REQUEST_TIMEOUT = 30

ATTRIBUTION = "Données : Rennes Métropole (calendriers de collecte)"
