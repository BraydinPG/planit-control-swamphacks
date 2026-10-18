"""Make the user-authorized exact pixel cutout. Requires Pillow 13.0.0.

Run from repository root: python frontend/scripts/prepare-brand-assets.py
The committed branding/foresite-logo-source.png stays byte-identical. Only alpha
changes for foreground pixels; RGB is zeroed where the background is fully removed.
Fixed coordinates/key thresholds refer to the approved 1983x793 replacement artwork.
"""

import hashlib
import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps, __version__

PUBLIC = Path(__file__).resolve().parents[1] / "public"
SOURCE = PUBLIC.parent / "branding" / "foresite-logo-source.png"
APPROVED = "2f14dd3437f22fe1ef9c420f0edc7b86878ddb6fec9144540c77caa9aa90d3db"
FULL = (138, 177, 1848, 600)
WORDMARK = (138, 177, 1848, 534)
CYCLONE = (326, 177, 701, 534)
SURFACE = "#0b141d"
LIGHT = PUBLIC / "foresite-logo-light.png"
APPROVED_LIGHT = "05a688ff75edc55538eb2343ffa038aea76d3a0bea7aef604b95848c9cd60fd3"


def remove_background(original):
    """Key the measured 9-18 charcoal background, keeping supplied foreground RGB."""
    rgb = original.convert("RGB")
    alpha = Image.new("L", rgb.size)
    # Every sampled background channel is <=18. The short transition preserves
    # antialiasing; foreground at >=32 stays opaque, including dark blue arms.
    alpha.putdata(
        [
            max(0, min(255, round((max(pixel) - 18) * 255 / 14)))
            for pixel in rgb.get_flattened_data()
        ]
    )
    # The cyclone's enclosed dark eye is negative space too, not a navy disk.
    pixels = rgb.load()
    eye, queue = {(512, 370)}, deque([(512, 370)])
    while queue:
        x, y = queue.popleft()
        for xx, yy in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                470 <= xx < 555
                and 330 <= yy < 415
                and (xx, yy) not in eye
                and max(pixels[xx, yy]) <= 110
            ):
                eye.add((xx, yy))
                queue.append((xx, yy))
    assert len(eye) == 2624, "Unexpected cyclone eye; review the supplied artwork"
    for xy in eye:
        alpha.putpixel(xy, 0)
    cutout = rgb.convert("RGBA")
    cutout.putalpha(alpha)
    cutout.putdata(
        [pixel if pixel[3] else (0, 0, 0, 0) for pixel in cutout.get_flattened_data()]
    )
    return cutout


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
    assert 50000 < len(selected) < 130000, "Unexpected cyclone; review the source"
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


def contain(image, size, padding=0):
    canvas = Image.new("RGBA", size)
    inside = ImageOps.contain(
        image, (size[0] - padding * 2, size[1] - padding * 2), Image.Resampling.LANCZOS
    )
    canvas.alpha_composite(
        inside, ((size[0] - inside.width) // 2, (size[1] - inside.height) // 2)
    )
    return canvas


def square(image, size, padding):
    return contain(image, (size, size), padding)


def main():
    if not SOURCE.is_file():
        raise SystemExit("Approved branding/foresite-logo-source.png is missing")
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == APPROVED, (
        "Unapproved source image"
    )
    assert LIGHT.is_file(), "Approved committed light-mode variant is missing"
    assert hashlib.sha256(LIGHT.read_bytes()).hexdigest() == APPROVED_LIGHT, (
        "Unapproved light-mode variant"
    )
    original = Image.open(SOURCE).convert("RGB")
    assert original.size == (1983, 793)
    original = remove_background(original)
    full = original.crop(FULL)
    compact = original.crop(WORDMARK)
    icon = extract_cyclone(original)
    assets = {
        "foresite-logo.png": original,
        "foresite-logo-light.png": Image.open(LIGHT).convert("RGBA"),
        "foresite-logo-full.png": contain(full, (1200, 300)),
        "foresite-wordmark.png": contain(compact, (768, 166)),
        "foresite-cyclone.png": square(icon, 384, 12),
        "foresite-favicon-16.png": square(icon, 16, 1),
        "foresite-favicon-32.png": square(icon, 32, 1),
        "foresite-apple-touch-icon.png": square(icon, 180, 8),
        "foresite-icon-192.png": square(icon, 192, 8),
    }
    # Metadata preview is a presentation surface, not a recolored logo variant.
    social = Image.new("RGBA", (1200, 630), SURFACE)
    artwork = ImageOps.contain(full, (1080, 450), Image.Resampling.LANCZOS)
    social.alpha_composite(
        artwork, ((1200 - artwork.width) // 2, (630 - artwork.height) // 2)
    )
    assets["foresite-social.png"] = social
    manifest = {
        "source_sha256": APPROVED,
        "source_file": "frontend/branding/foresite-logo-source.png",
        "light_source": {"approved_commit": "4508e9d", "sha256": APPROVED_LIGHT},
        "pillow_version": __version__,
        "method": "user-authorized pixel cutout; foreground RGB unchanged",
        "alpha_key": {
            "background_max_channel": 18,
            "opaque_min_channel_max": 32,
            "eye_pixels_removed": 2624,
        },
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
