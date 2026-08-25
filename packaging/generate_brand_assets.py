from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
EXTENSION_ICONS = ROOT / "web-extension" / "icons"

def extract_selected_mark() -> Image.Image:
    source = Image.open(ASSETS / "brand-source.png").convert("RGB")
    red, green, blue = source.split()
    maximum = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    minimum = ImageChops.darker(ImageChops.darker(red, green), blue)
    chroma = ImageChops.subtract(maximum, minimum)
    alpha = chroma.point(lambda value: 255 if value >= 5 else 0)
    alpha = alpha.filter(ImageFilter.MinFilter(5))
    mark = source.convert("RGBA")
    mark.putalpha(alpha)
    return mark.resize((1024, 1024), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    EXTENSION_ICONS.mkdir(parents=True, exist_ok=True)
    master = extract_selected_mark()
    master.save(ASSETS / "brand-mark.png", optimize=True)
    header_badge = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    badge_draw = ImageDraw.Draw(header_badge)
    badge_draw.rounded_rectangle((32, 32, 992, 992), radius=190, fill="#FFFFFF")
    badge_mark = master.resize((800, 800), Image.Resampling.LANCZOS)
    header_badge.alpha_composite(badge_mark, (112, 112))
    header_badge.resize((64, 64), Image.Resampling.LANCZOS).save(
        ASSETS / "brand-header.png", optimize=True
    )
    master.save(
        ASSETS / "softauto.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    for size in (16, 32, 48, 128):
        icon = master.resize((size, size), Image.Resampling.LANCZOS)
        icon.save(EXTENSION_ICONS / f"icon-{size}.png", optimize=True)


if __name__ == "__main__":
    main()
