"""Télécharge les calendriers PDF publiés sur le site déchets de Rennes Métropole.

Usage :
    python tools/download_sources.py 2027-2028

Les PDF sont enregistrés dans ``sources/<saison>/``. Les liens de la page
pointent vers des liseuses Heyzine ; on récupère le PDF d'origine qu'elles
affichent. Vous pouvez aussi déposer les PDF à la main dans ce dossier.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_URL = "https://dechets.metropole.rennes.fr/ou-et-comment-jeter-vos-dechets/"
HEADERS = {"User-Agent": "Mozilla/5.0 (collecte-dechets-rennes-metropole)"}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as resp:
        return resp.read()


def calendar_links(page: str) -> dict[str, str]:
    """{url liseuse: libellé} pour chaque lien de calendrier de la page."""
    links: dict[str, str] = {}
    for m in re.finditer(r'<a[^>]*href="?([^" >]*heyzine\.com/flip-book/[^" >]+)"?[^>]*>(.*?)</a>', page, re.S):
        label = unicodedata.normalize("NFC", html.unescape(re.sub(r"<[^>]+>", "", m.group(2))))
        label = label.replace("(lien externe)", "").strip()
        if "Document cadre" not in label:
            links.setdefault(m.group(1), label)
    return links


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("season", help="saison, ex. 2027-2028")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{4}", args.season):
        parser.error("la saison doit être au format AAAA-AAAA")

    out = ROOT / "sources" / args.season
    out.mkdir(parents=True, exist_ok=True)
    links = calendar_links(fetch(PAGE_URL).decode("utf-8", "ignore"))
    if not links:
        print("Aucun lien de calendrier trouvé : la page a peut-être changé.", file=sys.stderr)
        return 1

    for url, label in links.items():
        viewer = fetch(url).decode("utf-8", "ignore")
        m = re.search(r"https://cdn\w*\.heyzine\.com/files/uploaded/[0-9a-f-]+\.pdf", viewer)
        if not m:
            print(f"PDF introuvable pour {label} ({url})", file=sys.stderr)
            continue
        target = out / (url.rsplit("/", 1)[1].removesuffix(".html") + ".pdf")
        target.write_bytes(fetch(m.group(0)))
        print(f"{target.name}  {label}")
    print(f"\n{len(links)} calendriers dans {out}. Lancez ensuite : python tools/build_calendar.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
