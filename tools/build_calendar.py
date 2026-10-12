"""Convertit les calendriers PDF de Rennes Métropole en JSON pour l'intégration HA.

Usage :
    python tools/build_calendar.py            # traite sources/*/ et écrit data/
    python tools/build_calendar.py --strict   # code retour 1 s'il y a des écarts

Chaque sous-dossier de ``sources/`` correspond à une saison (ex. ``2026-2027``)
et contient les PDF « Vos collectes de déchets » tels que publiés par la
métropole. Le script peut être relancé à volonté : il régénère entièrement
``data/collectes.json`` et ``data/rapport.md``.

Principe : les jours de collecte sont lus dans les cases colorées du PDF
(gris = ordures ménagères, jaune = recyclables), qui intègrent déjà les
reports de jours fériés. La règle imprimée en légende (« Mardi - Semaine
impaire ») sert uniquement à contrôler le résultat.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = ROOT / "sources"
DATA_DIR = ROOT / "data"

SCHEMA_VERSION = 1

MONTHS = {
    "JANVIER": 1, "FÉVRIER": 2, "MARS": 3, "AVRIL": 4, "MAI": 5, "JUIN": 6,
    "JUILLET": 7, "AOÛT": 8, "SEPTEMBRE": 9, "OCTOBRE": 10, "NOVEMBRE": 11,
    "DÉCEMBRE": 12,
}
WEEKDAYS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5}

# Couleurs de remplissage des cases (RVB 0-1) et flux correspondant.
WASTE_COLORS = {
    "ordures_menageres": (0.745, 0.735, 0.741),
    "recyclables": (1.0, 0.8, 0.0),
}
COLOR_TOLERANCE = 0.06

LEGEND_LABELS = {
    "ORDURES MÉNAGÈRES": "ordures_menageres",
    "DÉCHETS RECYCLABLES": "recyclables",
}

WASTE_TYPES = {
    "ordures_menageres": {"fr": "Ordures ménagères", "en": "Household waste", "bin": "gris"},
    "recyclables": {"fr": "Déchets recyclables", "en": "Recyclables", "bin": "jaune"},
}

# Les 43 communes de la métropole, pour vérifier la couverture.
METROPOLE_COMMUNES = [
    "Acigné", "Bécherel", "Betton", "Bourgbarré", "Brécé", "Bruz", "Cesson-Sévigné",
    "Chantepie", "Chartres-de-Bretagne", "Chavagne", "Chevaigné", "Cintré", "Clayes",
    "Corps-Nuds", "Gévezé", "L'Hermitage", "La Chapelle-Chaussée",
    "La Chapelle-des-Fougeretz", "La Chapelle-Thouarault", "Laillé", "Langan",
    "Le Rheu", "Le Verger", "Miniac-sous-Bécherel", "Montgermont", "Mordelles",
    "Nouvoitou", "Noyal-Châtillon-sur-Seiche", "Orgères", "Pacé",
    "Parthenay-de-Bretagne", "Pont-Péan", "Rennes", "Romillé", "Saint-Armel",
    "Saint-Erblon", "Saint-Gilles", "Saint-Grégoire", "Saint-Jacques-de-la-Lande",
    "Saint-Sulpice-la-Forêt", "Thorigné-Fouillard", "Vern-sur-Seiche",
    "Vezin-le-Coquet",
]
# Graphies du PDF à corriger.
COMMUNE_ALIASES = {"La-Chapelle-Chaussée": "La Chapelle-Chaussée"}


class ParseError(Exception):
    """Le PDF ne correspond pas au format attendu."""


@dataclass
class Rule:
    weekday: int
    parity: str  # "paire" | "impaire"

    def __str__(self) -> str:
        day = [k for k, v in WEEKDAYS.items() if v == self.weekday][0]
        return f"{day} – semaine {self.parity}"


@dataclass
class Calendar:
    source: Path
    titles: list[str]
    season: str
    rules: dict[str, Rule] = field(default_factory=dict)
    collections: dict[str, list[dt.date]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Zone:
    id: str
    name: str
    commune: str
    calendar: Calendar


# --------------------------------------------------------------------------- #
# Lecture du PDF
# --------------------------------------------------------------------------- #

def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text).strip()


def _spans(page: pymupdf.Page) -> list[dict]:
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                text = _nfc(span["text"])
                if text:
                    spans.append({**span, "text": text})
    return spans


def _color_match(fill, ref) -> bool:
    return fill is not None and all(abs(a - b) <= COLOR_TOLERANCE for a, b in zip(fill, ref))


def _filled_rects(page: pymupdf.Page):
    """Retourne (flux, rect) pour chaque case colorée de la page."""
    for drawing in page.get_drawings():
        fill = drawing.get("fill")
        waste = next((w for w, c in WASTE_COLORS.items() if _color_match(fill, c)), None)
        if waste is None:
            continue
        rects = []
        for item in drawing["items"]:
            if item[0] == "re":
                rects.append(pymupdf.Rect(item[1]))
            elif item[0] == "qu":
                rects.append(item[1].rect)
        if not rects:  # chemin tracé en lignes : on prend son enveloppe
            rects.append(pymupdf.Rect(drawing["rect"]))
        for rect in rects:
            yield waste, rect


def _parse_titles(spans: list[dict]) -> list[str]:
    titles = [s["text"] for s in spans if s["bbox"][1] < 40 and s["font"].startswith("BrandonGrotesque-Bold")]
    if not titles:
        raise ParseError("titre de zone introuvable en haut de page")
    return titles


def _parse_rules(text: str) -> dict[str, Rule]:
    rules = {}
    for label, waste in LEGEND_LABELS.items():
        m = re.search(re.escape(label) + r"\s*\n\s*(\w+)\s*-\s*Semaine\s+(paire|impaire)", text, re.I)
        if m and m.group(1).lower() in WEEKDAYS:
            rules[waste] = Rule(WEEKDAYS[m.group(1).lower()], m.group(2).lower())
    return rules


def _parse_page(page: pymupdf.Page, cal: Calendar) -> None:
    spans = _spans(page)

    # Colonnes de mois : en-têtes « OCTOBRE 2026 »
    columns = []
    for s in spans:
        m = re.fullmatch(r"([A-ZÉÛÈ]+)\s+(\d{4})", s["text"])
        if m and m.group(1) in MONTHS:
            x0, y0, x1, y1 = s["bbox"]
            columns.append({"month": MONTHS[m.group(1)], "year": int(m.group(2)),
                            "cx": (x0 + x1) / 2, "top": y1, "days": {}})
    if len(columns) != 6:
        raise ParseError(f"page {page.number + 1} : {len(columns)} mois trouvés au lieu de 6")
    columns.sort(key=lambda c: c["cx"])
    half_width = min(b["cx"] - a["cx"] for a, b in zip(columns, columns[1:])) / 2

    # Numéros de jour : petits chiffres alignés à gauche de chaque colonne
    for s in spans:
        if not s["text"].isdigit() or s["size"] > 10:
            continue
        x0, y0, x1, y1 = s["bbox"]
        for col in columns:
            if col["cx"] - half_width <= x0 <= col["cx"] - half_width * 0.6 and y0 > col["top"]:
                col["days"][int(s["text"])] = (y0 + y1) / 2

    for col in columns:
        days = col["days"]
        expected = _month_length(col["year"], col["month"])
        if sorted(days) != list(range(1, expected + 1)):
            raise ParseError(f"{col['month']:02d}/{col['year']} : jours lus {sorted(days)}")
        col["row_height"] = (days[expected] - days[1]) / (expected - 1)

    # Cases colorées -> dates
    for waste, rect in _filled_rects(page):
        cx, cy = (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
        col = next((c for c in columns if abs(cx - c["cx"]) <= half_width), None)
        if col is None:
            continue  # légende, hors calendrier
        day, y = min(col["days"].items(), key=lambda kv: abs(kv[1] - cy))
        if abs(y - cy) > col["row_height"] * 0.6:
            cal.warnings.append(f"case {waste} non rattachée à un jour ({col['month']:02d}/{col['year']}, y={cy:.0f})")
            continue
        cal.collections.setdefault(waste, []).append(dt.date(col["year"], col["month"], day))


def _month_length(year: int, month: int) -> int:
    nxt = dt.date(year + month // 12, month % 12 + 1, 1)
    return (nxt - dt.timedelta(days=1)).day


def parse_pdf(path: Path, season: str) -> Calendar:
    doc = pymupdf.open(path)
    first = doc[0]
    cal = Calendar(source=path, titles=_parse_titles(_spans(first)), season=season)
    cal.rules = _parse_rules(first.get_text())
    for page in doc:
        _parse_page(page, cal)
    for waste in cal.collections:
        cal.collections[waste] = sorted(set(cal.collections[waste]))
    return cal


# --------------------------------------------------------------------------- #
# Zones
# --------------------------------------------------------------------------- #

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def zones_from_calendar(cal: Calendar) -> list[Zone]:
    zones = []
    for title in cal.titles:
        m = re.fullmatch(r"Rennes\s+Q(\d+)\s*:\s*(.+)", title)
        if m:
            zones.append(Zone(f"rennes-q{int(m.group(1))}", f"Rennes – Q{int(m.group(1))} : {m.group(2)}", "Rennes", cal))
            continue
        for commune in (c.strip() for c in title.split("|")):
            commune = COMMUNE_ALIASES.get(commune, commune).replace("’", "'")
            zones.append(Zone(slugify(commune), commune, commune, cal))
    return zones


# --------------------------------------------------------------------------- #
# Contrôle par rapport à la règle imprimée
# --------------------------------------------------------------------------- #

def easter(year: int) -> dt.date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def public_holidays(year: int) -> dict[dt.date, str]:
    e = easter(year)
    return {
        dt.date(year, 1, 1): "Jour de l'an", e + dt.timedelta(days=1): "Lundi de Pâques",
        dt.date(year, 5, 1): "Fête du travail", dt.date(year, 5, 8): "Victoire 1945",
        e + dt.timedelta(days=39): "Ascension", e + dt.timedelta(days=50): "Lundi de Pentecôte",
        dt.date(year, 7, 14): "Fête nationale", dt.date(year, 8, 15): "Assomption",
        dt.date(year, 11, 1): "Toussaint", dt.date(year, 11, 11): "Armistice",
        dt.date(year, 12, 25): "Noël",
    }


# Fériés sans décalage (« collecte maintenue » sur les calendriers).
MAINTAINED_HOLIDAYS = {"Ascension"}


def expected_dates(rule: Rule, start: dt.date, end: dt.date) -> list[dt.date]:
    """Dates théoriques : jour + parité ISO, décalées d'un jour après un férié de la semaine."""
    holidays = {d: n for d, n in {**public_holidays(start.year), **public_holidays(end.year)}.items()
                if n not in MAINTAINED_HOLIDAYS}
    dates = []
    day = start
    while day <= end:
        week = day.isocalendar().week
        if day.weekday() == rule.weekday and (week % 2 == 0) == (rule.parity == "paire"):
            monday = day - dt.timedelta(days=day.weekday())
            shift = any(monday + dt.timedelta(days=i) in holidays for i in range(rule.weekday + 1))
            dates.append(day + dt.timedelta(days=1) if shift else day)
        day += dt.timedelta(days=1)
    return dates


