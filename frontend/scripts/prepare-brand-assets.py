"""Extract approved FORESITE pixels, never redraw the logo. Requires Pillow 13.0.0.

Run from repository root: python frontend/scripts/prepare-brand-assets.py
The original public/foresite-logo.png stays byte-identical. Fixed crop coordinates
refer to the approved 2172x724 artwork; a different source requires review.
"""

import hashlib
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, __version__

PUBLIC = Path(__file__).resolve().parents[1] / "public"
SOURCE = PUBLIC / "foresite-logo.png"
APPROVED = "56ddbbb30501102a1700f57510feb5a18db2cbcb588e55bd558f42128ea5617d"
FULL = (164, 140, 2010, 602)
WORDMARK = (164, 140, 2010, 538)
CYCLONE = (355, 139, 779, 539)


def extract_cyclone(source):
    """Separate the cyclone from the adjacent F; retain original RGB/alpha edges."""
    crop = source.crop(CYCLONE)
    alpha = crop.getchannel("A")
    mask = alpha.point(lambda a: 255 if a >= 8 else 0)
    pixels = mask.load()
    components = []
    for y in range(crop.height):
        for x in range(crop.width):
            if not pixels[x, y]:
                continue
            queue, component = deque([(x, y)]), []
            pixels[x, y] = 0
            while queue:
                u, v = queue.popleft()
                component.append((u, v))
                for xx, yy in ((u - 1, v), (u + 1, v), (u, v - 1), (u, v + 1)):
                    if (
                        0 <= xx < crop.width
                        and 0 <= yy < crop.height
                        and pixels[xx, yy]
                    ):
                        pixels[xx, yy] = 0
                        queue.append((xx, yy))
            components.append(component)
    selected = max(components, key=len)
    assert len(selected) == 100079, "Unexpected artwork segmentation; review the source"
    silhouette = Image.new("L", crop.size)
    for xy in selected:
        silhouette.putpixel(xy, 255)
    # Include the original faint anti-alias edge, excluding all adjacent letter pixels.
    silhouette = silhouette.filter(ImageFilter.MaxFilter(5))
    for component in components:
        if component is not selected:
            for xy in component:
                silhouette.putpixel(xy, 0)
    crop.putalpha(ImageChops.darker(alpha, silhouette))
    return crop.crop(crop.getbbox())


def square(image, size, padding):
    canvas = Image.new("RGBA", (size, size))
    inside = ImageOps.contain(
        image, (size - padding * 2, size - padding * 2), Image.Resampling.LANCZOS
    )
    canvas.alpha_composite(
        inside, ((size - inside.width) // 2, (size - inside.height) // 2)
    )
    return canvas


def main():
    if not SOURCE.is_file():
        raise SystemExit(
            "Approved public/foresite-logo.png is missing; supply the official PNG first"
        )
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == APPROVED, (
        "Unapproved source image"
    )
    original = Image.open(SOURCE).convert("RGBA")
    assert original.size == (2172, 724)
    full = original.crop(FULL)
    compact = original.crop(WORDMARK)
    icon = extract_cyclone(original)
    assets = {
        "foresite-logo-full.png": ImageOps.contain(
            full, (1200, 1200), Image.Resampling.LANCZOS
        ),
        "foresite-wordmark.png": ImageOps.contain(
            compact, (768, 768), Image.Resampling.LANCZOS
        ),
        "foresite-cyclone.png": square(icon, 384, 12),
        "foresite-favicon-16.png": square(icon, 16, 1),
        "foresite-favicon-32.png": square(icon, 32, 1),
        "foresite-apple-touch-icon.png": square(icon, 180, 8),
        "foresite-icon-192.png": square(icon, 192, 8),
    }
    # Metadata preview is a presentation surface, not a recolored logo variant.
    social = Image.new("RGBA", (1200, 630), "white")
    artwork = ImageOps.contain(full, (1080, 450), Image.Resampling.LANCZOS)
    social.alpha_composite(
        artwork, ((1200 - artwork.width) // 2, (630 - artwork.height) // 2)
    )
    assets["foresite-social.png"] = social
    manifest = {
        "source_sha256": APPROVED,
        "pillow_version": __version__,
        "crop_boxes": {"full": FULL, "wordmark": WORDMARK, "cyclone": CYCLONE},
        "assets": {},
    }
    for name, image in assets.items():
        target = PUBLIC / name
        image.save(target, optimize=True)
        manifest["assets"][name] = {
            "width": image.width,
            "height": image.height,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        }
    ico = PUBLIC / "foresite-favicon.ico"
    square(icon, 48, 2).save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    manifest["assets"][ico.name] = {
        "sizes": [16, 32, 48],
        "sha256": hashlib.sha256(ico.read_bytes()).hexdigest(),
    }
    (PUBLIC / "foresite-brand-assets.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
