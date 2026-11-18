"""Build the CABBAGE Windows app icon (transparent multi-resolution ICO).

Only required when PACKAGING. The installed app needs no Pillow or Python.
"""
from pathlib import Path

def build_icon(destination: Path | None = None) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise RuntimeError("Install Pillow in the Windows build environment first") from exc

    if destination is None:
        destination = Path(__file__).resolve().parent / "branding" / "CabbageStudio.ico"
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 256
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Deep navy square with softly rounded silhouette.
    d.rounded_rectangle((9, 9, 246, 246), radius=61,
                        fill=(12, 25, 41), outline=(55, 95, 120), width=5)
    # Mint luminous ring and two side wheels, evoking a differential drive car.
    d.arc((38, 35, 218, 218), start=32, end=327, fill=(74, 232, 199), width=15)
    d.rounded_rectangle((53, 91, 79, 173), radius=12, fill=(93, 125, 159))
    d.rounded_rectangle((177, 91, 203, 173), radius=12, fill=(93, 125, 159))
    d.rounded_rectangle((84, 70, 173, 192), radius=27,
                        fill=(27, 64, 78), outline=(105, 220, 205), width=5)
    d.polygon([(128, 81), (107, 115), (149, 115)], fill=(74, 232, 199))
    # Strong single-line "C" mark, readable even at 16x16 icon size.
    d.arc((103, 108, 154, 162), 53, 303, fill=(244, 249, 255), width=12)
    # Save real multi-size ICO. Explicit ICO prevents misleading .png rename.
    im.save(destination, format="ICO", sizes=[
        (16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
        (96, 96), (128, 128), (256, 256),
    ])
    return destination


if __name__ == "__main__":
    print(build_icon())