def season_bounds(season: str) -> tuple[dt.date, dt.date]:
    first, second = (int(y) for y in season.split("-"))
    return dt.date(first, 10, 1), dt.date(second, 9, 30)


def check_calendar(cal: Calendar) -> list[str]:
    issues = list(cal.warnings)
    start, end = season_bounds(cal.season)
    holidays = {**public_holidays(start.year), **public_holidays(end.year)}
    for waste in WASTE_TYPES:
        found = cal.collections.get(waste, [])
        if not found:
            issues.append(f"**{WASTE_TYPES[waste]['fr']}** : aucune collecte lue")
            continue
        out = [d for d in found if not start <= d <= end]
        if out:
            issues.append(f"{WASTE_TYPES[waste]['fr']} : dates hors saison {', '.join(map(str, out))}")
        rule = cal.rules.get(waste)
        if rule is None:
            issues.append(f"{WASTE_TYPES[waste]['fr']} : règle de légende illisible")
            continue
        expected = set(expected_dates(rule, start, end))
        for d in sorted(set(found) - expected):
            note = f" ({holidays[d - dt.timedelta(days=1)]} la veille)" if d - dt.timedelta(days=1) in holidays else ""
            issues.append(f"{WASTE_TYPES[waste]['fr']} : collecte le {_fr(d)} non prévue par la règle{note}")
        for d in sorted(expected - set(found)):
            issues.append(f"{WASTE_TYPES[waste]['fr']} : pas de collecte le {_fr(d)} alors que la règle la prévoit")
    return issues


