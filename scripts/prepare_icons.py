#!/usr/bin/env python3
"""Generate platform icon variants from docs/assets/icon_eMeX.png."""
from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "docs" / "assets"
SOURCE = ASSET_DIR / "icon_eMeX.png"
ICO = ASSET_DIR / "icon_eMeX.ico"
ICNS = ASSET_DIR / "icon_eMeX.icns"


def _load_square_icon() -> Image.Image:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Missing source icon: {SOURCE}")
    image = Image.open(SOURCE).convert("RGBA")
    size = max(image.size)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(image, ((size - image.width) // 2, (size - image.height) // 2))
    return canvas


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    icon = _load_square_icon()

    icon.save(
        ICO,
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    icon.save(
        ICNS,
        sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
    )

    print(f"Wrote {ICO}")
    print(f"Wrote {ICNS}")


if __name__ == "__main__":
    main()
