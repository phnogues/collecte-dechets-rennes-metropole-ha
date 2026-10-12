# Collecte Déchets Rennes Métropole

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Validate](https://github.com/phnogues/collecte-dechets-rennes-metropole-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/phnogues/collecte-dechets-rennes-metropole-ha/actions/workflows/validate.yml)
[![Tests](https://github.com/phnogues/collecte-dechets-rennes-metropole-ha/actions/workflows/tests.yml/badge.svg)](https://github.com/phnogues/collecte-dechets-rennes-metropole-ha/actions/workflows/tests.yml)

Intégration Home Assistant qui affiche les jours de collecte des **ordures ménagères (bac gris)** et des **déchets recyclables (bac jaune)** pour les 43 communes de Rennes Métropole et les quartiers de Rennes.

Les données proviennent des calendriers PDF publiés chaque année par la métropole sur [dechets.metropole.rennes.fr](https://dechets.metropole.rennes.fr/ou-et-comment-jeter-vos-dechets/). Un script les convertit en un fichier `data/collectes.json`, que l'intégration télécharge.

> Les calendriers concernent les **maisons disposant de bacs roulants**. Le centre-ville de Rennes (Q1) et l'habitat collectif n'ont pas de calendrier publié.

## Démo

https://github.com/user-attachments/assets/3e69c0be-e278-4a1d-b720-ef1f48512f86

## Installation (HACS)

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=phnogues&repository=collecte-dechets-rennes-metropole-ha&category=integration)

1. HACS → menu ⋮ → *Dépôts personnalisés* → ajouter `https://github.com/phnogues/collecte-dechets-rennes-metropole-ha`, catégorie *Intégration* (ou cliquer sur le bouton ci-dessus).
2. Installer « Collecte Déchets Rennes Métropole », puis redémarrer Home Assistant.
3. *Paramètres → Appareils et services → Ajouter une intégration* → « Collecte Déchets Rennes Métropole ».
4. Choisir sa commune (ou son quartier à Rennes) dans la liste.

Vous pouvez ajouter plusieurs zones (une entrée par zone).

### Options

| Option | Par défaut | Rôle |
|---|---|---|
| Heure du rappel | 18:00 | Heure à laquelle « Sortir le bac » s'active la veille de la collecte |
| URL du fichier de données | `DEFAULT_DATA_URL` (voir `const.py`) | URL http(s) de `collectes.json`, ou chemin local (ex. `/config/collectes.json`) |

## Entités créées (par zone)

Les identifiants ci-dessous correspondent à une installation en français (en anglais : `..._put_the_bin_out`, etc.).

| Entité | État | Attributs |
|---|---|---|
| `calendar.<zone>_collectes` | Prochaine collecte | Un événement « journée entière » par jour de collecte |
| `sensor.<zone>_ordures_menageres` | Date du prochain passage du bac gris | `days_until`, `bin`, `upcoming` (5 prochaines dates) |
| `sensor.<zone>_dechets_recyclables` | Date du prochain passage du bac jaune | idem |
| `sensor.<zone>_prochaine_collecte` | Date du prochain passage, tous bacs confondus | `days_until`, `waste_types`, `bins`, `description` |
| `binary_sensor.<zone>_sortir_le_bac` | `on` de la veille (heure du rappel) jusqu'au début de la collecte (5h30) | `collection_date`, `waste_types`, `bins`, `description` |

### Exemple d'automatisation

```yaml
automation:
  - alias: "Rappel poubelles"
    triggers:
      - trigger: state
        entity_id: binary_sensor.acigne_sortir_le_bac
        to: "on"
    actions:
      - action: notify.mobile_app_mon_telephone
        data:
          title: "Poubelles"
          message: "Sortir ce soir : {{ state_attr('binary_sensor.acigne_sortir_le_bac', 'description') }}"
```

Si le calendrier n'a plus de dates à venir (après le 30 septembre sans nouveau fichier), une alerte apparaît dans *Paramètres → Réparations*. Si le fichier est injoignable, l'intégration utilise la dernière version téléchargée.

## Mise à jour annuelle des données

Les nouveaux calendriers (octobre → septembre) sont publiés en septembre.

```bash
pip install -r tools/requirements.txt
```

1. Télécharger les PDF de la nouvelle saison dans `sources/<saison>/`, ou les y déposer à la main :
   ```bash
   python tools/download_sources.py 2027-2028
   ```
2. Générer le JSON et le rapport de contrôle :
   ```bash
   python tools/build_calendar.py
   ```
3. Relire `data/rapport.md`, puis publier `data/collectes.json` (commit + push). Pas besoin de nouvelle version de l'intégration.

Le script peut être relancé à volonté. Il traite **toutes** les saisons présentes dans `sources/`, ce qui permet de publier la nouvelle saison avant le 1er octobre sans perdre les dates de fin septembre. Les zones sont identifiées par commune (ou numéro de quartier pour Rennes) : une configuration existante reste valable d'une année sur l'autre, même si les regroupements de communes changent.

### Fonctionnement du script

- Chaque PDF contient 12 colonnes de mois. Les jours de collecte sont les **cases colorées** : gris pour les ordures ménagères, jaune pour les recyclables. Ces cases intègrent déjà les reports de jours fériés.
- Le titre du PDF donne les communes (`Betton | Saint-Sulpice-la-Forêt | …`) ou le quartier de Rennes.
- **Contrôle** : la règle imprimée en légende (ex. « Mardi – Semaine impaire ») est rejouée avec les reports de jours fériés. Toute différence apparaît dans `data/rapport.md`. Les anomalies propres aux PDF y sont signalées, mais les dates publiées restent celles du PDF.
- `python tools/build_calendar.py --strict` renvoie le code 1 s'il y a des écarts (utile en CI).

Si la métropole change la mise en page, le script s'arrête sur le PDF concerné avec un message explicite, au lieu de produire des dates fausses.

## Format de `data/collectes.json`

```jsonc
{
  "schema_version": 1,
  "generated_at": "2026-10-05T14:05:00+00:00",
  "seasons": [{"id": "2026-2027", "start": "2026-10-01", "end": "2027-09-30"}],
  "valid_until": "2027-09-30",
  "collection_start": "05:30",
  "waste_types": {
    "ordures_menageres": {"fr": "Ordures ménagères", "en": "Household waste", "bin": "gris"},
    "recyclables": {"fr": "Déchets recyclables", "en": "Recyclables", "bin": "jaune"}
  },
  "zones": {
    "acigne": {
      "name": "Acigné",
      "commune": "Acigné",
      "collections": {
        "ordures_menageres": ["2026-10-06", "2026-10-20", "..."],
        "recyclables": ["2026-10-02", "..."]
      }
    }
  }
}
```

## Développement

```bash
python -m pytest
```

Lance les tests du script et de la logique de calendrier. Les tests Home Assistant (`tests/ha/`) nécessitent Linux ; ils tournent dans Docker :

```bash
docker build -t collecte-ha-test -f tests/docker/Dockerfile tools
```

```bash
docker run --rm -v "$PWD:/src" -w /src collecte-ha-test
```

## Intégration continue

| Workflow | Déclenchement | Rôle |
|---|---|---|
| `validate.yml` | chaque push + quotidien | HACS Action et Hassfest (exigés pour HACS) |
| `tests.yml` | chaque push | `pytest`, y compris les tests Home Assistant |
| `calendar.yml` | modification de `sources/`, `tools/build_calendar.py` ou `data/` | reconvertit les PDF, affiche le rapport de contrôle dans le résumé du workflow, et échoue si `data/collectes.json` n'a pas été régénéré |

L'icône (`custom_components/collecte_dechets_rennes_metropole/brand/`) est générée par `python tools/brand/make_icon.py` (Pillow). Elle est servie localement par Home Assistant depuis la version 2026.3.

## Publication

1. Mettre à jour `version` dans `manifest.json`, pousser, puis vérifier que les workflows *Validate* et *Tests* sont verts.
2. Créer une **release GitHub** avec le même numéro (ex. `v0.1.0`).
3. Pour la liste par défaut de HACS : forker [hacs/default](https://github.com/hacs/default), ajouter l'URL du dépôt dans le fichier `integration` (ordre alphabétique), et ouvrir la PR en remplissant tout le modèle. La relecture prend plusieurs mois.

## Licence

Code sous licence [MIT](LICENSE). Les calendriers de collecte (`sources/`, `data/`) sont des informations publiques de Rennes Métropole, réutilisées avec mention de la source.