def _fr(d: dt.date) -> str:
    return f"{['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim'][d.weekday()]}. {d:%d/%m/%Y}"


# --------------------------------------------------------------------------- #
# Programme principal
# --------------------------------------------------------------------------- #

def build(sources_dir: Path) -> tuple[dict, str, int]:
    seasons, zones, report, problems = [], {}, [], 0
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    report.append(f"# Rapport de conversion des calendriers\n\nGénéré le {now:%d/%m/%Y à %H:%M} UTC.\n")

    for season_dir in sorted(p for p in sources_dir.iterdir() if p.is_dir()):
        season = season_dir.name
        if not re.fullmatch(r"\d{4}-\d{4}", season):
            print(f"Dossier ignoré (nom attendu AAAA-AAAA) : {season_dir}", file=sys.stderr)
            continue
        start, end = season_bounds(season)
        seasons.append({"id": season, "start": start.isoformat(), "end": end.isoformat()})
        report.append(f"## Saison {season}\n")
        rows, details, seen = [], [], set()

        for pdf in sorted(season_dir.glob("*.pdf")):
            try:
                cal = parse_pdf(pdf, season)
            except ParseError as err:
                problems += 1
                details.append(f"### ❌ {pdf.name}\n\nPDF non exploitable : {err}\n")
                continue
            issues = check_calendar(cal)
            problems += len(issues)
            for zone in zones_from_calendar(cal):
                seen.add(zone.commune)
                entry = zones.setdefault(zone.id, {"name": zone.name, "commune": zone.commune,
                                                   "collections": {w: [] for w in WASTE_TYPES}})
                entry["name"] = zone.name  # le nom le plus récent l'emporte
                for waste, dates in cal.collections.items():
                    entry["collections"][waste] = sorted(set(entry["collections"][waste]) | {d.isoformat() for d in dates})
            counts = " / ".join(str(len(cal.collections.get(w, []))) for w in WASTE_TYPES)
            rules = " / ".join(str(cal.rules.get(w, "?")) for w in WASTE_TYPES)
            status = "✅" if not issues else f"⚠️ {len(issues)}"
            rows.append(f"| {' + '.join(cal.titles).replace('|', '/')} | `{pdf.name}` | {rules} | {counts} | {status} |")
            if issues:
                details.append(f"### ⚠️ {' + '.join(cal.titles).replace('|', '/')} (`{pdf.name}`)\n\n" + "\n".join(f"- {i}" for i in issues) + "\n")

        report.append("| Zone(s) | Fichier | Règle OM / recyclables | Nb collectes OM / recyclables | Contrôle |")
        report.append("|---|---|---|---|---|")
        report.extend(rows)
        report.append("")
        missing = [c for c in METROPOLE_COMMUNES if c not in seen]
        if missing:
            report.append(f"**Communes sans calendrier :** {', '.join(missing)}\n")
        if details:
            report.append("### Écarts à vérifier\n")
            report.append("Les dates publiées sont celles lues dans les cases colorées du PDF. "
                          "Un écart avec la règle de légende est normal autour des jours fériés "
                          "ou des semaines 53/1 ; sinon, vérifiez le PDF.\n")
            report.extend(details)

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now.isoformat(),
        "source": "https://dechets.metropole.rennes.fr/ou-et-comment-jeter-vos-dechets/",
        "seasons": seasons,
        "valid_until": max((s["end"] for s in seasons), default=None),
        "collection_start": "05:30",
        "waste_types": WASTE_TYPES,
        "zones": dict(sorted(zones.items(), key=_zone_sort_key)),
    }
    report.insert(1, f"**{len(zones)} zones**, {problems} point(s) à vérifier.\n")
    return data, "\n".join(report), problems


def _zone_sort_key(item: tuple[str, dict]) -> tuple:
    """Rennes d'abord, par numéro de quartier, puis les communes par ordre alphabétique."""
    zone_id, zone = item
    m = re.fullmatch(r"rennes-q(\d+)", zone_id)
    return (0, int(m.group(1)), "") if m else (1, 0, slugify(zone["name"]))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sources", type=Path, default=SOURCES_DIR)
    parser.add_argument("--output", type=Path, default=DATA_DIR)
    parser.add_argument("--strict", action="store_true", help="code retour 1 si des écarts sont détectés")
    args = parser.parse_args()

    data, report, problems = build(args.sources)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "collectes.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.output / "rapport.md").write_text(report, encoding="utf-8")
    print(f"{len(data['zones'])} zones écrites dans {args.output / 'collectes.json'}")
    print(f"{problems} point(s) à vérifier : voir {args.output / 'rapport.md'}")
    return 1 if args.strict and problems else 0


if __name__ == "__main__":
    sys.exit(main())
