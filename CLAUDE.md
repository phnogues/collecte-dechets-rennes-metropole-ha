# CLAUDE.md

Intégration Home Assistant (HACS) qui expose les jours de collecte des déchets de Rennes Métropole. Dépôt public : https://github.com/phnogues/collecte-dechets-rennes-metropole-ha. Le README décrit l'usage ; ce fichier liste ce qu'il faut savoir pour modifier le projet.

## Organisation

- `custom_components/collecte_dechets_rennes_metropole/` : l'intégration (domaine `collecte_dechets_rennes_metropole`). La logique de calendrier pure est dans `schedule.py`, sans dépendance à Home Assistant ; le reste est la couche HA (config flow, coordinator, entités).
- `tools/build_calendar.py` : convertit les PDF de `sources/<saison>/` en `data/collectes.json` + `data/rapport.md`.
- `data/collectes.json` : téléchargé par les installations depuis `raw.githubusercontent.com/.../main/data/collectes.json` (`DEFAULT_DATA_URL` dans `const.py`). Le pousser sur `main` suffit à mettre à jour tous les utilisateurs : renommer le dépôt, la branche ou ce fichier casse les installations existantes.
- `tools/video/` : génération locale de la vidéo de démo, volontairement hors git (`.gitignore`).

## Commandes

```bash
python -m pytest                                   # tests du script et de schedule.py (Windows OK)
python tools/build_calendar.py                     # régénère data/ depuis sources/
python tools/build_calendar.py --strict            # code 1 s'il y a des écarts de contrôle
```

Les tests de `tests/ha/` nécessitent Linux et Python 3.14 (`pytest-homeassistant-custom-component`) : ils tournent en CI ou dans Docker (voir README).

## Règles

- Les dates publiées sont celles des cases colorées des PDF, jamais celles recalculées par la règle de légende : la règle sert seulement de contrôle (`rapport.md`).
- Si la mise en page d'un PDF change, le script doit s'arrêter avec un message explicite plutôt que produire des dates fausses.
- Les identifiants de zone (commune, ou numéro de quartier à Rennes) doivent rester stables d'une saison à l'autre : ce sont les `unique_id` des entrées de configuration.
- Toute chaîne visible est traduite dans `strings.json`, `translations/fr.json` et `translations/en.json`.
- Après une modification de `sources/`, `tools/build_calendar.py` ou `data/`, régénérer et committer `data/collectes.json` : le workflow `calendar.yml` échoue sinon.

## Mise à jour annuelle (septembre)

Les calendriers vont d'octobre à septembre. Saison en cours : 2026-2027, valable jusqu'au 30 septembre 2027.

1. `python tools/download_sources.py 2027-2028`
2. `python tools/build_calendar.py`, puis relire `data/rapport.md`
3. Committer et pousser `sources/` et `data/` : pas besoin de nouvelle release.

## Release

Incrémenter `version` dans `manifest.json`, pousser, attendre que les workflows Validate et Tests soient verts, puis `gh release create vX.Y.Z` avec le même numéro.
