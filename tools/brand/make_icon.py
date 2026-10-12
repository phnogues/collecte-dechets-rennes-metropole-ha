"""Génère l'icône de l'intégration (bac gris + bac jaune) dans brand/.

Usage : python tools/brand/make_icon.py   (nécessite Pillow)
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "custom_components" / "collecte_dechets_rennes_metropole" / "brand"
S = 2048  # dessin en haute résolution puis réduction (anticrénelage)

GREY, GREY_DARK = (122, 128, 134), (78, 83, 88)
YELLOW, YELLOW_DARK = (255, 200, 0), (214, 158, 0)
WHEEL = (45, 48, 52)


def bin_(d: ImageDraw.ImageDraw, x: int, w: int, top: int, body, lid, symbol: str) -> None:
    bottom = int(S * 0.90)
    # Cuve légèrement évasée vers le haut
    d.polygon([(x + w * 0.04, top), (x + w * 0.96, top), (x + w * 0.88, bottom), (x + w * 0.12, bottom)], fill=body)
    # Couvercle + poignée
    d.rounded_rectangle([x - w * 0.02, top - S * 0.075, x + w * 1.02, top + S * 0.01], radius=S * 0.03, fill=lid)
    d.rounded_rectangle([x + w * 0.35, top - S * 0.115, x + w * 0.65, top - S * 0.06], radius=S * 0.02, fill=lid)
    # Roue
    r = S * 0.055
    cx, cy = x + w * 0.80, bottom
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHEEL)
    # Pictogramme
    cx, cy, u = x + w / 2, (top + bottom) / 2, w * 0.2
    white = (255, 255, 255)
    if symbol == "bag":  # sac poubelle noué
        d.ellipse([cx - u * 1.05, cy - u * 0.55, cx + u * 1.05, cy + u * 1.25], fill=white)
        d.polygon([(cx - u * 0.3, cy - u * 0.35), (cx + u * 0.3, cy - u * 0.35), (cx, cy - u * 0.7)], fill=white)
        d.polygon([(cx, cy - u * 0.65), (cx - u * 0.6, cy - u * 1.15), (cx - u * 0.15, cy - u * 1.2)], fill=white)
        d.polygon([(cx, cy - u * 0.65), (cx + u * 0.6, cy - u * 1.15), (cx + u * 0.15, cy - u * 1.2)], fill=white)
    else:  # flèche circulaire (recyclage)
        r, width = u * 1.0, int(u * 0.38)
        start, end = -50, 230
        d.arc([cx - r, cy - r, cx + r, cy + r], start, end, fill=white, width=width)
        a = math.radians(end)
        rm = r - width / 2  # rayon au milieu du trait
        px, py = cx + rm * math.cos(a), cy + rm * math.sin(a)
        tx, ty = -math.sin(a), math.cos(a)  # tangente (sens horaire)
        nx, ny = math.cos(a), math.sin(a)
        head, half = u * 0.75, u * 0.55
        d.polygon([
            (px + tx * head, py + ty * head),
            (px + nx * half, py + ny * half),
            (px - nx * half, py - ny * half),
        ], fill=white)

def main() -> None:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = int(S * 0.44)
    bin_(d, int(S * 0.04), w, int(S * 0.22), GREY, GREY_DARK, "bag")
    bin_(d, int(S * 0.52), w, int(S * 0.22), YELLOW, YELLOW_DARK, "recycle")
    img = img.crop(img.getbbox())
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon.png", 256), ("icon@2x.png", 512)):
        square.resize((size, size), Image.LANCZOS).save(OUT / name, optimize=True)
        print(OUT / name)


if __name__ == "__main__":
    main()
